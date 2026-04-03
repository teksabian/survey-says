"""Round creation, activation, closing, answer upload and editing routes."""

import os
import time
from flask import request, render_template, redirect, url_for, jsonify, flash

from config import (
    logger, BASE_DIR,
    AI_SCORING_ENABLED, AI_MODEL_CHOICES,
    FEUD_QUESTIONS_PROMPT, FEUD_ANSWERS_PROMPT, FEUD_REGEN_QUESTION_PROMPT,
)
from auth import host_required
from database import db_connect, get_setting, set_setting
from survey_history import save_survey_history, build_past_questions_block
from extensions import socketio
from parsers import parse_pptx, parse_docx
from ai import (
    _call_ai_for_generation, _parse_json_response,
    get_current_generation_model,
)

from routes.host import (host_bp, ROUNDS_CONFIG, DEFAULT_ROUNDS_CONFIG, build_rounds_config,
                         MIN_ROUNDS, MAX_ROUNDS, MIN_ANSWERS, MAX_ANSWERS,
                         DEFAULT_NUM_ROUNDS, DEFAULT_ANSWERS_PER_ROUND)

# Pre-built surveys for quick round creation via dropdown
PREBUILT_SURVEYS = {
    "survey1": {
        "name": "Survey 1",
        "rounds": [
            {"question": "Name Something Parents Warn Their Children Not To Get Their Fingers Caught In", "answers": ["Door", "Fan", "Outlet", "Cookie Jar"], "answer1_count": 45},
            {"question": "A Young Person \u201cFights For Their Right To Party.\u201d What Might An Old Person Fight For The Right To Do?", "answers": ["Sleep", "Vote", "Retire", "Keep License", "Get Social Security"], "answer1_count": 32},
            {"question": "Name Something That Goes Well With Pizza", "answers": ["Beer", "Soda", "Salad", "Breadstick/Knots", "Chicken Wings", "Chips"], "answer1_count": 36},
            {"question": "Name Something From The Laundry That\u2019s Impossible To Fold Neatly", "answers": ["Fitted Sheets", "Socks", "Underwear", "Blouse"], "answer1_count": 35},
            {"question": "Name A Place Where You\u2019d Be Mortified If Your Cell Phone Went Off", "answers": ["Church", "Funeral", "Movie Theater", "Job Interview", "Wedding"], "answer1_count": 39},
            {"question": "Name Something You Should Switch Off Before Going To Bed", "answers": ["Lights", "Phone", "TV"], "answer1_count": 67},
            {"question": "Name A Common Sickness That Kids Seem To Get More Often Than Adults", "answers": ["Cold", "Flu", "Chicken Pox", "Ear Infection", "Strep Throat"], "answer1_count": 32},
            {"question": "Name A Reason Why A Man Would Wax Hair Off Part Of His Body", "answers": ["Too Hairy", "For Spouse/Date", "Body Builder", "Swimmer"], "answer1_count": 34},
        ]
    },
    "survey2": {
        "name": "Survey 2",
        "rounds": [
            {"question": "Name Something Permanent On a Criminal\u2019s Skin That Police Use To Be Sure They\u2019ve Got Their Man", "answers": ["Tattoo", "Fingerprint", "Scar", "Birthmark"], "answer1_count": 41},
            {"question": "What Might Someone Use While Cutting Their Own Hair?", "answers": ["Scissors", "Mirror", "Clippers", "Comb", "Bowl"], "answer1_count": 48},
            {"question": "Name Something Babies And Puppies Have In Common", "answers": ["Cute", "Drooling", "Need Attention", "Playful", "Sleep A lot", "Cry"], "answer1_count": 34},
            {"question": "What Diaper Bag Item Would A Parent Hate To Be Without?", "answers": ["Diapers", "Wipes", "Bottle", "Pacifier"], "answer1_count": 49},
            {"question": "Name Something Twins Might Always Share", "answers": ["Looks", "Parents", "Genes", "Birthday", "Last Name"], "answer1_count": 40},
            {"question": "Something Specific People Do In Front Of Mirror", "answers": ["Apply Makeup", "Check Outfit", "Pose Naked"], "answer1_count": 63},
            {"question": "Name A Type Of Sauce That You\u2019d Never Put On Pasta", "answers": ["Apple Sauce", "Hot Sauce", "Ketchup", "BBQ", "Chocolate"], "answer1_count": 30},
            {"question": "Name Something A Child Does To Prove They\u2019re Too Sick For School", "answers": ["Cough", "Vomit", "Cry", "Take Temperature"], "answer1_count": 50},
        ]
    },
    "survey3": {
        "name": "Survey 3",
        "rounds": [
            {"question": "Name Something You Might Adjust When You Get Into A Rental Car", "answers": ["Seat", "Mirrors", "Seat Belt", "Steering Wheel"], "answer1_count": 58},
            {"question": "Name Something A Woman Should Know A Man Before Marrying Him", "answers": ["Income", "Age", "Does He Have Kids", "His Name", "Past Relationships"], "answer1_count": 39},
            {"question": "Name Something You Need In Order To Make A Garden", "answers": ["Seeds", "Soil", "Water", "Hoe", "Shovel", "Plot of Land"], "answer1_count": 35},
            {"question": "Name A Place Where You Hear People Being Paged Over A Loudspeaker", "answers": ["Hospital", "Airport", "School", "Store"], "answer1_count": 31},
            {"question": "Tell Me Something You Do When You Stay Up Late At Night", "answers": ["Watch TV/Movie", "Read", "Snack", "Drink", "Play Phone/Video Games"], "answer1_count": 58},
            {"question": "Name A Crime That Some People Probably Commit Every Day", "answers": ["Speeding", "Jaywalking", "Littering"], "answer1_count": 62},
            {"question": "Name A Reason Why A Person Might Prefer To Own A Dog Over A Cat", "answers": ["Protection", "Loyalty", "Cat Allergies", "Friendlier", "More fun to play with"], "answer1_count": 54},
            {"question": "Name A Phrase You\u2019d Say To Your Partner That Starts With \u201cYou Drive Me __.\u201d", "answers": ["Crazy/Nuts", "Wild", "Up a Wall", "To Drink"], "answer1_count": 58},
        ]
    },
    "survey4": {
        "name": "Survey 4",
        "rounds": [
            {"question": "We Asked 100 Women: Name A Gift That You\u2019d Always Be Happy To Get From Your Partner", "answers": ["Flowers", "Jewelry", "Money", "Chocolate"], "answer1_count": 43},
            {"question": "Name A Slow-Moving Vehicle That You Hate To Get Stuck Behind", "answers": ["Bus", "Semi-Truck", "Tractor", "Garbage Truck", "Dump Truck"], "answer1_count": 34},
            {"question": "Name A Last Minute Problem That Could Make You Late For Work", "answers": ["Traffic", "Car Trouble", "Lost Keys", "Child is Sick", "No Gas", "Bad Hair"], "answer1_count": 35},
            {"question": "Name Something Parents Warn Their Children Not To Get Their Fingers Caught In", "answers": ["Door", "Fan", "Outlet", "Cookie Jar"], "answer1_count": 45},
            {"question": "Name Something You Spray On Yourself That Would Sting If It Got In Your Eyes", "answers": ["Perfume", "Insect Repellent", "Hairspray", "Sunscreen/Tan", "Deodorant"], "answer1_count": 34},
            {"question": "Name Something You Dunk", "answers": ["Basketball", "Donuts", "Cookies"], "answer1_count": 59},
            {"question": "Name Something You Wear That Covers Your Ears", "answers": ["Earmuffs", "Hat", "Headphones", "Scarf", "Hood"], "answer1_count": 49},
            {"question": "Name Something A Politician Does When Scandalous News Breaks Out About Them", "answers": ["Lie/Deny It", "Go Into Hiding", "Apology/Press Conference", "Resign"], "answer1_count": 49},
        ]
    },
    "survey5": {
        "name": "Survey 5",
        "rounds": [
            {"question": "Name a chore kids try to avoid", "answers": ["Doing the Dishes", "Cleaning Their Room", "Taking Out The Trash", "Mowing The Lawn"], "answer1_count": 43},
            {"question": "What Would You Hear On The Radio That Would Make You Turn The Station?", "answers": ["Commercial", "News", "Bad Song", "Static", "Cursing"], "answer1_count": 34},
            {"question": "Name Something People Do With Both Hands", "answers": ["Drive", "Dishes", "Type on Keyboard", "Clap", "Cook", "Eat"], "answer1_count": 40},
            {"question": "Name A Day Of The Year That Some People Don\u2019t Want To Spend Alone", "answers": ["Christmas", "Valentines Day", "Birthday", "New Years Eve"], "answer1_count": 40},
            {"question": "Name Something You Might Pay Someone To Do While You\u2019re Away On Vacation", "answers": ["Care for Pets", "House Sit", "Water Plants", "Babysit", "Collect Mail"], "answer1_count": 28},
            {"question": "What Do You Find Out About A Town By Reading Signs On The Side Of The Road?", "answers": ["Population", "Town Name", "Speed Limit"], "answer1_count": 60},
            {"question": "Other Than Academics Why Might A Teen Choose A Certain College?", "answers": ["Sports Team", "Location", "Friends are Going", "Party School", "Cost of Tuition"], "answer1_count": 47},
            {"question": "Name Something That\u2019s On Your Dinner Table Every Night That The Dog Won\u2019t Beg For", "answers": ["Veggies/Salad", "Salt", "Silverware/Plates", "Napkins"], "answer1_count": 45},
        ]
    },
    "survey6": {
        "name": "Survey 6",
        "rounds": [
            {"question": "If You\u2019re Driving In The Middle Of No Where, What Animal Might You See Crossing The Street?", "answers": ["Deer", "Cow", "Moose", "Coyote"], "answer1_count": 50},
            {"question": "how Many Hours Of Sleep Does The average person Need In Oder To Wake Up Refreshed?", "answers": ["8", "7", "6", "10", "9"], "answer1_count": 47},
            {"question": "Name Something There Are Seven Of", "answers": ["Dwarfs", "Deadly Sins", "Wonders of the World", "Days Per Week", "Sins", "Continents"], "answer1_count": 28},
            {"question": "Name An Activity That\u2019d Be Hard To Do By Candlelight", "answers": ["Read", "Cook", "Write", "Sewing/Knitting"], "answer1_count": 62},
            {"question": "Name Something That Happens To An Old Person\u2019s Body, That You\u2019d Be Surprised To Hear A teen Complaining About", "answers": ["Wrinkles", "Arthritis", "Gray Hair", "Sagging", "Back Ache"], "answer1_count": 50},
            {"question": "Name something you might find in a kitchen drawer", "answers": ["Silverware/Utensils", "Knives", "Can Opener", "Scissors", "Junk/Batteries"], "answer1_count": 42},
            {"question": "Name A Good Place To Put Your Hands While Kissing Someone", "answers": ["Their Face", "Around Their Neck", "Their Hips", "Their Back", "Their Shoulders"], "answer1_count": 27},
            {"question": "Instead Of Their First Name, What Might A Parent Shout When Calling For Their Child?", "answers": ["Whole Name", "Nickname", "Hey!", "Siblings Name"], "answer1_count": 38},
        ]
    },
    "survey7": {
        "name": "Survey 7",
        "rounds": [
            {"question": "Name A Place An Animal Might Take A Bath, But You Never Would", "answers": ["Lake/Pond", "Puddle", "River", "Bird Bath"], "answer1_count": 51},
            {"question": "Name a job title someone might have in a big company", "answers": ["CEO", "President", "Vice President", "Supervisor", "Manager"], "answer1_count": 39},
            {"question": "Name A Job Where It Would Be Okay To Yell At Work", "answers": ["Construction", "Sports", "Teacher", "Police", "Stock Brocker", "Auctioneer"], "answer1_count": 43},
            {"question": "What Are 2 Brothers Most Likely To Fight Over?", "answers": ["Girls", "Toys", "TV Remote", "Attention"], "answer1_count": 45},
            {"question": "Name A Way You Can Tell A Storm Is Coming", "answers": ["Dark Clouds", "Lightning", "Wind Changes", "Smell", "Drizzling"], "answer1_count": 61},
            {"question": "Name Something A Plane Can't Fly Without", "answers": ["Wings", "Fuel", "A Pilot"], "answer1_count": 42},
            {"question": "Tell Me A Reason You Might Be Low On Sleep", "answers": ["Overworked", "Kids/New Baby", "Can\u2019t Sleep", "Sick", "Studying"], "answer1_count": 44},
            {"question": "Name A Color Baby Clothes Comes in", "answers": ["Pink", "Blue", "Yellow", "Green"], "answer1_count": 47},
        ]
    },
    "survey8": {
        "name": "Survey 8",
        "rounds": [
            {"question": "Last thing you\u2019d want to happen at the airport", "answers": ["Miss Flight", "Lose Luggage", "Stopped By Security", "Delayed"], "answer1_count": 0},
            {"question": "Something you do when approached by a salesperson", "answers": ["Avoid Them", "Ask For Help", "Smile", "Say Hi", "Just Looking"], "answer1_count": 0},
            {"question": "Someone you hope never writes a tell-all book", "answers": ["Parent", "Significant Other", "Ex", "Best Friend", "Sibling", "Son/Daughter"], "answer1_count": 0},
            {"question": "Something people check on their smartwatch", "answers": ["Steps", "Notifications", "Heart Rate", "Time"], "answer1_count": 0},
            {"question": "Famous phrase from The Wizard of Oz", "answers": ["Off To See The Wizard", "No Place Like Home", "Follow The Yellow Brick Road", "I\u2019ll Get You My Pretty", "Lions, Tigers & Bears!"], "answer1_count": 0},
            {"question": "Place people stash a spare charging cable", "answers": ["Car", "Work Desk", "Backpack/Purse"], "answer1_count": 0},
            {"question": "Chore that takes less than 10 minutes", "answers": ["Take Out Trash", "Wipe Counter", "Make The Bed", "Load Dishwasher", "Water Plants"], "answer1_count": 0},
            {"question": "Feature people look for in a new phone", "answers": ["Battery Life", "Camera", "Price", "Storage"], "answer1_count": 0},
        ]
    },
    "survey9": {
        "name": "Survey 9",
        "rounds": [
            {"question": "Name Something People Do To Get Ready For A Party", "answers": ["Get Dressed Up", "Clean The House", "Buy Food/Drinks", "Shower", "Do Hair/Makeup"], "answer1_count": 38},
            {"question": "Name A Reason Someone Might Return A Gift", "answers": ["Wrong Size", "Didn't Like It", "Already Have It", "Broken/Defective"], "answer1_count": 45},
            {"question": "Name Something You Associate With A Cowboy", "answers": ["Hat", "Horse", "Boots", "Lasso/Rope", "Rodeo"], "answer1_count": 40},
            {"question": "Name Something That Gets Passed Around", "answers": ["Ball", "Germs/Cold", "Collection Plate", "Gossip/Rumors", "Salt/Pepper"], "answer1_count": 33},
            {"question": "Name A Place Where You Have To Be Quiet", "answers": ["Library", "Church", "Hospital", "Movie Theater", "Classroom"], "answer1_count": 42},
            {"question": "Name Something People Collect", "answers": ["Stamps", "Coins", "Baseball Cards", "Dolls", "Rocks"], "answer1_count": 35},
            {"question": "Name A Reason You Might Stay Home From Work", "answers": ["Sick", "Kid Is Sick", "Bad Weather", "Mental Health Day", "Appointment"], "answer1_count": 55},
            {"question": "Name Something You Would Find On A Beach", "answers": ["Sand", "Shells", "Towels", "Seagulls", "Waves/Water"], "answer1_count": 48},
        ]
    },
}


@host_bp.route('/host/upload-answers', methods=['POST'])
@host_required
def upload_answers():
    """Upload DOCX or PPTX answer sheet and auto-create all rounds"""
    logger.info("[UPLOAD] upload_answers() - file upload started")
    try:
        if 'file' not in request.files:
            logger.warning("[UPLOAD] No file in request")
            flash('No file uploaded!', 'error')
            return redirect(url_for('.host_dashboard'))

        file = request.files['file']
        if file.filename == '':
            logger.warning("[UPLOAD] No file selected")
            flash('No file selected!', 'error')
            return redirect(url_for('.host_dashboard'))

        # Accept .docx, .pptx, and .pptm files
        file_ext = os.path.splitext(file.filename)[1].lower()
        logger.info(f"[UPLOAD] File received: '{file.filename}', type={file_ext}")
        if file_ext not in ['.docx', '.pptx', '.pptm']:
            logger.warning(f"[UPLOAD] Invalid file type: {file_ext}")
            flash('Please upload a .docx, .pptx, or .pptm file!', 'error')
            return redirect(url_for('.host_dashboard'))

        # Save temp file
        temp_path = os.path.join(BASE_DIR, f'temp_answers_{int(time.time())}{file_ext}')
        file.save(temp_path)

        # Parse based on file type
        rounds_data = []

        if file_ext == '.docx':
            rounds_data = parse_docx(temp_path)

        elif file_ext in ['.pptx', '.pptm']:
            rounds_data = parse_pptx(temp_path)

        # Always create all rounds found (should be 8)
        with db_connect() as conn:
            conn.execute("DELETE FROM rounds")
            conn.execute("DELETE FROM submissions")

            for idx, round_data in enumerate(rounds_data):
                round_num = idx + 1
                num_answers = len(round_data['answers'])
                # Clamp to valid range
                num_answers = max(MIN_ANSWERS, min(MAX_ANSWERS, num_answers)) if num_answers > 0 else MIN_ANSWERS

                fields = ['round_number', 'question', 'num_answers', 'is_active']
                values = [round_num, round_data['question'], num_answers, 0]

                for i in range(1, num_answers + 1):
                    if i <= len(round_data['answers']):
                        fields.append(f'answer{i}')
                        fields.append(f'answer{i}_count')
                        values.append(round_data['answers'][i-1]['answer'])
                        values.append(round_data['answers'][i-1]['count'])

                placeholders = ','.join(['?'] * len(values))
                conn.execute(f"INSERT INTO rounds ({','.join(fields)}) VALUES ({placeholders})", values)

            conn.commit()

        if os.path.exists(temp_path):
            os.remove(temp_path)

        rounds_created = len(rounds_data)
        set_setting('rounds_source', 'upload', 'How current rounds were created')
        logger.info(f"[UPLOAD] Complete: {rounds_created} rounds created from '{file.filename}'")
        for idx, rd in enumerate(rounds_data):
            logger.debug(f"[UPLOAD]   Round {idx+1}: Q='{rd['question'][:60]}', {len(rd['answers'])} answers")
        flash(f'\u2705 Success! {rounds_created} rounds created!', 'success')
        return redirect(url_for('.host_dashboard'))

    except FileNotFoundError as e:
        logger.error(f"[UPLOAD] FileNotFoundError: {e}")
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        flash(f'\u274c File error: Could not read the uploaded file. Please try again.', 'error')
        return redirect(url_for('.host_dashboard'))
    except ImportError as e:
        logger.error(f"[UPLOAD] ImportError (missing library): {e}")
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        flash(f'\u274c Missing library: {str(e)}. Please install required dependencies.', 'error')
        return redirect(url_for('.host_dashboard'))
    except Exception as e:
        logger.error(f"[UPLOAD] Unexpected error: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"[UPLOAD] Traceback:\n{traceback.format_exc()}")
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass

        # Provide helpful error messages based on the error type
        error_msg = str(e)
        if 'pptx' in error_msg.lower() or 'presentation' in error_msg.lower():
            flash(f'\u274c PowerPoint parsing error: The file format may be corrupted or unsupported. Details: {error_msg}', 'error')
        elif 'docx' in error_msg.lower() or 'document' in error_msg.lower():
            flash(f'\u274c Word document parsing error: The file format may be corrupted. Details: {error_msg}', 'error')
        elif 'table' in error_msg.lower():
            flash(f'\u274c Table parsing error: Could not read answer tables. Make sure your file has the correct format. Details: {error_msg}', 'error')
        else:
            flash(f'\u274c Upload failed: {error_msg}', 'error')

        return redirect(url_for('.host_dashboard'))

@host_bp.route('/host/round/create', methods=['POST'])
@host_required
def create_round():
    """Create a round manually"""
    round_num = int(request.form.get('round_number'))
    question = request.form.get('question', '').strip()
    logger.info(f"[ROUND] create_round() - round_num={round_num}, question='{question[:50] if question else ''}'")

    if not question:
        flash('Question cannot be empty.', 'error')
        return redirect(url_for('.host_dashboard'))

    config = next((r for r in ROUNDS_CONFIG if r['round'] == round_num), None)
    if not config:
        logger.warning(f"[ROUND] create_round() - invalid round number: {round_num}")
        return "Invalid round number", 400

    with db_connect() as conn:
        conn.execute("UPDATE rounds SET is_active = 0")
        conn.execute("""
            INSERT INTO rounds (round_number, question, num_answers, is_active)
            VALUES (?, ?, ?, 1)
        """, (round_num, question, config['answers']))
        conn.commit()
    logger.info(f"[ROUND] create_round() - round {round_num} created and activated")
    return redirect(url_for('.host_dashboard'))

@host_bp.route('/host/round/<int:round_id>/activate', methods=['POST'])
@host_required
def activate_round(round_id):
    """Activate a specific round"""
    logger.info(f"[ROUND] activate_round() - requesting activation of round_id={round_id}")
    with db_connect() as conn:
        # CRITICAL FIX: Validate that round has answers before activating
        round_data = conn.execute(
            "SELECT answer1, question FROM rounds WHERE id = ?",
            (round_id,)
        ).fetchone()

        if not round_data:
            logger.warning(f"[ROUND] activate_round() - round_id={round_id} not found")
            flash('\u274c Round not found!', 'error')
            return redirect(url_for('.host_dashboard'))

        if not round_data['answer1']:
            logger.warning(f"[ROUND] activate_round() - round_id={round_id} has no answers, blocking activation")
            flash('\u274c Cannot activate round without answers! Please set answers first.', 'error')
            return redirect(url_for('.host_dashboard'))

        # CRITICAL FIX: Use transaction to prevent race conditions
        # Deactivate ALL rounds, then activate the selected one atomically
        conn.execute("BEGIN IMMEDIATE")  # Lock database to prevent race conditions
        try:
            conn.execute("UPDATE rounds SET is_active = 0")
            conn.execute("UPDATE rounds SET is_active = 1 WHERE id = ?", (round_id,))
            conn.commit()

            round_info = conn.execute(
                "SELECT id, round_number, question, num_answers FROM rounds WHERE id = ?",
                (round_id,)
            ).fetchone()
            round_started_data = {
                'round_id': round_info['id'],
                'round_number': round_info['round_number'],
                'question': round_info['question'],
                'num_answers': round_info['num_answers']
            }
            socketio.emit('round:started', round_started_data, to='teams')
            socketio.emit('round:started', round_started_data, to='hosts')

            # Auto-sync TV board if enabled
            if get_setting('tv_board_enabled', 'true') == 'true':
                from tv_state import reset_for_round, get_tv_state
                reset_for_round(round_info['id'])
                socketio.emit('tv:state_update', get_tv_state(), to='tv')

            logger.info(f"[ROUND] activate_round() - round_id={round_id} now active (deactivated all others)")
            flash(f'\u2705 Round activated: {round_data["question"]}', 'success')
        except Exception as e:
            conn.rollback()
            logger.error(f"[ROUND] activate_round() - error: {e}")
            flash(f'\u274c Error activating round: {str(e)}', 'error')

    return redirect(url_for('.host_dashboard'))

@host_bp.route('/host/round/<int:round_id>/answers', methods=['POST'])
@host_required
def set_answers(round_id):
    """Set correct answers for a round"""
    logger.debug(f"[ROUND] set_answers() - round_id={round_id}")
    with db_connect() as conn:
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
        num_answers = round_info['num_answers']
        logger.debug(f"[ROUND] Setting {num_answers} answers for round {round_info['round_number']}")

        fields = []
        values = []
        for i in range(1, 7):
            if i <= num_answers:
                fields.append(f'answer{i} = ?')
                fields.append(f'answer{i}_count = ?')
                values.append(request.form.get(f'answer{i}', '').strip())
                values.append(int(request.form.get(f'answer{i}_count', 0) or 0))

        answer1 = request.form.get('answer1', '').strip()
        if not answer1:
            flash('Answer #1 (top answer) is required.', 'error')
            return redirect(url_for('.host_dashboard'))

        values.append(round_id)
        conn.execute(f"UPDATE rounds SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    logger.info(f"[ROUND] set_answers() - answers saved for round_id={round_id}")
    return redirect(url_for('.host_dashboard'))

@host_bp.route('/host/check-active-round')
@host_required
def check_active_round():
    """API endpoint to check if there's an active round (for AJAX polling)"""
    with db_connect() as conn:
        active_round = conn.execute(
            "SELECT id, round_number FROM rounds WHERE is_active = 1"
        ).fetchone()
        has_active = active_round is not None
        logger.debug(f"[API] check_active_round() = {has_active}")
        result = {'has_active_round': has_active}
        if active_round:
            result['round_id'] = active_round['id']
            result['round_number'] = active_round['round_number']
        return jsonify(result)

@host_bp.route('/host/start-next-round', methods=['POST'])
@host_required
def start_next_round():
    """Move to next round"""
    logger.debug("[ROUND] start_next_round() called")
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()

        if active_round:
            current_num = active_round['round_number']
            logger.info(f"[ROUND] Current active round: {current_num}, advancing to {current_num + 1}")
            # Deactivate current
            conn.execute("UPDATE rounds SET is_active = 0 WHERE id = ?", (active_round['id'],))

            # Activate next round
            next_round = conn.execute("""
                SELECT * FROM rounds WHERE round_number = ?
            """, (current_num + 1,)).fetchone()

            if next_round:
                conn.execute("UPDATE rounds SET is_active = 1 WHERE id = ?", (next_round['id'],))
                conn.commit()

                # Include previous round's winner so phones can show the interstitial
                prev_winner = conn.execute("""
                    SELECT r.winner_code, r.round_number, tc.team_name, s.score
                    FROM rounds r
                    LEFT JOIN team_codes tc ON r.winner_code = tc.code
                    LEFT JOIN submissions s ON r.winner_code = s.code AND r.id = s.round_id AND s.host_submitted = 1
                    WHERE r.id = ?
                """, (active_round['id'],)).fetchone()

                round_started_data = {
                    'round_id': next_round['id'],
                    'round_number': next_round['round_number'],
                    'question': next_round['question'],
                    'num_answers': next_round['num_answers'],
                    'mobile_experience': get_setting('mobile_experience', 'advanced_no_pp'),
                    'previous_round_number': active_round['round_number']
                }
                if prev_winner and prev_winner['winner_code']:
                    round_started_data['previous_winner_team'] = prev_winner['team_name']
                    round_started_data['previous_winner_score'] = prev_winner['score']

                    # Include previous round's survey question + answers for the winner screen
                    round_started_data['previous_question'] = active_round['question']
                    prev_answers = []
                    for i in range(1, 7):
                        ans = active_round[f'answer{i}']
                        if ans:
                            prev_answers.append(ans)
                    round_started_data['previous_answers'] = prev_answers

                    # Detect if win was by tiebreaker (multiple teams tied on score)
                    tied_count = conn.execute(
                        "SELECT COUNT(*) FROM submissions WHERE round_id = ? AND host_submitted = 1 AND score = ?",
                        (active_round['id'], prev_winner['score'])
                    ).fetchone()[0]
                    round_started_data['previous_won_on_tiebreaker'] = tied_count > 1
                    round_started_data['previous_tiebreaker_answer'] = active_round['answer1_count']

                # Include leaderboard data for between-round display
                teams = conn.execute("""
                    SELECT tc.team_name, tc.code,
                           COALESCE(SUM(CASE WHEN s.host_submitted = 1 THEN s.score ELSE 0 END), 0) as total_score
                    FROM team_codes tc
                    LEFT JOIN submissions s ON tc.code = s.code
                    WHERE tc.used = 1 AND tc.team_name IS NOT NULL
                    GROUP BY tc.code
                    ORDER BY total_score DESC, tc.team_name ASC
                """).fetchall()
                leaderboard = []
                for i, row in enumerate(teams):
                    leaderboard.append({
                        'team_name': row['team_name'],
                        'total_score': row['total_score'],
                        'rank': i + 1,
                    })
                round_started_data['leaderboard'] = leaderboard

                socketio.emit('round:started', round_started_data, to='teams')
                socketio.emit('round:started', round_started_data, to='hosts')

                # Auto-sync TV board if enabled
                if get_setting('tv_board_enabled', 'true') == 'true':
                    from tv_state import reset_for_round, get_tv_state

                    reset_for_round(next_round['id'])
                    socketio.emit('tv:state_update', get_tv_state(), to='tv')

                logger.info(f"[ROUND] Activated round {current_num + 1} (id={next_round['id']})")
            else:
                # No more rounds - game over
                conn.commit()
                logger.info(f"[ROUND] No round {current_num + 1} found - game complete!")

                # Build final leaderboard for game:over event
                teams = conn.execute("""
                    SELECT tc.team_name, tc.code,
                           COALESCE(SUM(CASE WHEN s.host_submitted = 1 THEN s.score ELSE 0 END), 0) as total_score
                    FROM team_codes tc
                    LEFT JOIN submissions s ON tc.code = s.code
                    WHERE tc.used = 1 AND tc.team_name IS NOT NULL
                    GROUP BY tc.code
                    ORDER BY total_score DESC, tc.team_name ASC
                """).fetchall()

                leaderboard = []
                for i, row in enumerate(teams):
                    leaderboard.append({
                        'team_name': row['team_name'],
                        'total_score': row['total_score'],
                        'rank': i + 1,
                    })

                game_over_data = {
                    'leaderboard': leaderboard,
                    'winner_team': leaderboard[0]['team_name'] if leaderboard else None,
                    'winner_score': leaderboard[0]['total_score'] if leaderboard else 0,
                }

                # Include last round's winner info
                prev_winner = conn.execute("""
                    SELECT r.winner_code, r.round_number, tc.team_name, s.score
                    FROM rounds r
                    LEFT JOIN team_codes tc ON r.winner_code = tc.code
                    LEFT JOIN submissions s ON r.winner_code = s.code AND r.id = s.round_id AND s.host_submitted = 1
                    WHERE r.id = ?
                """, (active_round['id'],)).fetchone()

                if prev_winner and prev_winner['winner_code']:
                    game_over_data['previous_winner_team'] = prev_winner['team_name']
                    game_over_data['previous_winner_score'] = prev_winner['score']
                    game_over_data['previous_round_number'] = prev_winner['round_number']
                    game_over_data['previous_question'] = active_round['question']
                    prev_answers = []
                    for i in range(1, 7):
                        ans = active_round[f'answer{i}']
                        if ans:
                            prev_answers.append(ans)
                    game_over_data['previous_answers'] = prev_answers

                socketio.emit('game:over', game_over_data, to='teams')
                socketio.emit('game:over', game_over_data, to='hosts')
                socketio.emit('game:over', game_over_data, to='tv')
                logger.info(f"[ROUND] Emitted game:over event with {len(leaderboard)} teams")

                # Auto-save AI-generated surveys to history
                if get_setting('rounds_source') == 'ai':
                    try:
                        all_rounds = conn.execute(
                            "SELECT * FROM rounds ORDER BY round_number"
                        ).fetchall()
                        save_survey_history(all_rounds)
                        logger.info("[ROUND] AI-generated survey saved to history")
                    except Exception as e:
                        logger.warning(f"[ROUND] Failed to save survey history: {e}")

                flash('All rounds complete!', 'info'); return redirect(url_for('.host_dashboard'))

        conn.commit()

    return redirect(url_for('.host_dashboard'))

@host_bp.route('/host/round/<int:round_id>/edit-answer/<int:answer_num>')
@host_required
def edit_single_answer(round_id, answer_num):
    """Edit a single answer"""
    logger.info(f"[ROUND] edit_single_answer() - round_id={round_id}, answer_num={answer_num}")
    with db_connect() as conn:
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()

        if not round_info:
            logger.warning(f"[ROUND] edit_single_answer() - round_id={round_id} not found")
            flash('Round not found!', 'error'); return redirect(url_for('.host_dashboard'))

        current_answer = round_info[f'answer{answer_num}']
        current_count = round_info[f'answer{answer_num}_count']

    return render_template('edit_answer.html',
                         round=dict(round_info),
                         answer_num=answer_num,
                         current_answer=current_answer,
                         current_count=current_count)

@host_bp.route('/host/round/<int:round_id>/update-answer/<int:answer_num>', methods=['POST'])
@host_required
def update_single_answer(round_id, answer_num):
    """Update a single answer"""
    new_answer = request.form.get('answer', '').strip()
    logger.info(f"[ROUND] update_single_answer() - round_id={round_id}, answer_num={answer_num}, new_answer='{new_answer}'")

    if answer_num == 1 and not new_answer:
        flash('Answer #1 (top answer) cannot be empty.', 'error')
        return redirect(url_for('.host_dashboard'))

    with db_connect() as conn:
        # Only update count if the form included the count field (answer #1 edit form)
        if 'count' in request.form:
            new_count = int(request.form.get('count', 0) or 0)
            conn.execute(f"""
                UPDATE rounds
                SET answer{answer_num} = ?, answer{answer_num}_count = ?
                WHERE id = ?
            """, (new_answer, new_count, round_id))
        else:
            conn.execute(f"""
                UPDATE rounds
                SET answer{answer_num} = ?
                WHERE id = ?
            """, (new_answer, round_id))

        conn.commit()

    flash('\u2705 Answer updated!', 'success'); return redirect(url_for('.host_dashboard'))

@host_bp.route('/host/create-round-manual')
@host_required
def create_round_manual_form():
    """Show manual round creation form"""
    return render_template('create_round_manual.html',
                         rounds_config=DEFAULT_ROUNDS_CONFIG,
                         prebuilt_surveys=PREBUILT_SURVEYS,
                         ai_enabled=AI_SCORING_ENABLED,
                         ai_model_choices=AI_MODEL_CHOICES,
                         current_generation_model=get_current_generation_model() if AI_SCORING_ENABLED else '',
                         min_rounds=MIN_ROUNDS,
                         max_rounds=MAX_ROUNDS,
                         min_answers=MIN_ANSWERS,
                         max_answers=MAX_ANSWERS,
                         default_num_rounds=DEFAULT_NUM_ROUNDS,
                         default_answers_per_round=DEFAULT_ANSWERS_PER_ROUND)

@host_bp.route('/host/create-round-manual/submit', methods=['POST'])
@host_required
def create_round_manual_submit():
    """Process manual round creation for all rounds"""
    num_rounds = int(request.form.get('num_rounds', 8) or 8)
    num_rounds = max(MIN_ROUNDS, min(MAX_ROUNDS, num_rounds))
    logger.info(f"[ROUND] create_round_manual_submit() - creating {num_rounds} rounds manually")
    try:
        with db_connect() as conn:
            # Delete any existing rounds and submissions
            conn.execute("DELETE FROM rounds")
            conn.execute("DELETE FROM submissions")

            # Create all rounds dynamically
            for round_num in range(1, num_rounds + 1):
                num_answers = int(request.form.get(f'round_{round_num}_num_answers', 4) or 4)
                num_answers = max(MIN_ANSWERS, min(MAX_ANSWERS, num_answers))

                # Get question for this round
                question = request.form.get(f'question{round_num}', '').strip()

                if not question:
                    flash(f'Question for Round {round_num} cannot be empty.', 'error')
                    return redirect(url_for('.create_round_manual_form'))

                # Build insert for this round
                fields = ['round_number', 'question', 'num_answers', 'is_active']
                is_active = 0
                values = [round_num, question, num_answers, is_active]

                # Get answers and counts for this round
                for i in range(1, num_answers + 1):
                    answer = request.form.get(f'round{round_num}_answer{i}', '').strip()
                    fields.append(f'answer{i}')
                    values.append(answer)

                    count = int(request.form.get(f'round{round_num}_answer{i}_count', 0) or 0)
                    fields.append(f'answer{i}_count')
                    values.append(count)

                answer1 = request.form.get(f'round{round_num}_answer1', '').strip()
                if not answer1:
                    flash(f'Answer #1 for Round {round_num} is required.', 'error')
                    return redirect(url_for('.create_round_manual_form'))

                # Insert this round
                placeholders = ','.join(['?'] * len(values))
                conn.execute(f"INSERT INTO rounds ({','.join(fields)}) VALUES ({placeholders})", values)

            conn.commit()

        logger.info(f"[ROUND] create_round_manual_submit() - all {num_rounds} rounds created successfully")
        flash(f'\u2705 All {num_rounds} rounds created!', 'success'); return redirect(url_for('.host_dashboard'))

    except Exception as e:
        logger.error(f"[ROUND] create_round_manual_submit() error: {e}")
        flash(f'Error creating rounds: {str(e)}', 'error'); return redirect(url_for('.host_dashboard'))

@host_bp.route('/host/generate-questions', methods=['POST'])
@host_required
def generate_questions():
    """Step 1: AI generates survey questions."""
    if not AI_SCORING_ENABLED:
        return jsonify({'success': False, 'error': 'AI is not enabled'}), 400
    try:
        body = request.get_json(silent=True) or {}
        num_rounds = int(body.get('num_rounds', 8))
        num_rounds = max(MIN_ROUNDS, min(MAX_ROUNDS, num_rounds))

        past_questions_block = build_past_questions_block()
        questions_json_example = ', '.join([f'"Question {i}"' for i in range(1, num_rounds + 1)])
        prompt = FEUD_QUESTIONS_PROMPT.format(
            past_questions_block=past_questions_block,
            num_rounds=num_rounds,
            questions_json_example=questions_json_example
        )
        response_text = _call_ai_for_generation(prompt)
        data = _parse_json_response(response_text)
        if not data or 'questions' not in data:
            logger.warning(f"[AI-GEN] Failed to parse questions response: {response_text[:500]}")
            return jsonify({'success': False, 'error': 'Failed to parse AI response'}), 500
        questions = data['questions']
        if len(questions) != num_rounds:
            return jsonify({'success': False, 'error': f'Expected {num_rounds} questions, got {len(questions)}'}), 500
        logger.info(f"[AI-GEN] Generated {num_rounds} questions successfully")
        return jsonify({'success': True, 'questions': questions})
    except Exception as e:
        logger.error(f"[AI-GEN] generate_questions error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@host_bp.route('/host/generate-round-data', methods=['POST'])
@host_required
def generate_round_data():
    """Step 2: AI generates answers + point values for approved questions."""
    if not AI_SCORING_ENABLED:
        return jsonify({'success': False, 'error': 'AI is not enabled'}), 400
    try:
        body = request.get_json()
        if not body or 'questions' not in body:
            return jsonify({'success': False, 'error': 'Must provide questions'}), 400
        questions = body['questions']

        # Build rounds config from request body, validated through build_rounds_config
        submitted_config = body.get('rounds_config', None)
        if submitted_config and len(submitted_config) == len(questions):
            per_round_answers = {}
            for item in submitted_config:
                r = item.get('round') if isinstance(item, dict) else None
                a = item.get('answers') if isinstance(item, dict) else None
                if isinstance(r, int) and isinstance(a, int):
                    per_round_answers[r] = a
            rounds_config = build_rounds_config(len(questions), DEFAULT_ANSWERS_PER_ROUND, per_round_answers)
        else:
            rounds_config = build_rounds_config(len(questions))

        num_rounds = len(rounds_config)
        if len(questions) != num_rounds:
            return jsonify({'success': False, 'error': f'Expected {num_rounds} questions, got {len(questions)}'}), 400

        # Build questions_block with answer counts
        lines = []
        for idx, q in enumerate(questions):
            config = rounds_config[idx]
            answers_count = config.get('answers', 4)
            lines.append(f'{idx + 1}. "{q}" ({answers_count} answers)')
        questions_block = '\n'.join(lines)

        past_questions_block = build_past_questions_block()
        prompt = FEUD_ANSWERS_PROMPT.format(
            questions_block=questions_block,
            past_questions_block=past_questions_block,
            num_rounds=num_rounds,
        )
        response_text = _call_ai_for_generation(prompt)
        data = _parse_json_response(response_text)
        if not data or 'rounds' not in data:
            logger.warning(f"[AI-GEN] Failed to parse round data response: {response_text[:500]}")
            return jsonify({'success': False, 'error': 'Failed to parse AI response'}), 500

        rounds = data['rounds']
        if len(rounds) != num_rounds:
            return jsonify({'success': False, 'error': f'Expected {num_rounds} rounds, got {len(rounds)}'}), 500

        # Validate each round
        for idx, rd in enumerate(rounds):
            config = rounds_config[idx]
            expected_answers = config.get('answers', 4)
            answers = rd.get('answers', [])
            if len(answers) != expected_answers:
                logger.warning(f"[AI-GEN] Round {idx+1}: expected {expected_answers} answers, got {len(answers)}")
            # Validate answer structure
            for ans in answers:
                if 'text' not in ans or 'points' not in ans:
                    return jsonify({'success': False, 'error': f'Round {idx+1}: answers must have "text" and "points"'}), 500
            # Check points sum (target: 93-97, lenient: 85-100)
            total = sum(a['points'] for a in answers)
            if total < 85 or total > 100:
                logger.warning(f"[AI-GEN] Round {idx+1} points sum={total} (outside 85-100 range, but allowing)")

        logger.info(f"[AI-GEN] Generated round data for {num_rounds} rounds successfully")
        set_setting('rounds_source', 'ai', 'How current rounds were created')
        return jsonify({'success': True, 'feud_data': {'rounds': rounds}})
    except Exception as e:
        logger.error(f"[AI-GEN] generate_round_data error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@host_bp.route('/host/regenerate-feud-question', methods=['POST'])
@host_required
def regenerate_feud_question():
    """Regenerate answers for a single question."""
    if not AI_SCORING_ENABLED:
        return jsonify({'success': False, 'error': 'AI is not enabled'}), 400
    try:
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'error': 'Missing request body'}), 400
        question = body.get('question', '').strip()
        num_answers = body.get('num_answers', 4)
        existing_answers = body.get('existing_answers', [])

        if not question:
            return jsonify({'success': False, 'error': 'Question is required'}), 400

        prompt = FEUD_REGEN_QUESTION_PROMPT.format(
            question=question,
            num_answers=num_answers,
            existing_answers=', '.join(existing_answers) if existing_answers else 'None',
        )
        response_text = _call_ai_for_generation(prompt)
        data = _parse_json_response(response_text)
        if not data or 'answers' not in data:
            logger.warning(f"[AI-GEN] Failed to parse regen response: {response_text[:500]}")
            return jsonify({'success': False, 'error': 'Failed to parse AI response'}), 500

        answers = data['answers']
        for ans in answers:
            if 'text' not in ans or 'points' not in ans:
                return jsonify({'success': False, 'error': 'Answers must have "text" and "points"'}), 500

        logger.info(f"[AI-GEN] Regenerated {len(answers)} answers for: {question[:60]}")
        return jsonify({'success': True, 'question': question, 'answers': answers})
    except Exception as e:
        logger.error(f"[AI-GEN] regenerate_feud_question error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@host_bp.route('/host/set-ai-generation-model', methods=['POST'])
@host_required
def set_ai_generation_model():
    """Save the AI model selection for round generation."""
    body = request.get_json()
    if not body or 'model' not in body:
        return jsonify({'success': False, 'error': 'Missing model'}), 400
    model_id = body['model']
    valid_ids = [m['id'] for m in AI_MODEL_CHOICES]
    if model_id not in valid_ids:
        return jsonify({'success': False, 'error': f'Unknown model: {model_id}'}), 400
    set_setting('ai_generation_model', model_id, 'AI model for round generation')
    logger.info(f"[AI-GEN] Generation model set to: {model_id}")
    return jsonify({'success': True})


@host_bp.route('/host/close-round', methods=['POST'])
@host_required
def close_round():
    """Close submissions for the active round and move to scoring"""
    logger.info("[ROUND] close_round() called")
    with db_connect() as conn:
        # Get active round
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()

        if not active_round:
            logger.warning("[ROUND] close_round() - no active round to close")
            flash('\u26a0\ufe0f No active round to close', 'error')
            return redirect(url_for('.host_dashboard'))

        # Mark round as closed
        conn.execute("UPDATE rounds SET submissions_closed = 1 WHERE id = ?", (active_round['id'],))
        conn.commit()
        socketio.emit('round:closed', {'round_id': active_round['id']}, to='teams')
        socketio.emit('round:closed', {'round_id': active_round['id']}, to='hosts')

        # Count submissions
        sub_count = conn.execute("SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ?",
                                (active_round['id'],)).fetchone()['cnt']

        # Check if all submissions are already scored
        unscored_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ? AND host_submitted = 0",
            (active_round['id'],)
        ).fetchone()['cnt']

        logger.info(f"[ROUND] Round {active_round['round_number']} closed - {sub_count} submissions, {unscored_count} unscored")
        flash(f'\ud83d\udd12 Round {active_round["round_number"]} closed! {sub_count} teams submitted.', 'success')

        # If all teams are already scored, skip scoring queue and go straight to scored teams
        if unscored_count == 0 and sub_count > 0:
            logger.info(f"[ROUND] All {sub_count} teams already scored - redirecting to scored_teams")
            return redirect(url_for('scoring.scored_teams'))

        return redirect(url_for('scoring.scoring_queue'))
