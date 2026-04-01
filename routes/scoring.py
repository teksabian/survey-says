"""
Scoring and photo scan routes for Family Feud.

Owns: Scoring queue, manual/AI scoring, score editing, undo/revert,
scored teams list, manual entry, and photo scan (capture + review).
"""

import os
import json
import base64
import sqlite3
import secrets
import string
import threading
from datetime import datetime
from difflib import SequenceMatcher
from flask import Blueprint, request, render_template, redirect, url_for, jsonify, session, flash, current_app

from config import logger, AI_SCORING_ENABLED, time_ago, format_timestamp
from auth import host_required
from database import db_connect, get_setting, set_setting
from extensions import socketio
from ai import save_correction_to_history, extract_single_scorecard, extract_answers_from_photo, score_with_ai

scoring_bp = Blueprint('scoring', __name__)


def emit_leaderboard_update():
    """Emit cumulative leaderboard to all team screens. No answer data exposed."""
    from tv_state import tv_state as _tv_state
    try:
        with db_connect() as conn:
            active_round = conn.execute("SELECT id FROM rounds WHERE is_active = 1").fetchone()
            active_round_id = active_round['id'] if active_round else -1

            teams = conn.execute("""
                SELECT tc.team_name, tc.code,
                       COALESCE(SUM(CASE WHEN s.host_submitted = 1 THEN s.score ELSE 0 END), 0) as total_score,
                       MAX(CASE WHEN s.round_id = ? AND s.host_submitted = 1 THEN 1 ELSE 0 END) as current_round_scored,
                       MAX(CASE WHEN s.host_submitted = 1 THEN 1 ELSE 0 END) as has_been_scored
                FROM team_codes tc
                LEFT JOIN submissions s ON tc.code = s.code
                WHERE tc.used = 1 AND tc.team_name IS NOT NULL
                GROUP BY tc.code
                ORDER BY total_score DESC, tc.team_name ASC
            """, (active_round_id,)).fetchall()

            leaderboard = []
            for i, row in enumerate(teams):
                leaderboard.append({
                    'team_name': row['team_name'],
                    'code': row['code'],
                    'total_score': row['total_score'],
                    'rank': i + 1,
                    'pending': bool(
                        (active_round and not row['current_round_scored']) or
                        (not active_round and not row['has_been_scored'])
                    )
                })

            socketio.emit('leaderboard:update', {
                'leaderboard': leaderboard,
                'scores_revealed': _tv_state.get('scores_revealed', False),
            }, to='teams')
    except Exception as e:
        logger.error(f"[LEADERBOARD] Error emitting update: {e}")


def run_ai_scoring_for_submission(submission_id, auto_accept=False):
    """Shared helper: run AI scoring for a submission and persist results to DB.

    Used by both the manual AI scoring endpoint and background auto-scoring.
    When auto_accept=True, also calculates and applies the final score automatically.
    Returns the AI result dict {'matches': [...], 'reasoning': [...]} or None on error.
    """
    try:
        with db_connect() as conn:
            submission = conn.execute(
                "SELECT * FROM submissions WHERE id = ?", (submission_id,)
            ).fetchone()

            if not submission:
                logger.error(f"[AI-SCORING] Submission {submission_id} not found")
                return None

            round_info = conn.execute(
                "SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)
            ).fetchone()

            if not round_info:
                logger.error(f"[AI-SCORING] Round {submission['round_id']} not found")
                return None

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
                logger.info(f"[AI-SCORING] No team answers to score for submission {submission_id}")
                return {'matches': [], 'reasoning': []}

            logger.debug(f"[AI-SCORING] Scoring {len(team_answers)} team answers against {len(survey_answers)} survey answers")

            ai_result = score_with_ai(
                question=round_info['question'],
                survey_answers=survey_answers,
                team_answers=team_answers
            )

            matches = ai_result.get('matches', [])
            reasoning = ai_result.get('reasoning', [])

            # Derive matches from reasoning for consistency
            derived_matches = set()
            for entry in reasoning:
                if entry.get('matched_to') is not None:
                    derived_matches.add(entry['matched_to'])

            # Persist AI results to DB
            conn.execute(
                "UPDATE submissions SET ai_matches = ?, ai_reasoning = ? WHERE id = ?",
                (','.join(str(m) for m in sorted(derived_matches)), json.dumps(reasoning), submission_id)
            )

            # Auto-accept: calculate and apply score from AI matches (including zero-match case)
            if auto_accept:
                num_answers = round_info['num_answers']
                score = sum(num_answers - ans_num + 1 for ans_num in derived_matches) if derived_matches else 0
                checked_str = ','.join(str(m) for m in sorted(derived_matches)) if derived_matches else ''
                current_score = submission['score']
                conn.execute("""
                    UPDATE submissions
                    SET score = ?, scored = 1, host_submitted = 1, scored_at = CURRENT_TIMESTAMP,
                        checked_answers = ?, previous_score = ?
                    WHERE id = ?
                """, (score, checked_str, current_score, submission_id))

                team_info = conn.execute("SELECT team_name FROM team_codes WHERE code = ?", (submission['code'],)).fetchone()
                team_name = team_info['team_name'] if team_info else 'Unknown'
                logger.info(f"[AUTO-AI] Auto-accepted score for {team_name} ({submission['code']}): {score}pts (matches: {checked_str})")

                socketio.emit('scoring:submission_scored', {
                    'submission_id': submission_id,
                    'code': submission['code'],
                    'score': score,
                    'ai_reasoning': reasoning,
                    'auto_accepted': True
                }, to='hosts')
                socketio.emit('scoring:your_results', {
                    'checked_answers': checked_str,
                    'score': score,
                }, to=f'team:{submission["code"]}')
                emit_leaderboard_update()

            conn.commit()

            unscored = conn.execute("SELECT COUNT(*) FROM submissions WHERE host_submitted = 0").fetchone()[0]
            socketio.emit('scoring:count', {'unscored_count': unscored}, to='hosts')

            logger.info(f"[AI-SCORING] Result for submission {submission_id}: matches={matches}, reasoning_count={len(reasoning)}")
            return ai_result

    except Exception as e:
        logger.error(f"[AI-SCORING] Error scoring submission {submission_id}: {e}", exc_info=True)
        return None


# ============= SCORING ROUTES =============

@scoring_bp.route('/host/scoring-queue')
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
            ORDER BY s.host_submitted ASC, s.submitted_at ASC
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
                # Unscored: pre-populate from AI results if available, else all unchecked
                ai_matches_str = sub_dict.get('ai_matches', '') or ''
                if ai_matches_str:
                    ai_match_list = [int(x) for x in ai_matches_str.split(',') if x.strip()]
                    auto_checks = {i: (i in ai_match_list) for i in range(1, active_round['num_answers'] + 1)}
                else:
                    auto_checks = {i: False for i in range(1, active_round['num_answers'] + 1)}

            if not sub_dict.get('host_submitted'):
                unscored_count += 1

            sub_dict['auto_checks'] = auto_checks
            sub_dict['photo_path'] = sub_dict.get('photo_path', None)
            submissions_data.append(sub_dict)
    logger.debug(f"[SCORING] scoring_queue() - {len(submissions_data)} total submissions ({unscored_count} unscored) for round {active_round['round_number']}")
    ai_enabled = AI_SCORING_ENABLED and get_setting('ai_scoring_enabled', 'true') == 'true'
    auto_ai_scoring = ai_enabled and get_setting('auto_ai_scoring', 'false') == 'true'
    return render_template('scoring_queue.html',
                         round=dict(active_round),
                         submissions=submissions_data,
                         unscored_count=unscored_count,
                         ai_scoring_enabled=ai_enabled,
                         auto_ai_scoring=auto_ai_scoring)

@scoring_bp.route('/host/count-unscored')
@host_required
def count_unscored():
    """API endpoint to get count of unscored submissions"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT id FROM rounds WHERE is_active = 1").fetchone()

        if not active_round:
            return jsonify({'count': 0})

        count = conn.execute("""
            SELECT COUNT(*) as cnt FROM submissions
            WHERE round_id = ? AND host_submitted = 0
        """, (active_round['id'],)).fetchone()['cnt']
        logger.debug(f"[API] count_unscored() = {count}")
        return jsonify({'count': count})

@scoring_bp.route('/host/toggle-auto-ai-scoring', methods=['POST'])
@host_required
def toggle_auto_ai_scoring():
    """AJAX endpoint: toggle the auto_ai_scoring setting, return new state as JSON"""
    current_value = get_setting('auto_ai_scoring', 'false')
    new_value = 'false' if current_value == 'true' else 'true'
    set_setting('auto_ai_scoring', new_value, 'Auto AI score new submissions on the scoring queue')
    logger.info(f"[SETTINGS] toggle_auto_ai_scoring: '{current_value}' -> '{new_value}'")
    return jsonify({'success': True, 'auto_ai_scoring': new_value == 'true'})

@scoring_bp.route('/host/score-team/<int:submission_id>', methods=['POST'])
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
            SET score = ?, scored = 1, host_submitted = 1, scored_at = CURRENT_TIMESTAMP, checked_answers = ?, previous_score = ?
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

            # Build pool of unmatched team answers from AI reasoning (preserve order)
            unmatched_pool = []
            for entry in ai_reasoning_list:
                if entry.get('matched_to') is None and entry.get('team_answer'):
                    unmatched_pool.append({
                        'team_answer': entry.get('team_answer', ''),
                        'why': entry.get('why', ''),
                        'claimed': False
                    })

            for survey_num in host_added:
                survey_answer = round_info[f'answer{survey_num}']
                team_answer = None
                ai_reason = None

                # Strategy 1: Find an unmatched team answer that resembles this survey answer
                survey_words = set(survey_answer.lower().split())
                best_candidate = None
                for candidate in unmatched_pool:
                    if candidate['claimed']:
                        continue
                    team_lower = candidate['team_answer'].lower()
                    team_words = set(team_lower.split())
                    if (survey_answer.lower() in team_lower
                            or team_lower in survey_answer.lower()
                            or survey_words & team_words):
                        best_candidate = candidate
                        break

                # Strategy 2: Fall back to first unclaimed unmatched entry
                if not best_candidate:
                    for candidate in unmatched_pool:
                        if not candidate['claimed']:
                            best_candidate = candidate
                            break

                if best_candidate:
                    best_candidate['claimed'] = True
                    team_answer = best_candidate['team_answer']
                    ai_reason = best_candidate['why']

                # Strategy 3: Last resort fallback to raw submission data
                if not team_answer:
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

        unscored = conn.execute("SELECT COUNT(*) FROM submissions WHERE host_submitted = 0").fetchone()[0]
        socketio.emit('scoring:count', {'unscored_count': unscored}, to='hosts')
        socketio.emit('scoring:submission_scored', {
            'submission_id': submission_id,
            'code': submission['code'],
            'score': score
        }, to='hosts')
        socketio.emit('scoring:your_results', {
            'checked_answers': checked_answers_str,
            'score': score,
        }, to=f'team:{submission["code"]}')
        emit_leaderboard_update()

        # Check if all submissions for this round are scored
        total_subs = conn.execute("SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ?",
                                   (submission['round_id'],)).fetchone()['cnt']
        scored_subs = conn.execute("SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ? AND host_submitted = 1",
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

                winner_team = conn.execute(
                    "SELECT team_name FROM team_codes WHERE code = ?",
                    (winner['code'],)
                ).fetchone()
                winner_name = winner_team['team_name'] if winner_team else 'Unknown'

                # Notify hosts only — teams see the winner when host clicks "Start Next Round"
                socketio.emit('scoring:all_complete', {
                    'round_id': submission['round_id'],
                    'winner_code': winner['code'],
                    'winner_team': winner_name,
                    'winner_score': winner['score']
                }, to='hosts')

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
        return redirect(url_for('scoring.scoring_queue'))

@scoring_bp.route('/host/ai-score/<int:submission_id>', methods=['POST'])
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

    ai_result = run_ai_scoring_for_submission(submission_id)
    if ai_result is None:
        return jsonify({'error': 'AI scoring failed'}), 500

    return jsonify({
        'success': True,
        'matches': ai_result.get('matches', []),
        'reasoning': ai_result.get('reasoning', [])
    })

@scoring_bp.route('/host/undo-score/<int:submission_id>', methods=['POST'])
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
            SET score = ?, previous_score = NULL, host_submitted = 0
            WHERE id = ?
        """, (previous_score, submission_id))
        conn.commit()

        logger.info(f"[SCORING] undo_score() - {team_name} reverted from {submission['score']} to {previous_score}")
        emit_leaderboard_update()

        return jsonify({
            "success": True,
            "message": f"{team_name}'s score restored to {previous_score}",
            "new_score": previous_score
        })

@scoring_bp.route('/host/scored-teams')
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
    from routes.host.codes import get_qr_base_url
    return render_template('scored_teams.html',
                         round=dict(active_round),
                         submissions=submissions_data,
                         tv_board_enabled=(get_setting('tv_board_enabled', 'true') == 'true'),
                         qr_base_url=get_qr_base_url(),
                         scan_token=get_setting('scan_token', ''))

@scoring_bp.route('/host/ai-accepted-summary')
@host_required
def ai_accepted_summary():
    """Return AI-accepted variant answers grouped by survey answer slot for the active round."""
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        if not active_round:
            return jsonify({"success": False, "message": "No active round"})

        submissions = conn.execute(
            "SELECT ai_reasoning FROM submissions WHERE round_id = ? AND scored = 1 AND ai_reasoning IS NOT NULL",
            (active_round['id'],)
        ).fetchall()

        if not submissions:
            return jsonify({"success": True, "answers": []})

        # Build canonical answer lookup from round
        num_answers = active_round['num_answers'] or 0
        canonical = {}
        for i in range(1, num_answers + 1):
            text = active_round[f'answer{i}']
            if text:
                canonical[i] = text

        # Collect unique variant answers per survey answer slot
        variants_by_num = {i: set() for i in canonical}
        for sub in submissions:
            try:
                reasoning = json.loads(sub['ai_reasoning'])
            except (json.JSONDecodeError, TypeError):
                continue
            for entry in reasoning:
                matched_to = entry.get('matched_to')
                team_answer = entry.get('team_answer', '').strip()
                if matched_to is not None and matched_to in canonical and team_answer:
                    # Filter out misspellings/typos — only keep true synonyms/fringe answers
                    team_lower = team_answer.lower().replace(' ', '')
                    canon_lower = canonical[matched_to].lower().replace(' ', '')

                    # Check 1: sequential similarity (catches close misspellings)
                    if SequenceMatcher(None, team_lower, canon_lower).ratio() > 0.6:
                        continue
                    # Check 2: character composition (catches anagrams like "tottao"→"tattoo")
                    if SequenceMatcher(None, sorted(team_lower), sorted(canon_lower)).ratio() > 0.85:
                        continue
                    # Check 3: one contains the other (e.g., "cars"→"car")
                    if team_lower in canon_lower or canon_lower in team_lower:
                        continue

                    variants_by_num[matched_to].add(team_answer)

        answers = []
        for num in sorted(canonical):
            answers.append({
                "number": num,
                "canonical": canonical[num],
                "variants": sorted(variants_by_num.get(num, []), key=str.lower)
            })

        return jsonify({"success": True, "answers": answers})

@scoring_bp.route('/host/edit-score/<int:submission_id>')
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

@scoring_bp.route('/host/update-score/<int:submission_id>', methods=['POST'])
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
    emit_leaderboard_update()
    return redirect(url_for('scoring.scored_teams'))

@scoring_bp.route('/host/edit-submission/<int:submission_id>')
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
            return redirect(url_for('scoring.scoring_queue'))

        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()

        if not round_info:
            flash('Round not found!', 'error')
            return redirect(url_for('scoring.scoring_queue'))

    return render_template('edit_submission.html',
                         round=dict(round_info),
                         submission=dict(submission))

@scoring_bp.route('/host/update-submission/<int:submission_id>', methods=['POST'])
@host_required
def update_submission(submission_id):
    """Save edited team answers (answer1-6 + tiebreaker)"""
    logger.info(f"[SCORING] update_submission() - submission_id={submission_id}")

    with db_connect() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()

        if not submission:
            flash('Submission not found!', 'error')
            return redirect(url_for('scoring.scoring_queue'))

        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()
        num_answers = round_info['num_answers']

        # Collect edited answers
        updates = []
        values = []
        for i in range(1, num_answers + 1):
            answer_val = request.form.get(f'answer{i}', '').strip()
            updates.append(f'answer{i} = ?')
            values.append(answer_val)

        if not any(values):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Please provide at least one answer.'}), 400
            flash('Please provide at least one answer.', 'error')
            return redirect(url_for('scoring.scoring_queue'))

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
    return redirect(url_for('scoring.scoring_queue'))

@scoring_bp.route('/host/revert-score/<int:submission_id>')
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
            emit_leaderboard_update()

    return redirect(url_for('scoring.scored_teams'))

@scoring_bp.route('/host/manual-entry')
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

    from routes.host.codes import get_qr_base_url
    qr_base_url = get_qr_base_url()
    scan_token = get_setting('scan_token')

    return render_template('manual_entry.html',
                         round=dict(active_round),
                         codes=all_codes,
                         qr_base_url=qr_base_url,
                         scan_token=scan_token)

@scoring_bp.route('/host/manual-entry/submit', methods=['POST'])
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
            return redirect(url_for('scoring.manual_entry'))

    with db_connect() as conn:
        # Mark code as used with team name
        conn.execute("UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?", (team_name, code))

        # Get round info
        round_info = conn.execute("SELECT num_answers FROM rounds WHERE id = ?", (round_id,)).fetchone()
        num_answers = round_info['num_answers']

        # Collect answers
        answers = {f'answer{i}': request.form.get(f'answer{i}', '').strip() for i in range(1, num_answers + 1)}

        if not any(answers.values()):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Please provide at least one answer.'}), 400
            flash('Please provide at least one answer.', 'error')
            return redirect(url_for('scoring.manual_entry'))

        # Insert submission
        fields = ['code', 'round_id', 'tiebreaker'] + [f'answer{i}' for i in range(1, num_answers + 1)]
        placeholders = ', '.join(['?'] * len(fields))
        values = [code, round_id, tiebreaker] + [answers[f'answer{i}'] for i in range(1, num_answers + 1)]

        try:
            conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
            conn.commit()

            unscored = conn.execute("SELECT COUNT(*) FROM submissions WHERE host_submitted = 0").fetchone()[0]
            socketio.emit('scoring:count', {'unscored_count': unscored}, to='hosts')
            socketio.emit('team:joined', {'code': code, 'team_name': team_name}, to='hosts')
            codes = conn.execute("SELECT code, used, team_name FROM team_codes ORDER BY id ASC").fetchall()
            codes_data = [{'code': c['code'], 'used': bool(c['used']), 'team_name': c['team_name']} for c in codes]
            socketio.emit('codes:updated', {'codes': codes_data}, to='hosts')

            logger.info(f"[SCORING] manual_entry_submit() - submission created for team '{team_name}' (code={code})")
        except sqlite3.IntegrityError:
            logger.warning(f"[SCORING] manual_entry_submit() - duplicate submission for code={code}")
            # Check if AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'This code has already submitted for this round!'}), 400
            else:
                flash('This code has already submitted for this round!', 'error')
                return redirect(url_for('scoring.manual_entry'))

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

@scoring_bp.route('/host/photo-scan')
@scoring_bp.route('/host/scan')
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
            logger.debug("[PHOTO-SCAN] photo_scan() - no active round, showing waiting screen")
            return render_template('photo_scan.html',
                                 no_active_round=True,
                                 round=None,
                                 total_teams=0,
                                 submitted_count=0,
                                 valid_codes=[])

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
                         no_active_round=False,
                         round=dict(active_round),
                         total_teams=total_teams,
                         submitted_count=submitted_count,
                         valid_codes=valid_codes)


@scoring_bp.route('/host/photo-scan/upload', methods=['POST'])
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
        upload_dir = os.path.join(current_app.static_folder, 'uploads')
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

        unscored = conn.execute("SELECT COUNT(*) FROM submissions WHERE host_submitted = 0").fetchone()[0]
        socketio.emit('scoring:count', {'unscored_count': unscored}, to='hosts')

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


@scoring_bp.route('/host/photo-scan/extract', methods=['POST'])
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
    upload_dir = os.path.join(current_app.static_folder, 'uploads')
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


@scoring_bp.route('/host/photo-scan/submit-reviewed', methods=['POST'])
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

        if not any(a.strip() for a in answers if isinstance(a, str)):
            return jsonify({'success': False, 'error': 'Please provide at least one answer.'}), 400

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
            # Always mark code as used when scanned
            conn.execute("UPDATE team_codes SET used = 1 WHERE code = ?", (code,))
            if pending_name_update:
                if old_name and old_name != pending_name_update:
                    logger.info(f"[PHOTO-SCAN] Team name changed: code={code} '{old_name}' -> '{pending_name_update}'")
                conn.execute("UPDATE team_codes SET team_name = ? WHERE code = ?",
                            (pending_name_update, code))
            conn.commit()

            unscored = conn.execute("SELECT COUNT(*) FROM submissions WHERE host_submitted = 0").fetchone()[0]
            socketio.emit('scoring:count', {'unscored_count': unscored}, to='hosts')
            codes = conn.execute("SELECT code, used, team_name FROM team_codes ORDER BY id ASC").fetchall()
            codes_data = [{'code': c['code'], 'used': bool(c['used']), 'team_name': c['team_name']} for c in codes]
            socketio.emit('codes:updated', {'codes': codes_data}, to='hosts')

            logger.info(f"[PHOTO-SCAN] Reviewed submission saved: team='{team_name}' code={code}")

            # Auto AI Scoring: trigger in background if enabled
            if AI_SCORING_ENABLED and get_setting('ai_scoring_enabled', 'true') == 'true' and get_setting('auto_ai_scoring', 'false') == 'true':
                sub_row = conn.execute(
                    "SELECT id FROM submissions WHERE code = ? AND round_id = ?",
                    (code, round_id)
                ).fetchone()
                if sub_row:
                    sub_id = sub_row['id']
                    logger.info(f"[AUTO-AI] Triggering background AI scoring for photo-scan submission {sub_id}")
                    def _background_ai_score(sid):
                        import time
                        for attempt in range(3):
                            try:
                                result = run_ai_scoring_for_submission(sid, auto_accept=True)
                                if result is not None:
                                    logger.info(f"[AUTO-AI] Background scoring succeeded for photo-scan submission {sid} on attempt {attempt + 1}")
                                    return
                                logger.warning(f"[AUTO-AI] Background scoring returned None for photo-scan submission {sid}, attempt {attempt + 1}")
                            except Exception as e:
                                logger.error(f"[AUTO-AI] Background scoring failed for photo-scan submission {sid}, attempt {attempt + 1}: {e}", exc_info=True)
                            if attempt < 2:
                                time.sleep(2 ** attempt)
                        logger.error(f"[AUTO-AI] Background scoring exhausted retries for photo-scan submission {sid}")
                    thread = threading.Thread(target=_background_ai_score, args=(sub_id,), daemon=True)
                    thread.start()

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


@scoring_bp.route('/host/photo-scan/team-count')
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
