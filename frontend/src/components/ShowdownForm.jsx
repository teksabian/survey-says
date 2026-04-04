import React, { useState, useEffect, useRef, useCallback } from 'react';
import AnswerProgress from './AnswerProgress';
import { compactHeader, expandHeader } from './FixedHeader';
import { useToast } from './Toast';

export default function ShowdownForm({
  gameState,
  autoSave,
  onSubmitted,
  typingRef,
  formSubmittedRef,
}) {
  const { num_answers, round_id, cache_bust } = gameState;
  const addToast = useToast();

  const [answers, setAnswers] = useState(() => {
    const restored = autoSave.restore();
    const initial = {};
    for (let i = 1; i <= num_answers; i++) {
      initial[`answer${i}`] = (restored && restored[`answer${i}`]) || '';
    }
    initial.tiebreaker = (restored && restored.tiebreaker) || '';
    return initial;
  });

  const [submitting, setSubmitting] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const typingTimeout = useRef(null);

  const filled = Object.keys(answers)
    .filter(k => k.startsWith('answer'))
    .filter(k => answers[k].trim()).length;

  const handleInput = useCallback((name, value) => {
    setAnswers(prev => {
      const next = { ...prev, [name]: value };
      autoSave.save(next);
      return next;
    });

    // Mark typing
    typingRef.current = true;
    clearTimeout(typingTimeout.current);
    typingTimeout.current = setTimeout(() => { typingRef.current = false; }, 2000);
  }, [autoSave, typingRef]);

  const handleFocus = useCallback((e) => {
    compactHeader();
    setTimeout(() => {
      e.target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 300);
  }, []);

  const handleBlur = useCallback(() => {
    setTimeout(() => {
      if (!document.activeElement || document.activeElement.tagName !== 'INPUT') {
        expandHeader();
      }
    }, 100);
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (submitting) return;

    // Check for blank answers
    let blankCount = 0;
    for (let i = 1; i <= num_answers; i++) {
      if (!answers[`answer${i}`].trim()) blankCount++;
    }

    if (blankCount > 0) {
      const plural = blankCount === 1 ? 'answer is' : 'answers are';
      if (!confirm(`Warning: ${blankCount} ${plural} blank!\n\nAre you sure you want to submit?`)) {
        return;
      }
    }

    setSubmitting(true);

    const formData = new FormData();
    formData.append('round_id', round_id);
    formData.append('tiebreaker', answers.tiebreaker || '0');
    for (let i = 1; i <= num_answers; i++) {
      formData.append(`answer${i}`, answers[`answer${i}`]);
    }

    try {
      const response = await fetch(`/play/submit?v=${cache_bust}`, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
        },
      });
      const data = await response.json();

      if (data.success) {
        formSubmittedRef.current = true;
        autoSave.clear();
        onSubmitted(data);
      } else {
        addToast(data.error || 'Submission failed. Please try again.', 'error');
        setSubmitting(false);
      }
    } catch {
      // Fallback: submit form normally
      setSubmitting(false);
      const form = document.getElementById('answerForm');
      if (form) {
        form.removeAttribute('onsubmit');
        form.submit();
      }
    }
  }, [answers, num_answers, round_id, cache_bust, submitting, autoSave, onSubmitted, addToast, formSubmittedRef]);

  return (
    <>
      <div className="instructions-toggle" onClick={() => setInstructionsOpen(!instructionsOpen)}>
        <div className="instructions-header">
          <span>How Scoring Works (Tap to Expand)</span>
          <span className={`toggle-icon${instructionsOpen ? ' expanded' : ''}`}>{'\u25BC'}</span>
        </div>
        <div className={`instructions-content${instructionsOpen ? ' show' : ''}`}>
          <p style={{ color: 'var(--text, #fff)', fontSize: '0.9em', margin: '12px 0 8px 0', lineHeight: '1.5' }}>
            Each survey question was posed to 100 people, you're trying to match their top answers!
          </p>
          <ul className="instructions-list">
            <li>Order doesn't matter - just guess the answers!</li>
            <li>Most popular answer = {num_answers} points</li>
            <li>Points decrease down to 1 point</li>
            <li>Tiebreaker: How many out of 100 people gave the #1 answer?</li>
          </ul>
        </div>
      </div>

      <AnswerProgress filled={filled} total={num_answers} />

      <form id="answerForm" method="POST" action={`/play/submit?v=${cache_bust}`} onSubmit={handleSubmit}>
        <input type="hidden" name="round_id" value={round_id} />

        {Array.from({ length: num_answers }, (_, i) => i + 1).map(i => (
          <div className="answer-group" key={i}>
            <div className="answer-label">Answer #{i}</div>
            <input
              type="text"
              name={`answer${i}`}
              placeholder={`Your answer #${i}...`}
              autoComplete="off"
              value={answers[`answer${i}`]}
              onChange={e => handleInput(`answer${i}`, e.target.value)}
              onFocus={handleFocus}
              onBlur={handleBlur}
            />
          </div>
        ))}

        <div className="tiebreaker-box">
          <h3>{'\uD83C\uDFAF'} Tiebreaker</h3>
          <input
            type="number"
            name="tiebreaker"
            placeholder="0-100"
            min="0"
            max="100"
            value={answers.tiebreaker}
            onChange={e => handleInput('tiebreaker', e.target.value)}
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
          <p>How many out of 100 people gave the #1 answer?</p>
        </div>

        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting...' : 'Submit Answers'}
        </button>
      </form>
    </>
  );
}
