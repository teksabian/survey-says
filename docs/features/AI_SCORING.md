# AI-Assisted Scoring

**Added in:** v2.0.1
**API:** Claude (Anthropic) or GPT (OpenAI)

---

## Overview

The host can optionally send any team's answers to AI for automated scoring. AI evaluates semantic matches between team answers and survey answers. The host reviews suggestions and can accept, modify, or ignore them.

## How It Works

1. Host goes to Scoring Queue and sees a team's submission
2. Clicks "Send to AI for Scoring"
3. AI analyzes the question, survey answers (with point values), and team answers
4. AI returns which team answers match which survey answers with confidence levels
5. UI updates checkboxes based on AI suggestions
6. Host can accept (just click Submit), modify, or ignore completely

## What AI Understands

- **Synonyms:** "car" matches "automobile"
- **Abbreviations:** "bike" matches "bicycle"
- **Specific types:** "minivan" matches "van"
- **No false positives:** "boat" won't match anything if no boat answer exists

## Setup

1. Get an API key from one (or both) providers:
   - **Anthropic:** [console.anthropic.com](https://console.anthropic.com/)
   - **OpenAI:** [platform.openai.com](https://platform.openai.com/)
2. Add your API key(s) as environment variables on Render:
   - `ANTHROPIC_API_KEY` for Claude models
   - `OPENAI_API_KEY` for GPT models
3. Set `ENABLE_AI_SCORING=true` as an environment variable on Render
4. Deploy — pick your model from the Settings dropdown

> `ENABLE_AI_SCORING=true` **plus** at least one API key is required. Both keys can be set — the settings dropdown will show all available models grouped by provider.

## Fallback Behavior

- **No API key:** AI scoring section hidden in settings
- **API call fails:** Error message shown, manual scoring still works
- **Always safe:** Manual scoring is always available regardless of AI status

## Cost

Cost depends on the model selected. Ranges from ~$0.001 (GPT-4o-mini) to ~$0.05 (Claude Opus 4) per scoring.

## AI Training (v2.0.3+)

The AI learns from host corrections:
- When the host overrides an AI suggestion, the correction is recorded
- Corrections feed back into future AI calls as context
- Host notes (v2.0.4) let you teach the AI your scoring philosophy
- Corrections persist to `corrections_history.json` with GitHub sync (v2.0.4)

## Fringe Answers Summary (v3.2.0+)

After scoring, the Scored Teams page shows a collapsible "What AI Accepted This Round" panel. This tells the host which non-obvious answers the AI counted as correct — useful for announcing to the room.

- **Shows only true synonyms** — misspellings and typos are filtered out using character-level similarity checks
- **Grouped by survey answer** — each answer slot shows its accepted variants as green pill badges
- **Lazy-loaded** — data fetches from `/host/ai-accepted-summary` only when the panel is first expanded

## Security

- API key stored server-side only (environment variable)
- Never exposed to clients/browsers
- Only question + answers sent to API (no team names or personal info)
