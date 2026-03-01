# AI-Assisted Scoring

**Added in:** v2.0.1
**API:** Claude (Anthropic)

---

## Overview

The host can optionally send any team's answers to Claude AI for automated scoring. AI evaluates semantic matches between team answers and survey answers. The host reviews suggestions and can accept, modify, or ignore them.

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

1. Get an API key from [console.anthropic.com](https://console.anthropic.com/)
2. Add `ANTHROPIC_API_KEY` as an environment variable on Render
3. Set `ENABLE_AI_SCORING=true` as an environment variable on Render
4. Deploy — feature is live

> **Both** `ANTHROPIC_API_KEY` **and** `ENABLE_AI_SCORING=true` are required. The API key alone won't activate the feature.

## Fallback Behavior

- **No API key:** Button appears but shows "AI scoring not configured"
- **API call fails:** Error message shown, manual scoring still works
- **Always safe:** Manual scoring is always available regardless of AI status

## Cost

~$0.01 per scoring (1 penny). 100 scorings = ~$1.

## AI Training (v2.0.3+)

The AI learns from host corrections:
- When the host overrides an AI suggestion, the correction is recorded
- Corrections feed back into future AI calls as context
- Host notes (v2.0.4) let you teach the AI your scoring philosophy
- Corrections persist to `corrections_history.json` with GitHub sync (v2.0.4)

## Security

- API key stored server-side only (environment variable)
- Never exposed to clients/browsers
- Only question + answers sent to API (no team names or personal info)
