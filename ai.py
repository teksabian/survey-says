"""
AI scoring, photo extraction, and corrections utilities for Family Feud.

This is a utility module (NOT a Blueprint) — it contains all Anthropic API
integration, prompt construction, and fuzzy matching helpers.  Called by
scoring and photo-scan routes in app.py.
"""

import os
import json
from difflib import SequenceMatcher

from config import (
    logger,
    ANTHROPIC_AVAILABLE, ANTHROPIC_API_KEY,
    AI_SCORING_ENABLED, AI_MODEL_DEFAULT, AI_MODEL_CHOICES,
    CORRECTIONS_FILE,
    PHOTO_SCAN_PROMPT, PHOTO_SCAN_SINGLE_PROMPT,
)
from database import get_setting


# ============= CORRECTIONS HISTORY =============

def load_corrections_history():
    """Load persistent corrections from JSON file (survives deploys)."""
    try:
        if os.path.exists(CORRECTIONS_FILE):
            with open(CORRECTIONS_FILE, 'r') as f:
                data = json.load(f)
                logger.info(f"[AI-CORRECTIONS] Loaded {len(data)} corrections from history file")
                return data
    except Exception as e:
        logger.warning(f"[AI-CORRECTIONS] Failed to load corrections history: {e}")
    return []


def save_correction_to_history(correction):
    """Append a correction to the persistent JSON file."""
    try:
        history = load_corrections_history()
        history.append(correction)
        with open(CORRECTIONS_FILE, 'w') as f:
            json.dump(history, f, indent=2)
        logger.info(f"[AI-CORRECTIONS] Saved correction to history file (total: {len(history)})")
    except Exception as e:
        logger.warning(f"[AI-CORRECTIONS] Failed to save correction to history: {e}")


# ============= ANTHROPIC CLIENT =============

# Initialize Anthropic client once for connection pooling
anthropic_client = None
if AI_SCORING_ENABLED:
    import anthropic
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info("Anthropic client initialized (connection pooling enabled)")


# ============= AI HELPERS =============

def get_current_ai_model():
    """Get the current AI model to use.
    Priority: database setting > AI_MODEL env var > hardcoded default.
    """
    db_value = get_setting('ai_model', '')
    if db_value:
        valid_ids = [m['id'] for m in AI_MODEL_CHOICES]
        if db_value in valid_ids:
            return db_value
        else:
            logger.warning(f"[AI] Unknown model in database: '{db_value}', falling back to default")
    return AI_MODEL_DEFAULT

def build_claude_api_kwargs(max_tokens_default):
    """Build keyword arguments for client.messages.create() based on current settings.

    When extended thinking is enabled, removes temperature and adds thinking parameter.
    When disabled, uses temperature=0.
    """
    thinking_enabled = get_setting('extended_thinking_enabled', 'false') == 'true'

    if thinking_enabled:
        budget = int(get_setting('thinking_budget_tokens', '10000'))
        budget = max(budget, 1024)
        effective_max_tokens = budget + max_tokens_default
        return {
            'max_tokens': effective_max_tokens,
            'thinking': {
                'type': 'enabled',
                'budget_tokens': budget,
            },
        }
    else:
        return {
            'max_tokens': max_tokens_default,
            'temperature': 0,
        }

def extract_response_text(message):
    """Extract the text content from a Claude API response.

    When extended thinking is enabled, message.content contains a thinking block
    followed by a text block. This finds the text block regardless.
    """
    for block in message.content:
        if block.type == 'text':
            return block.text
    return message.content[0].text

# Anthropic SDK requires streaming when max_tokens exceeds this threshold
# to avoid HTTP timeouts on long-running extended thinking requests.
STREAMING_THRESHOLD = 21333

def call_claude_api(client, model, messages, api_kwargs):
    """Call Claude API, using streaming when max_tokens exceeds SDK threshold.

    When extended thinking is enabled and max_tokens > 21333, the Anthropic SDK
    requires streaming to avoid HTTP timeouts. This helper automatically switches
    to streaming in that case, returning the same Message object either way.
    """
    use_streaming = (
        'thinking' in api_kwargs
        and api_kwargs.get('max_tokens', 0) > STREAMING_THRESHOLD
    )

    if use_streaming:
        logger.debug(f"[AI] Using streaming (max_tokens={api_kwargs['max_tokens']} > {STREAMING_THRESHOLD})")
        with client.messages.stream(
            model=model,
            messages=messages,
            **api_kwargs
        ) as stream:
            return stream.get_final_message()
    else:
        return client.messages.create(
            model=model,
            messages=messages,
            **api_kwargs
        )


# ============= FUZZY MATCHING =============

def similar(a, b):
    """Check if answers are similar (for auto-checking)"""
    if not a or not b:
        return False
    a_clean = a.lower().strip()
    b_clean = b.lower().strip()
    if a_clean == b_clean:
        logger.debug(f"[SCORING] similar() exact match: '{a}' == '{b}'")
        return True
    ratio = SequenceMatcher(None, a_clean, b_clean).ratio()
    if ratio > 0.9:
        logger.debug(f"[SCORING] similar() fuzzy match: '{a}' ~ '{b}' (ratio={ratio:.3f})")
        return True
    return False


# ============= VISION / PHOTO EXTRACTION =============

def extract_single_scorecard(image_b64):
    """
    Use Claude Vision API to extract answers from a photo of a SINGLE team's scorecard.

    Args:
        image_b64: Base64-encoded JPEG image string (no data URI prefix)

    Returns:
        Dict with keys: code, team_name, answers (list of 6 strings), tiebreaker (int), low_confidence_fields (list)
    """
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        logger.error("[PHOTO-SCAN] extract_single_scorecard() called but AI not available")
        return None

    try:
        current_model = get_current_ai_model()
        logger.info(f"[PHOTO-SCAN] Single scorecard extraction (model: {current_model}, image size: {len(image_b64)} chars base64)")

        client = anthropic_client

        api_kwargs = build_claude_api_kwargs(max_tokens_default=1024)

        message = call_claude_api(
            client=client,
            model=current_model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": PHOTO_SCAN_SINGLE_PROMPT
                    }
                ]
            }],
            api_kwargs=api_kwargs
        )

        response_text = extract_response_text(message)
        logger.info(f"[PHOTO-SCAN] Single scorecard response: {response_text[:500]}")

        # Parse JSON response
        response_json = None
        try:
            response_json = json.loads(response_text)
        except json.JSONDecodeError:
            brace_start = response_text.find('{')
            brace_end = response_text.rfind('}')
            if brace_start != -1 and brace_end != -1:
                try:
                    response_json = json.loads(response_text[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    pass

        if isinstance(response_json, dict):
            # Normalize the result
            response_json.setdefault('code', '')
            response_json.setdefault('team_name', '')
            response_json.setdefault('tiebreaker', 0)
            response_json.setdefault('low_confidence_fields', [])
            # Ensure exactly 6 answers
            answers = response_json.get('answers', [])
            while len(answers) < 6:
                answers.append('')
            response_json['answers'] = answers[:6]
            # Ensure tiebreaker is int
            try:
                response_json['tiebreaker'] = int(response_json['tiebreaker'])
            except (ValueError, TypeError):
                response_json['tiebreaker'] = 0

            logger.info(f"[PHOTO-SCAN] Extracted single scorecard: code='{response_json['code']}' team='{response_json['team_name']}'")
            return response_json
        else:
            logger.warning("[PHOTO-SCAN] Could not parse single scorecard response")
            return None

    except Exception as e:
        logger.error(f"[PHOTO-SCAN] Single scorecard extraction failed: {e}", exc_info=True)
        raise


def extract_answers_from_photo(image_b64):
    """
    Use Claude Vision API to extract handwritten answers from a photo of a paper answer sheet.

    Args:
        image_b64: Base64-encoded JPEG image string (no data URI prefix)

    Returns:
        List of dicts with keys: code, team_name, answers (list of 6 strings), tiebreaker (int), low_confidence_fields (list)
    """
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        logger.error("[PHOTO-SCAN] extract_answers_from_photo() called but AI not available")
        return []

    try:
        current_model = get_current_ai_model()
        logger.info(f"[PHOTO-SCAN] Calling Claude Vision API (model: {current_model}, image size: {len(image_b64)} chars base64)")

        client = anthropic_client

        api_kwargs = build_claude_api_kwargs(max_tokens_default=2048)
        logger.info(f"[PHOTO-SCAN] Extended thinking: {'ON' if 'thinking' in api_kwargs else 'OFF'}")

        message = call_claude_api(
            client=client,
            model=current_model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": PHOTO_SCAN_PROMPT
                    }
                ]
            }],
            api_kwargs=api_kwargs
        )

        response_text = extract_response_text(message)
        logger.info(f"[PHOTO-SCAN] Claude Vision response: {response_text[:500]}")

        # Parse JSON response - same fallback pattern as score_with_ai()
        response_json = None
        try:
            response_json = json.loads(response_text)
        except json.JSONDecodeError:
            brace_start = response_text.find('{')
            brace_end = response_text.rfind('}')
            if brace_start != -1 and brace_end != -1:
                try:
                    response_json = json.loads(response_text[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    pass

        if response_json and 'teams' in response_json:
            teams = response_json['teams']
            # Validate and normalize each team
            for team in teams:
                team.setdefault('code', '')
                team.setdefault('team_name', '')
                team.setdefault('tiebreaker', 0)
                team.setdefault('low_confidence_fields', [])
                # Ensure exactly 6 answers
                answers = team.get('answers', [])
                while len(answers) < 6:
                    answers.append('')
                team['answers'] = answers[:6]
                # Ensure tiebreaker is int
                try:
                    team['tiebreaker'] = int(team['tiebreaker'])
                except (ValueError, TypeError):
                    team['tiebreaker'] = 0

            logger.info(f"[PHOTO-SCAN] Extracted {len(teams)} teams from photo")
            return teams
        else:
            logger.warning(f"[PHOTO-SCAN] Could not parse teams from response")
            return []

    except Exception as e:
        logger.error(f"[PHOTO-SCAN] Claude Vision API call failed: {e}", exc_info=True)
        raise


# ============= AI SCORING =============

def score_with_ai(question, survey_answers, team_answers):
    """
    Use Claude AI to determine semantic matches between team answers and survey answers.

    Args:
        question: The Family Feud question text
        survey_answers: List of dicts with 'number', 'text', 'points' keys
        team_answers: List of strings (team's submitted answers)

    Returns:
        Dict with 'matches' (list of ints) and 'reasoning' (list of dicts)
    """
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        logger.error("[AI-SCORING] score_with_ai() called but AI not available")
        return {'matches': [], 'reasoning': []}

    # Build the prompt
    prompt = f"""You are scoring a Family Feud game. Determine which survey answers semantically match the team's submitted answers.

Question: "{question}"

Survey Answers (the correct answers from the survey):
"""
    for ans in survey_answers:
        prompt += f"{ans['number']}. {ans['text']} ({ans['points']} points)\n"

    prompt += "\nTeam's Submitted Answers:\n"
    for ans in team_answers:
        prompt += f"- {ans}\n"

    # === Fetch past corrections for long-term training ===
    # Load from persistent JSON file (survives deploys and DB resets)
    all_corrections = load_corrections_history()

    # Prioritize: same question first, then all others (most recent last)
    same_q = [c for c in all_corrections if c.get('question') == question]
    other_q = [c for c in all_corrections if c.get('question') != question]
    # Take up to 10 same-question + fill remaining with others, max 30 total
    recent_corrections = same_q[-10:] + other_q[-20:]
    if recent_corrections:
        logger.debug(f"[AI-SCORING] Loaded {len(recent_corrections)} corrections for training ({len(same_q)} same-question)")

    if recent_corrections:
        prompt += "\nPast Corrections (learn from these host overrides — apply similar logic to current answers):\n"
        for idx, corr in enumerate(recent_corrections, 1):
            if corr['correction_type'] == 'host_added':
                prompt += f'{idx}. SHOULD match: "{corr["team_answer"]}" matches "{corr["survey_answer"]}"'
            else:
                prompt += f'{idx}. Should NOT match: "{corr["team_answer"]}" does NOT match "{corr["survey_answer"]}"'
            # Prioritize host's explanation over AI's original reasoning
            if corr.get('host_reason'):
                prompt += f' — Host says: "{corr["host_reason"]}"'
            elif corr.get('ai_reasoning'):
                prompt += f' (you previously thought: {corr["ai_reasoning"]})'
            prompt += '\n'
        prompt += '\n'

    prompt += """
Matching Rules:
- Exact matches count (e.g., "car" matches "car")
- Synonyms count (e.g., "automobile" matches "car")
- Common abbreviations count (e.g., "bike" matches "bicycle")
- Specific types count (e.g., "minivan" matches "van")
- Plurals/singulars are the same (e.g., "dogs" matches "dog")
- Minor misspellings count if intent is clear
- Creative descriptions, slang, and informal phrases count if they clearly describe a survey answer (e.g., "electric holes" matches "outlet" because it describes the holes in an electrical outlet)
- IMPORTANT: Always interpret multi-word answers as a complete phrase first. Do NOT split compound phrases into individual words and match them separately. The meaning of the whole phrase takes priority
- Use the question as context to disambiguate close calls. Consider which survey answer the team most likely intended given what the question is asking
- DO NOT match if the meaning is different
- DO NOT match partial words that change meaning

Respond with ONLY a JSON object in this exact format:
{
  "matches": [1, 3, 5],
  "reasoning": [
    {"team_answer": "car", "matched_to": 1, "survey_answer": "Automobile", "why": "Car is a common synonym for automobile"},
    {"team_answer": "food", "matched_to": null, "survey_answer": null, "why": "Too vague, no survey answer about food"}
  ]
}

"matches" = list of survey answer numbers that have a semantic match in the team's answers.
"reasoning" = one entry per team answer, in the order they were submitted:
  - "team_answer" = the team's submitted text
  - "matched_to" = the survey answer number (integer) it matches, or null if no match
  - "survey_answer" = the text of the matched survey answer, or null if no match
  - "why" = one short sentence explaining the decision

If no matches at all, return: {"matches": [], "reasoning": [...]}"""

    try:
        current_model = get_current_ai_model()
        logger.debug(f"[AI-SCORING] Calling Claude API (model: {current_model}, prompt length: {len(prompt)} chars)")

        client = anthropic_client

        api_kwargs = build_claude_api_kwargs(max_tokens_default=1024)
        logger.debug(f"[AI-SCORING] Extended thinking: {'ON' if 'thinking' in api_kwargs else 'OFF'}")

        message = call_claude_api(
            client=client,
            model=current_model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            api_kwargs=api_kwargs
        )

        response_text = extract_response_text(message)
        logger.debug(f"[AI-SCORING] Claude response: {response_text}")

        # Parse JSON response - try full parse first, then regex fallback
        response_json = None
        try:
            response_json = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON object from response text
            # Find the outermost { ... } block
            brace_start = response_text.find('{')
            brace_end = response_text.rfind('}')
            if brace_start != -1 and brace_end != -1:
                try:
                    response_json = json.loads(response_text[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    pass

        if response_json and 'matches' in response_json:
            matches = response_json.get('matches', [])
            reasoning = response_json.get('reasoning', [])

            # Validate matches are within valid range
            max_num = max(a['number'] for a in survey_answers) if survey_answers else 0
            valid_matches = [m for m in matches if isinstance(m, int) and 1 <= m <= max_num]

            logger.info(f"[AI-SCORING] Parsed {len(valid_matches)} valid matches: {valid_matches}, {len(reasoning)} reasoning entries")
            return {'matches': valid_matches, 'reasoning': reasoning}
        else:
            logger.warning(f"[AI-SCORING] Could not parse JSON from response: {response_text}")
            return {'matches': [], 'reasoning': []}

    except Exception as e:
        logger.error(f"[AI-SCORING] Claude API call failed: {e}", exc_info=True)
        raise
