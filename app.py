import os
import json
import base64
import sqlite3
import secrets
import string
import time
from datetime import datetime
from difflib import SequenceMatcher
from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash

from config import (
    logger, APP_VERSION, STARTUP_ID, reset_state,
    AI_SCORING_ENABLED,
    time_ago, format_timestamp,
)
from auth import auth_bp, host_required, team_session_valid, configure_session
from database import (
    db_connect,
    ensure_fixed_codes,
    init_db,
    nuke_all_data,
    get_setting,
)
from ai import (
    save_correction_to_history,
    extract_single_scorecard,
    extract_answers_from_photo,
    score_with_ai,
)

from routes.host import host_bp

app = Flask(__name__)
configure_session(app)
app.register_blueprint(auth_bp)
app.register_blueprint(host_bp)

@app.context_processor
def inject_version():
    """Make app version and cache buster available in all templates.

    {{ app_version }} - Display version string (e.g. "v2.0.0 - Fusion")
    {{ cache_bust }}  - Query param for static assets, changes every deploy
                        Usage: href="...?v={{ cache_bust }}"
    """
    return dict(app_version=APP_VERSION, cache_bust=STARTUP_ID)

@app.after_request
def add_cache_headers(response):
    """Prevent browsers from caching HTML pages after deployment.

    Static assets use ?v= query params for cache busting.
    HTML responses get no-cache so phones always get fresh pages on reload.
    """
    if 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

init_db()
nuke_all_data()  # NUKE EVERYTHING on every server start
ensure_fixed_codes()  # Load fixed codes from codes.json

# ============= SCORING ROUTES =============

@app.route('/host/scoring-queue')
@host_required
def scoring_queue():
    """Manual scoring page - single-team-at-a-time view with arrow navigation"""
    logger.debug("[SCORING] scoring_queue() - loading scoring queue")
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()

        if not active_round:
            logger.warning("[SCORING] scoring_queue() - no active round")
            flash('No active round!', 'error'); return redirect(url_for('host.host_dashboard'))

        # Get ALL submissions (unscored first, then scored) for single-team navigation
        submissions = conn.execute("""
            SELECT s.*, tc.team_name
            FROM submissions s
            JOIN team_codes tc ON s.code = tc.code
            WHERE s.round_id = ?
            ORDER BY s.scored ASC, s.submitted_at ASC
        """, (active_round['id'],)).fetchall()

        submissions_data = []
        unscored_count = 0
        for sub in submissions:
            sub_dict = dict(sub)
            sub_dict['time_ago'] = time_ago(sub['submitted_at'])
            sub_dict['submitted_time'] = format_timestamp(sub['submitted_at'])

            if sub_dict['scored']:
                # For scored teams, restore their checked answers
                checked_str = sub_dict.get('checked_answers', '') or ''
                checked_list = [int(x) for x in checked_str.split(',') if x.strip()]
                auto_checks = {i: (i in checked_list) for i in range(1, active_round['num_answers'] + 1)}
            else:
                # Unscored: all boxes unchecked by default
                auto_checks = {i: False for i in range(1, active_round['num_answers'] + 1)}
                unscored_count += 1

            sub_dict['auto_checks'] = auto_checks
            sub_dict['photo_path'] = sub_dict.get('photo_path', None)
            submissions_data.append(sub_dict)
    logger.debug(f"[SCORING] scoring_queue() - {len(submissions_data)} total submissions ({unscored_count} unscored) for round {active_round['round_number']}")
    ai_enabled = AI_SCORING_ENABLED and get_setting('ai_scoring_enabled', 'true') == 'true'
    return render_template('scoring_queue.html',
                         round=dict(active_round),
                         submissions=submissions_data,
                         unscored_count=unscored_count,
                         ai_scoring_enabled=ai_enabled)

@app.route('/host/count-unscored')
@host_required
def count_unscored():
    """API endpoint to get count of unscored submissions"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT id FROM rounds WHERE is_active = 1").fetchone()
        
        if not active_round:
            return jsonify({'count': 0})
        
        count = conn.execute("""
            SELECT COUNT(*) as cnt FROM submissions
            WHERE round_id = ? AND scored = 0
        """, (active_round['id'],)).fetchone()['cnt']
        logger.debug(f"[API] count_unscored() = {count}")
        return jsonify({'count': count})

@app.route('/host/score-team/<int:submission_id>', methods=['POST'])
@host_required
def score_team(submission_id):
    """Submit score for a single team"""
    logger.debug(f"[SCORING] score_team() - submission_id={submission_id}")
    checked_answers = []
    for key in request.form:
        if key.startswith('answer_'):
            checked_answers.append(int(key.split('_')[1]))
    logger.debug(f"[SCORING] Checked answers: {sorted(checked_answers)}")

    with db_connect() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()

        # Get team name
        team_info = conn.execute("SELECT team_name FROM team_codes WHERE code = ?", (submission['code'],)).fetchone()
        team_name = team_info['team_name'] if team_info else 'Unknown Team'
        logger.debug(f"[SCORING] Team: {team_name} (code={submission['code']})")
        
        # Calculate score based on checked boxes
        score = 0
        for ans_num in checked_answers:
            points = round_info['num_answers'] - ans_num + 1
            score += points
        
        # Store which answers were checked (e.g., "1,3,5")
        checked_answers_str = ','.join(map(str, sorted(checked_answers))) if checked_answers else ''
        
        # Store current score as previous_score before updating (for undo functionality)
        current_score = submission['score']
        
        # Update submission with new score and save previous
        logger.debug(f"[SCORING] Score calculated: {score} points (checked: {checked_answers_str}), previous_score: {current_score}")
        logger.info(f"[SCORING] Scored: {team_name} ({submission['code']}) = {score}pts (answers: {checked_answers_str})")

        conn.execute("""
            UPDATE submissions
            SET score = ?, scored = 1, scored_at = CURRENT_TIMESTAMP, checked_answers = ?, previous_score = ?
            WHERE id = ?
        """, (score, checked_answers_str, current_score, submission_id))

        # === AI CORRECTIONS: Detect and store host overrides ===
        ai_matches_str = request.form.get('ai_matches', '').strip()
        ai_reasoning_str = request.form.get('ai_reasoning', '').strip()
        # Per-answer override notes: ai_note_1, ai_note_2, etc.
        ai_notes = {}
        for key, val in request.form.items():
            if key.startswith('ai_note_') and val.strip():
                try:
                    answer_num = int(key.split('_')[2])
                    ai_notes[answer_num] = val.strip()[:200]
                except (ValueError, IndexError):
                    pass

        if ai_matches_str:
            logger.debug(f"[AI-CORRECTIONS] Processing corrections for submission_id={submission_id}")
            ai_matches = set(int(x) for x in ai_matches_str.split(',') if x.strip())
            host_matches = set(checked_answers)

            # Parse AI reasoning for context
            ai_reasoning_list = []
            if ai_reasoning_str:
                try:
                    ai_reasoning_list = json.loads(ai_reasoning_str)
                except Exception:
                    logger.warning("[AI-CORRECTIONS] Failed to parse ai_reasoning JSON")

            host_added = host_matches - ai_matches    # Host checked, AI didn't
            host_removed = ai_matches - host_matches  # AI checked, host unchecked

            logger.debug(f"[AI-CORRECTIONS] AI={sorted(ai_matches)}, Host={sorted(host_matches)}, added={host_added}, removed={host_removed}")

            corrections_count = 0

            for survey_num in host_added:
                survey_answer = round_info[f'answer{survey_num}']
                # Find the team answer from reasoning that relates to this survey answer
                team_answer = None
                ai_reason = None
                for entry in ai_reasoning_list:
                    # Check unmatched entries — AI didn't match them, but host says they match this survey answer
                    if entry.get('matched_to') is None and entry.get('team_answer'):
                        team_answer = entry.get('team_answer', '')
                        ai_reason = entry.get('why', '')
                        break
                if not team_answer:
                    # Fallback: use any team answer from the submission
                    for j in range(1, round_info['num_answers'] + 1):
                        ans = submission[f'answer{j}']
                        if ans and ans.strip():
                            team_answer = ans.strip()
                            break
                if team_answer:
                    host_note = ai_notes.get(survey_num, None)
                    conn.execute("""
                        INSERT INTO ai_corrections (round_id, submission_id, question, team_answer, survey_answer, survey_num, correction_type, ai_reasoning, host_reason)
                        VALUES (?, ?, ?, ?, ?, ?, 'host_added', ?, ?)
                    """, (submission['round_id'], submission_id, round_info['question'], team_answer, survey_answer, survey_num, ai_reason, host_note))
                    save_correction_to_history({
                        'team_answer': team_answer, 'survey_answer': survey_answer,
                        'correction_type': 'host_added', 'ai_reasoning': ai_reason,
                        'host_reason': host_note, 'question': round_info['question']
                    })
                    corrections_count += 1

            for survey_num in host_removed:
                survey_answer = round_info[f'answer{survey_num}']
                # Find the team answer AI matched to this survey answer
                team_answer = None
                ai_reason = None
                for entry in ai_reasoning_list:
                    if entry.get('matched_to') == survey_num:
                        team_answer = entry.get('team_answer', '')
                        ai_reason = entry.get('why', '')
                        break
                if team_answer:
                    host_note = ai_notes.get(survey_num, None)
                    conn.execute("""
                        INSERT INTO ai_corrections (round_id, submission_id, question, team_answer, survey_answer, survey_num, correction_type, ai_reasoning, host_reason)
                        VALUES (?, ?, ?, ?, ?, ?, 'host_removed', ?, ?)
                    """, (submission['round_id'], submission_id, round_info['question'], team_answer, survey_answer, survey_num, ai_reason, host_note))
                    save_correction_to_history({
                        'team_answer': team_answer, 'survey_answer': survey_answer,
                        'correction_type': 'host_removed', 'ai_reasoning': ai_reason,
                        'host_reason': host_note, 'question': round_info['question']
                    })
                    corrections_count += 1

            if corrections_count > 0:
                logger.info(f"[AI-CORRECTIONS] Stored {corrections_count} correction(s) for submission_id={submission_id}")
                if ai_notes:
                    logger.info(f"[AI-CORRECTIONS] Host notes: {ai_notes}")

        conn.commit()

        # Check if all submissions for this round are scored
        total_subs = conn.execute("SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ?", 
                                   (submission['round_id'],)).fetchone()['cnt']
        scored_subs = conn.execute("SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ? AND scored = 1", 
                                    (submission['round_id'],)).fetchone()['cnt']
        
        logger.info(f"[SCORING] Round progress: {scored_subs}/{total_subs} teams scored")

        # If all scored, find winner and update round
        if total_subs > 0 and scored_subs == total_subs:
            logger.info("[SCORING] ALL TEAMS SCORED - determining winner")
            winner = conn.execute("""
                SELECT code, score FROM submissions 
                WHERE round_id = ? 
                ORDER BY score DESC, tiebreaker DESC 
                LIMIT 1
            """, (submission['round_id'],)).fetchone()
            
            if winner:
                conn.execute("UPDATE rounds SET winner_code = ? WHERE id = ?", 
                           (winner['code'], submission['round_id']))
                conn.commit()
                logger.info(f"[SCORING] WINNER: code={winner['code']}, score={winner['score']} for round_id={submission['round_id']}")
    
    # Check if AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return JSON for AJAX
        return jsonify({
            'success': True,
            'score': score,
            'team_name': team_name
        })
    else:
        # Traditional form submit (fallback)
        flash(f'{team_name} scored {score} points!', 'success')
        return redirect(url_for('scoring_queue'))

@app.route('/host/ai-score/<int:submission_id>', methods=['POST'])
@host_required
def ai_score_submission(submission_id):
    """Use Claude AI to suggest scoring for a submission"""
    logger.debug(f"[AI-SCORING] ai_score_submission() - submission_id={submission_id}")

    if not AI_SCORING_ENABLED:
        logger.error("[AI-SCORING] AI scoring not enabled at server level")
        return jsonify({'error': 'AI scoring not enabled'}), 500

    if get_setting('ai_scoring_enabled', 'true') != 'true':
        logger.error("[AI-SCORING] AI scoring disabled in settings")
        return jsonify({'error': 'AI scoring is turned off in settings'}), 500

    try:
        with db_connect() as conn:
            submission = conn.execute(
                "SELECT * FROM submissions WHERE id = ?", (submission_id,)
            ).fetchone()

            if not submission:
                logger.error(f"[AI-SCORING] Submission {submission_id} not found")
                return jsonify({'error': 'Submission not found'}), 404

            round_info = conn.execute(
                "SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)
            ).fetchone()

            if not round_info:
                logger.error(f"[AI-SCORING] Round {submission['round_id']} not found")
                return jsonify({'error': 'Round not found'}), 404

            # Build survey answers list
            survey_answers = []
            for i in range(1, round_info['num_answers'] + 1):
                answer = round_info[f'answer{i}']
                if answer:
                    survey_answers.append({
                        'number': i,
                        'text': answer,
                        'points': round_info['num_answers'] - i + 1
                    })

            # Build team answers list (only non-blank)
            team_answers = []
            for i in range(1, round_info['num_answers'] + 1):
                answer = submission[f'answer{i}']
                if answer and answer.strip():
                    team_answers.append(answer.strip())

            if not team_answers:
                logger.info("[AI-SCORING] No team answers to score")
                return jsonify({'success': True, 'matches': [], 'reasoning': []})

            logger.debug(f"[AI-SCORING] Scoring {len(team_answers)} team answers against {len(survey_answers)} survey answers")

            ai_result = score_with_ai(
                question=round_info['question'],
                survey_answers=survey_answers,
                team_answers=team_answers
            )

            logger.info(f"[AI-SCORING] Result: matches={ai_result['matches']}, reasoning_count={len(ai_result.get('reasoning', []))}")

            return jsonify({
                'success': True,
                'matches': ai_result['matches'],
                'reasoning': ai_result.get('reasoning', [])
            })

    except Exception as e:
        logger.error(f"[AI-SCORING] Error: {e}", exc_info=True)
        return jsonify({'error': f'AI scoring failed: {str(e)}'}), 500

@app.route('/host/undo-score/<int:submission_id>', methods=['POST'])
@host_required
def undo_score(submission_id):
    """Undo the last score for a submission"""
    logger.info(f"[SCORING] undo_score() - submission_id={submission_id}")
    with db_connect() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()

        if not submission:
            logger.warning(f"[SCORING] undo_score() - submission {submission_id} not found")
            return jsonify({"success": False, "message": "Submission not found"}), 404

        if submission['previous_score'] is None:
            logger.warning(f"[SCORING] undo_score() - no previous score for submission {submission_id}")
            return jsonify({"success": False, "message": "No previous score to restore"}), 400
        
        # Get team name
        team_info = conn.execute("SELECT team_name FROM team_codes WHERE code = ?", (submission['code'],)).fetchone()
        team_name = team_info['team_name'] if team_info else 'Unknown Team'
        
        # Restore previous score
        previous_score = submission['previous_score']
        conn.execute("""
            UPDATE submissions 
            SET score = ?, previous_score = NULL
            WHERE id = ?
        """, (previous_score, submission_id))
        conn.commit()
        
        logger.info(f"[SCORING] undo_score() - {team_name} reverted from {submission['score']} to {previous_score}")
        
        return jsonify({
            "success": True,
            "message": f"{team_name}'s score restored to {previous_score}",
            "new_score": previous_score
        })

@app.route('/host/scored-teams')
@host_required
def scored_teams():
    """View all scored teams"""
    logger.debug("[SCORING] scored_teams() - loading scored teams list")
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()

        if not active_round:
            logger.warning("[SCORING] scored_teams() - no active round")
            flash('No active round!', 'error'); return redirect(url_for('host.host_dashboard'))
        
        submissions = conn.execute("""
            SELECT s.*, tc.team_name
            FROM submissions s
            JOIN team_codes tc ON s.code = tc.code
            WHERE s.round_id = ? AND s.scored = 1
            ORDER BY s.score DESC, 
                     ABS(COALESCE(s.tiebreaker, 0) - ?) ASC
        """, (active_round['id'], active_round['answer1_count'] or 0)).fetchall()
        
        # Add formatted timestamps
        submissions_data = []
        for sub in submissions:
            sub_dict = dict(sub)
            sub_dict['submitted_time'] = format_timestamp(sub['submitted_at'])
            submissions_data.append(sub_dict)
    
    logger.debug(f"[SCORING] scored_teams() - {len(submissions_data)} scored teams for round {active_round['round_number']}")
    return render_template('scored_teams.html',
                         round=dict(active_round),
                         submissions=submissions_data)

@app.route('/host/edit-score/<int:submission_id>')
@host_required
def edit_score(submission_id):
    """Edit an already-scored submission"""
    logger.debug(f"[SCORING] edit_score() - loading edit form for submission_id={submission_id}")
    with db_connect() as conn:
        submission = conn.execute("""
            SELECT s.*, tc.team_name
            FROM submissions s
            JOIN team_codes tc ON s.code = tc.code
            WHERE s.id = ?
        """, (submission_id,)).fetchone()
        
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()
        
        # Use stored checked_answers if available
        checked_set = set()
        if submission['checked_answers']:
            # Parse "1,3,5" into set {1, 3, 5}
            checked_set = set(map(int, submission['checked_answers'].split(',')))
        else:
            checked_set = set()  # No auto-matching — start unchecked
        
        # Convert to dict for template
        auto_checks = {i: (i in checked_set) for i in range(1, round_info['num_answers'] + 1)}
    logger.debug(f"[SCORING] edit_score() - team={submission['team_name']}, current_score={submission['score']}, checked={checked_set}")
    return render_template('edit_score.html',
                         round=dict(round_info),
                         submission=dict(submission),
                         auto_checks=auto_checks)

@app.route('/host/update-score/<int:submission_id>', methods=['POST'])
@host_required
def update_score(submission_id):
    """Update score for edited submission"""
    logger.debug(f"[SCORING] update_score() - submission_id={submission_id}")
    checked_answers = []
    for key in request.form:
        if key.startswith('answer_'):
            checked_answers.append(int(key.split('_')[1]))
    
    # Get tiebreaker if provided
    tiebreaker = request.form.get('tiebreaker', type=int)
    
    with db_connect() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()
        
        # Store previous score before updating
        previous_score = submission['score'] if submission['score'] is not None else 0
        
        score = 0
        for ans_num in checked_answers:
            points = round_info['num_answers'] - ans_num + 1
            score += points
        
        # Store which answers were checked
        checked_answers_str = ','.join(map(str, sorted(checked_answers))) if checked_answers else ''
        
        # Update score, tiebreaker, checked_answers, and previous_score
        if tiebreaker is not None:
            conn.execute("UPDATE submissions SET score = ?, tiebreaker = ?, checked_answers = ?, previous_score = ? WHERE id = ?", 
                        (score, tiebreaker, checked_answers_str, previous_score, submission_id))
        else:
            conn.execute("UPDATE submissions SET score = ?, checked_answers = ?, previous_score = ? WHERE id = ?",
                        (score, checked_answers_str, previous_score, submission_id))
        conn.commit()
    logger.info(f"[SCORING] update_score() - old_score={previous_score}, new_score={score}, checked={checked_answers_str}, tiebreaker={tiebreaker}")
    return redirect(url_for('scored_teams'))

@app.route('/host/edit-submission/<int:submission_id>')
@host_required
def edit_submission(submission_id):
    """Edit a team's submitted answers (answer1-6 + tiebreaker) before scoring"""
    logger.info(f"[SCORING] edit_submission() - loading edit form for submission_id={submission_id}")
    with db_connect() as conn:
        submission = conn.execute("""
            SELECT s.*, tc.team_name
            FROM submissions s
            JOIN team_codes tc ON s.code = tc.code
            WHERE s.id = ?
        """, (submission_id,)).fetchone()

        if not submission:
            flash('Submission not found!', 'error')
            return redirect(url_for('scoring_queue'))

        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()

        if not round_info:
            flash('Round not found!', 'error')
            return redirect(url_for('scoring_queue'))

    return render_template('edit_submission.html',
                         round=dict(round_info),
                         submission=dict(submission))

@app.route('/host/update-submission/<int:submission_id>', methods=['POST'])
@host_required
def update_submission(submission_id):
    """Save edited team answers (answer1-6 + tiebreaker)"""
    logger.info(f"[SCORING] update_submission() - submission_id={submission_id}")

    with db_connect() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()

        if not submission:
            flash('Submission not found!', 'error')
            return redirect(url_for('scoring_queue'))

        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()
        num_answers = round_info['num_answers']

        # Collect edited answers
        updates = []
        values = []
        for i in range(1, num_answers + 1):
            answer_val = request.form.get(f'answer{i}', '').strip()
            updates.append(f'answer{i} = ?')
            values.append(answer_val)

        # Collect edited tiebreaker
        tiebreaker = request.form.get('tiebreaker', type=int)
        if tiebreaker is None or tiebreaker < 0 or tiebreaker > 100:
            tiebreaker = 0
        updates.append('tiebreaker = ?')
        values.append(tiebreaker)

        values.append(submission_id)

        conn.execute(
            f"UPDATE submissions SET {', '.join(updates)} WHERE id = ?",
            values
        )
        conn.commit()

    logger.info(f"[SCORING] update_submission() - answers updated for submission_id={submission_id}")

    # Return JSON for AJAX (inline edit) requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        answers = {}
        for i in range(1, num_answers + 1):
            answers[f'answer{i}'] = request.form.get(f'answer{i}', '').strip()
        return jsonify(success=True, answers=answers, tiebreaker=tiebreaker)

    flash('Submission answers updated!', 'success')
    return redirect(url_for('scoring_queue'))

@app.route('/host/revert-score/<int:submission_id>')
@host_required
def revert_score(submission_id):
    """Revert score to previous value"""
    logger.info(f"[SCORING] revert_score() - submission_id={submission_id}")
    with db_connect() as conn:
        submission = conn.execute("SELECT previous_score FROM submissions WHERE id = ?", (submission_id,)).fetchone()

        if submission and submission['previous_score'] is not None:
            logger.info(f"[SCORING] revert_score() - reverting to previous_score={submission['previous_score']}")
            # Swap current and previous scores
            current_previous = submission['previous_score']
            conn.execute("UPDATE submissions SET score = ?, previous_score = score WHERE id = ?", 
                        (current_previous, submission_id))
            conn.commit()
    
    return redirect(url_for('scored_teams'))

@app.route('/host/manual-entry')
@host_required
def manual_entry():
    """Manual entry form for paper submissions"""
    logger.debug("[SCORING] manual_entry() - loading manual entry form")
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()

        if not active_round:
            flash('No active round! Please activate a round first.', 'error')
            return redirect(url_for('host.host_dashboard'))
        
        # Get ALL codes (both used and unused)
        all_codes = conn.execute("""
            SELECT code, team_name, used FROM team_codes 
            ORDER BY code ASC
        """).fetchall()
    
    return render_template('manual_entry.html',
                         round=dict(active_round),
                         codes=all_codes)

@app.route('/host/manual-entry/submit', methods=['POST'])
@host_required
def manual_entry_submit():
    """Process manual paper submission"""
    code = request.form.get('code')
    team_name = request.form.get('team_name', '').strip()
    round_id = request.form.get('round_id')
    tiebreaker = int(request.form.get('tiebreaker', 0) or 0)
    logger.info(f"[SCORING] manual_entry_submit() - code={code}, team_name='{team_name}', round_id={round_id}")
    
    if not code or not team_name:
        # Check if AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Please fill in all required fields!'}), 400
        else:
            flash('Please fill in all required fields!', 'error')
            return redirect(url_for('manual_entry'))
    
    with db_connect() as conn:
        # Mark code as used with team name
        conn.execute("UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?", (team_name, code))
        
        # Get round info
        round_info = conn.execute("SELECT num_answers FROM rounds WHERE id = ?", (round_id,)).fetchone()
        num_answers = round_info['num_answers']
        
        # Collect answers
        answers = {f'answer{i}': request.form.get(f'answer{i}', '').strip() for i in range(1, num_answers + 1)}
        
        # Insert submission
        fields = ['code', 'round_id', 'tiebreaker'] + [f'answer{i}' for i in range(1, num_answers + 1)]
        placeholders = ', '.join(['?'] * len(fields))
        values = [code, round_id, tiebreaker] + [answers[f'answer{i}'] for i in range(1, num_answers + 1)]
        
        try:
            conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
            conn.commit()
            logger.info(f"[SCORING] manual_entry_submit() - submission created for team '{team_name}' (code={code})")
        except sqlite3.IntegrityError:
            logger.warning(f"[SCORING] manual_entry_submit() - duplicate submission for code={code}")
            # Check if AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'This code has already submitted for this round!'}), 400
            else:
                flash('This code has already submitted for this round!', 'error')
                return redirect(url_for('manual_entry'))
    
    # Check if AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return JSON for AJAX
        return jsonify({
            'success': True,
            'team_name': team_name
        })
    else:
        # Traditional form submit (fallback)
        flash('✅ Manual entry submitted successfully!', 'success')
        return redirect(url_for('host.host_dashboard'))

@app.route('/host/photo-scan')
@app.route('/host/scan')
@host_required
def photo_scan():
    """Photo scan page — mobile camera UI for scanning paper answer sheets"""
    logger.debug("[PHOTO-SCAN] photo_scan() - loading photo scan page")

    if not AI_SCORING_ENABLED:
        flash('AI features are required for Photo Scan. Enable AI scoring in Settings.', 'error')
        return redirect(url_for('host.host_dashboard'))

    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()

        if not active_round:
            flash('No active round! Please activate a round first.', 'error')
            return redirect(url_for('host.host_dashboard'))

        # Count registered teams and already-submitted for this round
        total_teams = conn.execute("SELECT COUNT(*) as cnt FROM team_codes WHERE used = 1").fetchone()['cnt']
        submitted_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ?",
            (active_round['id'],)
        ).fetchone()['cnt']

        # Get valid team codes for the code dropdown
        valid_codes = [dict(row) for row in conn.execute(
            "SELECT code, team_name FROM team_codes ORDER BY code"
        ).fetchall()]

    return render_template('photo_scan.html',
                         round=dict(active_round),
                         total_teams=total_teams,
                         submitted_count=submitted_count,
                         valid_codes=valid_codes)


@app.route('/host/photo-scan/upload', methods=['POST'])
@host_required
def photo_scan_upload():
    """Receive photo, extract answers via Claude Vision, insert into submissions"""
    logger.info("[PHOTO-SCAN] photo_scan_upload() - processing image")

    if not AI_SCORING_ENABLED:
        return jsonify({'success': False, 'error': 'AI features not available'}), 503

    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'success': False, 'error': 'No image provided'}), 400

    image_b64 = data['image']
    round_id = data.get('round_id')

    with db_connect() as conn:
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
        if not round_info:
            return jsonify({'success': False, 'error': 'Round not found'}), 404
        num_answers = round_info['num_answers']

        # Get valid codes for matching
        valid_codes = {row['code'].upper(): row['code'] for row in
                       conn.execute("SELECT code FROM team_codes").fetchall()}

        # Save scorecard image to disk
        upload_dir = os.path.join(app.static_folder, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique = secrets.token_hex(4)
        photo_filename = f'scan_{round_id}_{ts}_{unique}.jpg'
        photo_disk_path = os.path.join(upload_dir, photo_filename)
        try:
            with open(photo_disk_path, 'wb') as f:
                f.write(base64.b64decode(image_b64))
            photo_rel_path = f'uploads/{photo_filename}'
            logger.info(f"[PHOTO-SCAN] Saved scorecard image: {photo_rel_path}")
        except Exception as e:
            logger.warning(f"[PHOTO-SCAN] Failed to save image: {e}")
            photo_rel_path = None

        # Extract answers from photo
        try:
            teams = extract_answers_from_photo(image_b64)
        except Exception as e:
            logger.error(f"[PHOTO-SCAN] Extraction failed: {e}")
            return jsonify({'success': False, 'error': 'Failed to read photo. Try again with better lighting.'}), 500

        if not teams:
            return jsonify({'success': False, 'error': 'No teams found in photo. Make sure the answer sheet is clearly visible.'}), 400

        # Insert each team into submissions
        results = []
        for team in teams:
            code_raw = team.get('code', '').strip()
            team_name = team.get('team_name', '').strip()
            tiebreaker = team.get('tiebreaker', 0)
            answers = team.get('answers', [''] * 6)

            # Match code: exact first, fuzzy fallback
            code = valid_codes.get(code_raw.upper(), '')

            if not code and code_raw:
                # Fuzzy fallback — find closest code (3 of 4 letters must match)
                best_ratio = 0
                best_code = ''
                code_upper = code_raw.upper()
                for valid_upper, valid_original in valid_codes.items():
                    ratio = SequenceMatcher(None, code_upper, valid_upper).ratio()
                    if ratio > best_ratio and ratio >= 0.75:
                        best_ratio = ratio
                        best_code = valid_original
                if best_code:
                    code = best_code
                    logger.info(f"[PHOTO-SCAN] Fuzzy code match: '{code_raw}' → {code} (ratio={best_ratio:.2f})")

            if not code:
                results.append({
                    'team_name': team_name or '(blank)',
                    'code': code_raw,
                    'success': False,
                    'error': f'Code "{code_raw}" not found'
                })
                continue

            # Answer sheet is authoritative for team names
            existing = conn.execute("SELECT team_name, used FROM team_codes WHERE code = ?", (code,)).fetchone()
            old_name = existing['team_name'] if existing else None

            if team_name:
                # Sheet has a name — use it (first registration OR rename)
                pending_name_update = team_name
            elif old_name:
                # No name on sheet but code already registered — keep existing name
                team_name = old_name
                pending_name_update = None
                logger.info(f"[PHOTO-SCAN] No name on sheet for code={code}, keeping existing: '{team_name}'")
            else:
                # No name on sheet AND code not registered — assign placeholder
                suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
                team_name = f"NO_NAME_{suffix}"
                pending_name_update = team_name
                logger.info(f"[PHOTO-SCAN] No name on sheet for unregistered code={code}, assigned: '{team_name}'")

            # Build and insert submission (same logic as manual_entry_submit)
            fields = ['code', 'round_id', 'tiebreaker', 'photo_path'] + [f'answer{i}' for i in range(1, num_answers + 1)]
            placeholders = ', '.join(['?'] * len(fields))
            values = [code, round_id, tiebreaker, photo_rel_path] + [answers[i] if i < len(answers) else '' for i in range(num_answers)]

            try:
                conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
                # Only update team name after submission succeeds to avoid
                # corrupting the canonical name on duplicate/failed inserts
                if pending_name_update:
                    if old_name and old_name != pending_name_update:
                        logger.info(f"[PHOTO-SCAN] Team name changed: code={code} '{old_name}' -> '{pending_name_update}'")
                    conn.execute("UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?",
                                (pending_name_update, code))
                result_entry = {
                    'team_name': team_name,
                    'code': code,
                    'success': True
                }
                if old_name and old_name != team_name:
                    result_entry['name_changed_from'] = old_name
                results.append(result_entry)
                logger.info(f"[PHOTO-SCAN] Submitted: team='{team_name}' code={code}")
            except sqlite3.IntegrityError:
                results.append({
                    'team_name': old_name or team_name,
                    'code': code,
                    'success': False,
                    'error': 'Already submitted for this round'
                })
                logger.warning(f"[PHOTO-SCAN] Duplicate: code={code}")

        conn.commit()

    succeeded = sum(1 for r in results if r['success'])
    failed = sum(1 for r in results if not r['success'])
    logger.info(f"[PHOTO-SCAN] Done: {succeeded} succeeded, {failed} failed")

    return jsonify({
        'success': True,
        'results': results,
        'summary': {
            'total': len(results),
            'succeeded': succeeded,
            'failed': failed
        }
    })


@app.route('/host/photo-scan/extract', methods=['POST'])
@host_required
def photo_scan_extract():
    """Extract answers from a single team's scorecard photo — returns data for review, does NOT save to DB"""
    logger.info("[PHOTO-SCAN] photo_scan_extract() - extracting single scorecard")

    if not AI_SCORING_ENABLED:
        return jsonify({'success': False, 'error': 'AI features not available'}), 503

    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'success': False, 'error': 'No image provided'}), 400

    image_b64 = data['image']
    round_id = data.get('round_id')

    with db_connect() as conn:
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
        if not round_info:
            return jsonify({'success': False, 'error': 'Round not found'}), 404
        num_answers = round_info['num_answers']

        # Get valid codes for fuzzy matching
        valid_codes = {row['code'].upper(): row['code'] for row in
                       conn.execute("SELECT code FROM team_codes").fetchall()}

    # Save scorecard image to disk
    upload_dir = os.path.join(app.static_folder, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique = secrets.token_hex(4)
    photo_filename = f'scan_{round_id}_{ts}_{unique}.jpg'
    photo_disk_path = os.path.join(upload_dir, photo_filename)
    try:
        with open(photo_disk_path, 'wb') as f:
            f.write(base64.b64decode(image_b64))
        photo_rel_path = f'uploads/{photo_filename}'
        logger.info(f"[PHOTO-SCAN] Saved scorecard image: {photo_rel_path}")
    except Exception as e:
        logger.warning(f"[PHOTO-SCAN] Failed to save image: {e}")
        photo_rel_path = None

    # Extract answers from photo
    try:
        result = extract_single_scorecard(image_b64)
    except Exception as e:
        logger.error(f"[PHOTO-SCAN] Single extraction failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to read photo. Try again with better lighting.'}), 500

    if not result:
        return jsonify({'success': False, 'error': 'Could not read the scorecard. Make sure the answer sheet is clearly visible.'}), 400

    # Fuzzy-match the code to a valid code
    code_raw = result.get('code', '').strip()
    matched_code = valid_codes.get(code_raw.upper(), '')

    if not matched_code and code_raw:
        best_ratio = 0
        best_code = ''
        code_upper = code_raw.upper()
        for valid_upper, valid_original in valid_codes.items():
            ratio = SequenceMatcher(None, code_upper, valid_upper).ratio()
            if ratio > best_ratio and ratio >= 0.75:
                best_ratio = ratio
                best_code = valid_original
        if best_code:
            matched_code = best_code
            logger.info(f"[PHOTO-SCAN] Fuzzy code match: '{code_raw}' → {matched_code} (ratio={best_ratio:.2f})")
            if 'code' not in result.get('low_confidence_fields', []):
                result.setdefault('low_confidence_fields', []).append('code')

    # Look up existing team name for this code
    existing_team_name = ''
    if matched_code:
        with db_connect() as conn:
            existing = conn.execute("SELECT team_name FROM team_codes WHERE code = ?", (matched_code,)).fetchone()
            if existing and existing['team_name']:
                existing_team_name = existing['team_name']

    return jsonify({
        'success': True,
        'extracted': {
            'code': matched_code or code_raw,
            'code_raw': code_raw,
            'code_matched': bool(matched_code),
            'team_name': result.get('team_name', ''),
            'existing_team_name': existing_team_name,
            'answers': result.get('answers', [''] * 6)[:num_answers],
            'tiebreaker': result.get('tiebreaker', 0),
            'low_confidence_fields': result.get('low_confidence_fields', []),
        },
        'num_answers': num_answers,
        'photo_path': photo_rel_path
    })


@app.route('/host/photo-scan/submit-reviewed', methods=['POST'])
@host_required
def photo_scan_submit_reviewed():
    """Submit host-reviewed/edited answers from single scorecard scan"""
    logger.info("[PHOTO-SCAN] photo_scan_submit_reviewed() - submitting reviewed answers")

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    code = data.get('code', '').strip()
    team_name = data.get('team_name', '').strip()
    answers = data.get('answers', [])
    tiebreaker = data.get('tiebreaker', 0)
    round_id = data.get('round_id')
    photo_path = data.get('photo_path')

    if not code:
        return jsonify({'success': False, 'error': 'Team code is required'}), 400

    try:
        tiebreaker = int(tiebreaker)
    except (ValueError, TypeError):
        tiebreaker = 0

    with db_connect() as conn:
        # Validate round
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
        if not round_info:
            return jsonify({'success': False, 'error': 'Round not found'}), 404
        num_answers = round_info['num_answers']

        # Validate code exists
        code_row = conn.execute("SELECT code, team_name, used FROM team_codes WHERE code = ?", (code,)).fetchone()
        if not code_row:
            return jsonify({'success': False, 'error': f'Code "{code}" not found in system'}), 400

        old_name = code_row['team_name']

        # Determine team name to save
        if team_name:
            pending_name_update = team_name
        elif old_name:
            team_name = old_name
            pending_name_update = None
        else:
            suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
            team_name = f"NO_NAME_{suffix}"
            pending_name_update = team_name

        # Build and insert submission
        fields = ['code', 'round_id', 'tiebreaker', 'photo_path'] + [f'answer{i}' for i in range(1, num_answers + 1)]
        placeholders = ', '.join(['?'] * len(fields))
        values = [code, round_id, tiebreaker, photo_path] + [answers[i] if i < len(answers) else '' for i in range(num_answers)]

        try:
            conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
            if pending_name_update:
                if old_name and old_name != pending_name_update:
                    logger.info(f"[PHOTO-SCAN] Team name changed: code={code} '{old_name}' -> '{pending_name_update}'")
                conn.execute("UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?",
                            (pending_name_update, code))
            conn.commit()
            logger.info(f"[PHOTO-SCAN] Reviewed submission saved: team='{team_name}' code={code}")
            return jsonify({
                'success': True,
                'team_name': team_name,
                'code': code
            })
        except sqlite3.IntegrityError:
            return jsonify({
                'success': False,
                'error': f'Team {code} already submitted for this round'
            }), 409


@app.route('/host/photo-scan/team-count')
@host_required
def photo_scan_team_count():
    """Return count of teams that have submitted for the active round"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT id FROM rounds WHERE is_active = 1").fetchone()
        if not active_round:
            return jsonify({'submitted': 0, 'total': 0})

        submitted = conn.execute(
            "SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ?",
            (active_round['id'],)
        ).fetchone()['cnt']

        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM team_codes WHERE used = 1"
        ).fetchone()['cnt']

    return jsonify({'submitted': submitted, 'total': total})


# ============= TEAM ROUTES =============

@app.route('/join')
def join():
    """Team join page - step 1"""
    paused = get_setting('system_paused', 'false') == 'true'
    reg_closed = get_setting('allow_team_registration', 'true') == 'false'
    logger.debug(f"[TEAM] join() page loaded | paused={paused}, registration_closed={reg_closed}")
    # Check if system is paused
    if paused:
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")

    # Check if team registration is allowed
    if reg_closed:
        return render_template('join.html', error="🚫 Team registration is currently closed.")

    # Support ?code= query param to pre-fill code from QR scan
    prefill_code = request.args.get('code', '').strip().upper()
    return render_template('join.html', prefill_code=prefill_code)

@app.route('/terms')
def terms():
    """Terms and conditions page"""
    return render_template('terms.html')

@app.route('/join/validate-code', methods=['POST'])
def validate_code():
    """Step 1: Validate team code"""
    logger.debug(f"[TEAM] validate_code() - code='{request.form.get('code', '').strip().upper()}'")
    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")
    
    # Check if team registration is allowed
    if get_setting('allow_team_registration', 'true') == 'false':
        return render_template('join.html', error="🚫 Team registration is currently closed.")
    
    code = request.form.get('code', '').strip().upper()
    
    if not code:
        return render_template('join.html', error="Please enter a code")
    
    with db_connect() as conn:
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()
        
        if not code_row:
            logger.warning(f"[TEAM] validate_code() - code '{code}' not found in database")
            return render_template('join.html', error="Invalid code. Check your code and try again.")

        if code_row['used']:
            logger.info(f"[TEAM] validate_code() - code '{code}' already used by '{code_row['team_name']}', showing reconnect form")
            # Code is in use - show reconnection form
            return render_template('join.html', code=code, show_reconnect_form=True, existing_team=code_row['team_name'])

    logger.info(f"[TEAM] validate_code() - code '{code}' is valid and unused, showing team name form")
    return render_template('join.html', code=code, show_team_form=True)

def _rejoin_team(conn, code, code_row, source="REJOIN"):
    """Shared rejoin logic for both join_submit and join_reconnect routes.

    Handles: DB update (reconnected flag, heartbeat), session creation, redirect.
    Called AFTER validation has already confirmed the code is used and team name matches.

    Args:
        conn: Active database connection
        code: Team code (uppercase)
        code_row: Database row for the team code
        source: Log label ("REJOIN" or "RECONNECT") for distinguishing routes in logs

    Returns:
        Flask redirect to team_play
    """
    original_name = code_row['team_name']  # Always use DB capitalization

    logger.debug(f"[TEAM] {source}: Team '{original_name}' rejoining with code {code}")

    # Mark as reconnected + refresh heartbeat
    conn.execute(
        "UPDATE team_codes SET reconnected = 1, last_heartbeat = CURRENT_TIMESTAMP WHERE code = ?",
        (code,)
    )
    conn.commit()

    # Create session with current server state
    session['code'] = code
    session['team_name'] = original_name
    session['startup_id'] = STARTUP_ID
    session['reset_counter'] = reset_state['counter']

    logger.info(f"[TEAM] {source}: Session created for '{original_name}' (Code: {code}), redirecting to team_play")
    return redirect(url_for('team_play'))


@app.route('/join/reconnect', methods=['POST'])
def join_reconnect():
    """Reconnect with existing team code"""
    logger.debug("[TEAM] RECONNECT: Attempt started")

    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        logger.info(f"[TEAM] RECONNECT: Blocked - system paused")
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")

    code = request.form.get('code', '').strip().upper()
    team_name = request.form.get('team_name', '').strip()

    logger.debug(f"[TEAM] RECONNECT: code='{code}', team_name='{team_name}'")

    if not code or not team_name:
        logger.warning(f"[TEAM] RECONNECT: Missing code or team_name")
        return render_template('join.html', error="Please enter both code and team name")

    with db_connect() as conn:
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()

        if not code_row:
            logger.warning(f"[TEAM] RECONNECT: Code '{code}' not found in database")
            return render_template('join.html', error="Invalid code")

        logger.debug(f"[TEAM] RECONNECT: Code found - used={code_row['used']}, team_name='{code_row['team_name']}'")

        if not code_row['used']:
            logger.warning(f"[TEAM] RECONNECT: Code '{code}' not yet used, rejecting reconnect")
            return render_template('join.html', error="This code hasn't been used yet. Use regular join.")

        # Case-insensitive team name comparison
        if code_row['team_name'].lower() != team_name.lower():
            logger.warning(f"[TEAM] RECONNECT: Name mismatch - DB='{code_row['team_name']}', submitted='{team_name}'")
            return render_template('join.html',
                code=code,
                show_reconnect_form=True,
                existing_team=code_row['team_name'],
                error="❌ Team name doesn't match. This code belongs to another team. Get a new code from the host.")

        # Validation passed - use shared rejoin logic
        return _rejoin_team(conn, code, code_row, source="RECONNECT")

@app.route('/join/submit', methods=['POST'])
def join_submit():
    """Step 2: Submit team name"""
    code_val = request.form.get('code', '').strip().upper()
    team_val = request.form.get('team_name', '').strip()
    logger.debug(f"[TEAM] join_submit() - code='{code_val}', team_name='{team_val}'")
    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")
    
    # Check if team registration is allowed
    if get_setting('allow_team_registration', 'true') == 'false':
        return render_template('join.html', error="🚫 Team registration is currently closed.")
    
    code = request.form.get('code', '').strip().upper()
    team_name = request.form.get('team_name', '').strip()
    
    # Validation: Check for empty code or team name
    if not code or not team_name:
        return render_template('join.html', code=code, error="Please enter both code and team name")
    
    # Validation: Check for whitespace-only team name
    if len(team_name.strip()) == 0:
        return render_template('join.html', code=code, error="Team name cannot be empty or just spaces")
    
    # Validation: Team name character limit (30 chars max)
    if len(team_name) > 30:
        return render_template('join.html', code=code, error="Team name too long! Maximum 30 characters.")
    
    with db_connect() as conn:
        # Validation: Check for duplicate team names (case-insensitive)
        existing_team = conn.execute(
            "SELECT team_name FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1 AND code != ?",
            (team_name, code)
        ).fetchone()
        if existing_team:
            logger.warning(f"[TEAM] join_submit() - team name '{team_name}' already taken")
            # Suggest alternative names
            base_name = team_name if len(team_name) <= 27 else team_name[:27]  # Leave room for " 2"
            counter = 2
            suggested_name = f"{base_name} {counter}"
            while conn.execute(
                "SELECT team_name FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1 AND code != ?",
                (suggested_name, code)
            ).fetchone():
                counter += 1
                suggested_name = f"{base_name} {counter}"
            
            return render_template('join.html', code=code, error=f'Team name "{team_name}" already taken! Try: "{suggested_name}"')
        
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()
        
        if not code_row:
            return render_template('join.html', error="Invalid code")
        
        if code_row['used']:
            # Code is already used - check if it's the same team trying to rejoin
            if code_row['team_name'] and code_row['team_name'].lower() == team_name.lower():
                # Same team rejoining - use shared rejoin logic
                return _rejoin_team(conn, code, code_row, source="REJOIN")
            else:
                # Different team trying to use an already-used code
                logger.warning(f"[TEAM] REJOIN BLOCKED: Code {code} used by '{code_row['team_name']}', attempted by '{team_name}'")
                return render_template('join.html', error="Code already used by another team")
        
        # Code is unused - claim it
        conn.execute("UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?", (team_name, code))
        conn.commit()
        logger.info(f"[TEAM] join_submit() - code '{code}' claimed by team '{team_name}', session created")

        # Store current startup_id and reset_counter in session
        # If server restarts or game resets, session becomes invalid
        session['code'] = code
        session['team_name'] = team_name
        session['startup_id'] = STARTUP_ID
        session['reset_counter'] = reset_state['counter']
        
        return redirect(url_for('team_play'))

@app.route('/api/heartbeat', methods=['POST'])
@team_session_valid
def heartbeat():
    """Update last heartbeat timestamp for active tab detection"""
    code = session.get('code')
    logger.debug(f"[API] heartbeat() - code={code}")

    if not code:
        return jsonify({"success": False}), 401
    
    with db_connect() as conn:
        conn.execute("""
            UPDATE team_codes 
            SET last_heartbeat = CURRENT_TIMESTAMP 
            WHERE code = ?
        """, (code,))
        conn.commit()
    
    return jsonify({"success": True})

@app.route('/host/team-status')
@host_required
def get_team_status():
    """Get status of all teams (online/offline) for host dashboard"""
    logger.debug("[API] get_team_status() called")
    with db_connect() as conn:
        teams = conn.execute("""
            SELECT code, team_name, used, last_heartbeat,
                   CASE 
                       WHEN last_heartbeat IS NULL THEN 0
                       WHEN (julianday('now') - julianday(last_heartbeat)) * 86400 <= 15 THEN 1
                       ELSE 0
                   END as is_online
            FROM team_codes
            ORDER BY code
        """).fetchall()
        
        result = []
        for team in teams:
            team_dict = dict(team)
            # Calculate last seen time
            if team['last_heartbeat']:
                from datetime import datetime
                try:
                    last_seen = datetime.fromisoformat(team['last_heartbeat'].replace('Z', '+00:00'))
                    now = datetime.now(last_seen.tzinfo) if last_seen.tzinfo else datetime.now()
                    seconds_ago = int((now - last_seen).total_seconds())
                    
                    if seconds_ago < 60:
                        team_dict['last_seen_text'] = f"{seconds_ago} seconds ago"
                    elif seconds_ago < 3600:
                        minutes = seconds_ago // 60
                        team_dict['last_seen_text'] = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    else:
                        hours = seconds_ago // 3600
                        team_dict['last_seen_text'] = f"{hours} hour{'s' if hours != 1 else ''} ago"
                except:
                    team_dict['last_seen_text'] = "Unknown"
            else:
                team_dict['last_seen_text'] = "Never"
            
            result.append(team_dict)

        online_count = sum(1 for t in result if t.get('is_online'))
        logger.debug(f"[API] get_team_status() -> {len(result)} teams, {online_count} online")
        return jsonify(result)

@app.route('/api/check-round-status')
def check_round_status():
    """API endpoint to check if there's an active round (for AJAX polling)"""
    code = session.get('code')
    logger.debug(f"[API] check_round_status() - code={code}")

    if not code:
        return jsonify({'error': 'No code in session'}), 401
    
    # Check if server was restarted (startup_id mismatch)
    session_startup_id = session.get('startup_id')
    if session_startup_id != STARTUP_ID:
        return jsonify({'error': 'Server restarted', 'reload': True}), 401
    
    # Check if game was reset (reset_counter mismatch)
    session_reset_counter = session.get('reset_counter', 0)
    if session_reset_counter != reset_state['counter']:
        return jsonify({'error': 'Game was reset', 'reload': True}), 401
    
    # Check if server is in sleep mode
    server_sleep = get_setting('server_sleep', 'false')
    if server_sleep == 'true':
        return jsonify({'sleep_mode': True, 'message': 'Server in sleep mode'}), 200
    
    with db_connect() as conn:
        # Check if there's an active round
        active_round = conn.execute("SELECT id, round_number, submissions_closed FROM rounds WHERE is_active = 1").fetchone()
        
        if active_round:
            # Check if this team already submitted for this round
            submission = conn.execute(
                "SELECT id FROM submissions WHERE code = ? AND round_id = ?",
                (code, active_round['id'])
            ).fetchone()

            result = {
                'has_active_round': True,
                'round_id': active_round['id'],
                'round_number': active_round['round_number'],
                'submissions_closed': bool(active_round['submissions_closed']),
                'already_submitted': submission is not None
            }

            # Include previous round's winner (for winner interstitial on round transition)
            prev_round = conn.execute("""
                SELECT r.round_number, r.winner_code, tc.team_name, s.score
                FROM rounds r
                LEFT JOIN team_codes tc ON r.winner_code = tc.code
                LEFT JOIN submissions s ON r.winner_code = s.code AND r.id = s.round_id
                WHERE r.round_number = ? - 1
            """, (active_round['round_number'],)).fetchone()

            if prev_round and prev_round['winner_code']:
                result['prev_winner_team'] = prev_round['team_name']
                result['prev_winner_score'] = prev_round['score']
                result['prev_round_number'] = prev_round['round_number']

            logger.debug(f"[API] check_round_status() -> round={active_round['round_number']}, closed={bool(active_round['submissions_closed'])}, submitted={submission is not None}")
            return jsonify(result)
        else:
            logger.debug("[API] check_round_status() -> no active round")
            return jsonify({
                'has_active_round': False
            })

@app.route('/view/<code>')
def team_view(code):
    """View-only page for manually-entered teams. Auth is the code in the URL."""
    code = code.strip().upper()
    logger.debug(f"[VIEW] team_view() - code={code}")

    with db_connect() as conn:
        team = conn.execute(
            "SELECT code, team_name, used FROM team_codes WHERE code = ?",
            (code,)
        ).fetchone()

        if not team:
            logger.warning(f"[VIEW] team_view() - code not found: {code}")
            return render_template('view.html',
                team_name=f"Code: {code}",
                code=code,
                state='code_not_found',
                round_num=0,
                question='')

        if not team['used'] or not team['team_name']:
            logger.debug(f"[VIEW] team_view() - code exists but not yet registered: {code}")
            return render_template('view.html',
                team_name=f"Code: {code}",
                code=code,
                state='waiting_for_registration',
                round_num=0,
                question='')

        team_name = team['team_name']

        active_round = conn.execute(
            "SELECT * FROM rounds WHERE is_active = 1"
        ).fetchone()

        if not active_round:
            return render_template('view.html',
                team_name=team_name,
                code=code,
                state='waiting_for_round',
                round_num=0,
                question='')

        submission = conn.execute(
            "SELECT * FROM submissions WHERE code = ? AND round_id = ?",
            (code, active_round['id'])
        ).fetchone()

        if not submission:
            return render_template('view.html',
                team_name=team_name,
                code=code,
                state='waiting_for_entry',
                round_num=active_round['round_number'],
                question=active_round['question'])

        if not submission['scored']:
            return render_template('view.html',
                team_name=team_name,
                code=code,
                state='waiting_for_scoring',
                round_num=active_round['round_number'],
                question=active_round['question'],
                num_answers=active_round['num_answers'],
                submission=dict(submission))

        return render_template('view.html',
            team_name=team_name,
            code=code,
            state='scored',
            round_num=active_round['round_number'],
            question=active_round['question'],
            num_answers=active_round['num_answers'],
            submission=dict(submission))

@app.route('/play')
@team_session_valid
def team_play():
    """Team answer submission page"""
    code = session.get('code')
    team_name = session.get('team_name')
    logger.debug(f"[TEAM] team_play() - code={code}, team={team_name}")

    if not code:
        logger.warning("[TEAM] team_play() - no code in session, redirecting to join")
        return redirect(url_for('join'))
    
    with db_connect() as conn:
        # DEFENSIVE: Verify team still exists in database
        team = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()
        
        if not team:
            # Team doesn't exist anymore - session is stale
            logger.error(f"[TEAM] team_play() - team {code} not found in database, clearing session")
            session.clear()
            return redirect(url_for('join'))
        
        # DEFENSIVE: Initialize last_heartbeat if NULL (for rejoining teams)
        if team['last_heartbeat'] is None:
            logger.debug(f"[TEAM] team_play() - initializing heartbeat for team {code} ({team_name})")
            conn.execute(
                "UPDATE team_codes SET last_heartbeat = CURRENT_TIMESTAMP WHERE code = ?",
                (code,)
            )
            conn.commit()
        
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        
        if not active_round:
            logger.debug(f"[TEAM] team_play() - no active round, showing waiting screen")
            return render_template('play.html',
                                 team_name=team_name,
                                 code=code,
                                 no_active_round=True)
        
        submission = conn.execute("""
            SELECT * FROM submissions 
            WHERE code = ? AND round_id = ?
        """, (code, active_round['id'])).fetchone()
        
        if submission:
            logger.debug(f"[TEAM] team_play() - round {active_round['round_number']}, already submitted")
            # Get last_submission from session (for answer preview)
            last_submission = session.pop('last_submission', None)
            
            return render_template('play.html',
                                 team_name=team_name,
                                 code=code,
                                 round_num=active_round['round_number'],
                                 question=active_round['question'],
                                 num_answers=active_round['num_answers'],
                                 already_submitted=True,
                                 submissions_closed=active_round['submissions_closed'],
                                 submission=dict(submission),
                                 last_submission=last_submission)
    
    logger.debug(f"[TEAM] team_play() - round {active_round['round_number']}, showing answer form ({active_round['num_answers']} answers)")
    return render_template('play.html',
                         team_name=team_name,
                         code=code,
                         round_num=active_round['round_number'],
                         question=active_round['question'],
                         num_answers=active_round['num_answers'],
                         round_id=active_round['id'],
                         submissions_closed=active_round['submissions_closed'])

@app.route('/play/submit', methods=['POST'])
@team_session_valid
def submit_answers():
    """Submit team answers"""
    code = session.get('code')
    round_id = request.form.get('round_id')
    logger.info(f"[TEAM] submit_answers() - code={code}, round_id={round_id}")

    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        logger.warning(f"[TEAM] submit_answers() - system paused, rejecting from code={code}")
        flash('⏸️ System is currently paused. Submissions are disabled.', 'error')
        return redirect(url_for('team_play'))

    if not code:
        return redirect(url_for('join'))
    
    # Validation: Tiebreaker must be 0-100
    try:
        tiebreaker = int(request.form.get('tiebreaker', 0) or 0)
        if tiebreaker < 0 or tiebreaker > 100:
            flash('⚠️ Tiebreaker must be between 0 and 100', 'error')
            return redirect(url_for('team_play'))
    except ValueError:
        tiebreaker = 0
    
    with db_connect() as conn:
        # Validate that this is still the active round (prevent stale submissions)
        active_round = conn.execute("SELECT id, submissions_closed FROM rounds WHERE is_active = 1").fetchone()
        if not active_round or str(active_round['id']) != str(round_id):
            logger.warning(f"[TEAM] submit_answers() - stale round_id={round_id}, active={active_round['id'] if active_round else 'None'}")
            # Round has changed - redirect to play page to get current round
            return redirect(url_for('team_play'))

        # Check if round is closed
        if active_round['submissions_closed']:
            logger.warning(f"[TEAM] submit_answers() - round closed, rejecting submission from code={code}")
            flash('⏰ Round has ended. Submissions are closed.', 'error')
            return redirect(url_for('team_play'))
        
        # CRITICAL FIX: Check for duplicate submission BEFORE attempting insert
        existing_submission = conn.execute(
            "SELECT id FROM submissions WHERE code = ? AND round_id = ?",
            (code, round_id)
        ).fetchone()
        
        if existing_submission:
            logger.warning(f"[TEAM] submit_answers() - duplicate submission from code={code} for round_id={round_id}")
            flash('✅ You have already submitted for this round!', 'warning')
            return redirect(url_for('team_play'))
        
        round_info = conn.execute("SELECT num_answers FROM rounds WHERE id = ?", (round_id,)).fetchone()
        num_answers = round_info['num_answers']
        
        answers = {f'answer{i}': request.form.get(f'answer{i}', '').strip() for i in range(1, num_answers + 1)}
        
        try:
            fields = ['code', 'round_id', 'tiebreaker'] + [f'answer{i}' for i in range(1, num_answers + 1)]
            placeholders = ', '.join(['?'] * len(fields))
            values = [code, round_id, tiebreaker] + [answers[f'answer{i}'] for i in range(1, num_answers + 1)]
            
            conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
            conn.commit()
            logger.info(f"[TEAM] submit_answers() - submission saved for code={code}, round_id={round_id}, tiebreaker={tiebreaker}, answers={answers}")

            # Store submission for answer preview
            session['last_submission'] = {
                'round_id': round_id,
                'answers': answers,
                'tiebreaker': tiebreaker
            }
        except sqlite3.IntegrityError:
            # Fallback: UNIQUE constraint caught it
            logger.warning(f"[TEAM] submit_answers() - UNIQUE constraint caught duplicate from code={code}")
            flash('✅ You have already submitted for this round!', 'warning')
    
    return redirect(url_for('team_play'))

@app.route('/api/broadcast-message')
def api_broadcast_message():
    """API endpoint for teams to get current broadcast message"""
    logger.debug("[API] api_broadcast_message() called")
    import json
    
    broadcast_json = get_setting('broadcast_message', '')
    
    # Handle legacy format (plain string) or new format (JSON)
    try:
        if broadcast_json:
            broadcast_data = json.loads(broadcast_json)
            return jsonify({
                'message': broadcast_data.get('message', ''),
                'timestamp': broadcast_data.get('timestamp', 0)
            })
        else:
            return jsonify({'message': '', 'timestamp': 0})
    except (json.JSONDecodeError, TypeError):
        # Legacy format - just a plain string
        return jsonify({'message': broadcast_json, 'timestamp': 0})

@app.route('/api/view-status/<code>')
def api_view_status(code):
    """API endpoint for view-only page polling. Returns round + scoring state."""
    code = code.strip().upper()
    logger.debug(f"[API] api_view_status() - code={code}")

    server_sleep = get_setting('server_sleep', 'false')
    if server_sleep == 'true':
        return jsonify({'sleep_mode': True}), 200

    with db_connect() as conn:
        team = conn.execute(
            "SELECT code, team_name, used FROM team_codes WHERE code = ?",
            (code,)
        ).fetchone()

        if not team:
            return jsonify({'state': 'code_not_found', 'has_active_round': False})

        if not team['used'] or not team['team_name']:
            return jsonify({'state': 'waiting_for_registration', 'has_active_round': False})

        active_round = conn.execute(
            "SELECT * FROM rounds WHERE is_active = 1"
        ).fetchone()

        if not active_round:
            result = {
                'has_active_round': False,
                'state': 'waiting_for_round'
            }

            last_round = conn.execute("""
                SELECT r.round_number, r.winner_code, tc.team_name, s.score
                FROM rounds r
                LEFT JOIN team_codes tc ON r.winner_code = tc.code
                LEFT JOIN submissions s ON r.winner_code = s.code AND r.id = s.round_id
                ORDER BY r.round_number DESC LIMIT 1
            """).fetchone()

            if last_round and last_round['winner_code']:
                result['prev_winner_team'] = last_round['team_name']
                result['prev_winner_score'] = last_round['score']
                result['prev_round_number'] = last_round['round_number']

            return jsonify(result)

        submission = conn.execute(
            "SELECT * FROM submissions WHERE code = ? AND round_id = ?",
            (code, active_round['id'])
        ).fetchone()

        result = {
            'has_active_round': True,
            'round_id': active_round['id'],
            'round_number': active_round['round_number'],
            'question': active_round['question'],
            'num_answers': active_round['num_answers'],
            'submissions_closed': bool(active_round['submissions_closed'])
        }

        if not submission:
            result['state'] = 'waiting_for_entry'
        elif not submission['scored']:
            result['state'] = 'waiting_for_scoring'
            result['answers'] = {
                f'answer{i}': submission[f'answer{i}']
                for i in range(1, active_round['num_answers'] + 1)
            }
            result['tiebreaker'] = submission['tiebreaker']
        else:
            # Players only see their submitted answers - no scoring data
            result['state'] = 'scored'
            result['answers'] = {
                f'answer{i}': submission[f'answer{i}']
                for i in range(1, active_round['num_answers'] + 1)
            }
            result['tiebreaker'] = submission['tiebreaker']

        prev_round = conn.execute("""
            SELECT r.round_number, r.winner_code, tc.team_name, s.score
            FROM rounds r
            LEFT JOIN team_codes tc ON r.winner_code = tc.code
            LEFT JOIN submissions s ON r.winner_code = s.code AND r.id = s.round_id
            WHERE r.round_number = ? - 1
        """, (active_round['round_number'],)).fetchone()

        if prev_round and prev_round['winner_code']:
            result['prev_winner_team'] = prev_round['team_name']
            result['prev_winner_score'] = prev_round['score']
            result['prev_round_number'] = prev_round['round_number']

        return jsonify(result)

if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("\n" + "="*60)
    print("🎮 FAMILY FEUD - PRODUCTION SERVER")
    print("="*60)
    print(f"\n📱 Team Join: http://{local_ip}:5000/join")
    print(f"🖥️  Host Dashboard: http://localhost:5000/host")
    print(f"🏆 Scoring Queue: http://localhost:5000/host/scoring-queue")
    print(f"\n💡 Upload answer sheet, generate codes, start playing!")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
