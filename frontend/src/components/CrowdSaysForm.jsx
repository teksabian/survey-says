import React, { useState, useEffect, useRef, useCallback } from 'react';
import { compactHeader, expandHeader } from './FixedHeader';
import { useToast } from './Toast';

export default function CrowdSaysForm({
  gameState,
  autoSave,
  onSubmitted,
  typingRef,
  formSubmittedRef,
}) {
  const { num_answers, round_id, cache_bust, clues, timer_enabled, timer_seconds } = gameState;
  const addToast = useToast();

  const [answers, setAnswers] = useState(() => {
    const restored = autoSave.restore();
    const initial = {};
    for (let i = 1; i <= num_answers; i++) {
      initial[`answer${i}`] = (restored && restored[`answer${i}`]) || '';
    }
    return initial;
  });

  const [submitting, setSubmitting] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(timer_seconds || 45);
  const typingTimeout = useRef(null);
  const timerStarted = useRef(false);
  const formRef = useRef(null);

  // Timer countdown
  useEffect(() => {
    if (!timer_enabled || timerStarted.current) return;
    timerStarted.current = true;

    const interval = setInterval(() => {
      setTimeRemaining(prev => {
        if (prev <= 1) {
          clearInterval(interval);
          // Auto-submit
          if (!formSubmittedRef.current) {
            formSubmittedRef.current = true;
            if (formRef.current) formRef.current.requestSubmit();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [timer_enabled, formSubmittedRef]);

  const timerPct = timer_seconds > 0 ? (timeRemaining / timer_seconds * 100) : 100;
  const timerColor = timeRemaining <= 10 ? '#dc3545' : timeRemaining <= 20 ? '#ffc107' : 'var(--success, #28a745)';
  const timerMins = Math.floor(timeRemaining / 60);
  const timerSecs = timeRemaining % 60;

  const handleInput = useCallback((name, value) => {
    setAnswers(prev => {
      const next = { ...prev, [name]: value };
      autoSave.save(next);
      return next;
    });
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

    if (blankCount > 0 && timeRemaining > 0) {
      const plural = blankCount === 1 ? 'answer is' : 'answers are';
      if (!confirm(`Warning: ${blankCount} ${plural} blank!\n\nAre you sure you want to submit?`)) {
        return;
      }
    }

    setSubmitting(true);

    const formData = new FormData();
    formData.append('round_id', round_id);
    formData.append('tiebreaker', '0');
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
      setSubmitting(false);
      const form = formRef.current;
      if (form) {
        form.removeAttribute('onsubmit');
        form.submit();
      }
    }
  }, [answers, num_answers, round_id, cache_bust, submitting, timeRemaining, autoSave, onSubmitted, addToast, formSubmittedRef]);

  return (
    <>
      <div className="instructions-toggle" onClick={() => setInstructionsOpen(!instructionsOpen)}>
        <div className="instructions-header">
          <span>How Scoring Works (Tap to Expand)</span>
          <span className={`toggle-icon${instructionsOpen ? ' expanded' : ''}`}>{'\u25BC'}</span>
        </div>
        <div className={`instructions-content${instructionsOpen ? ' show' : ''}`}>
          <p style={{ color: 'var(--text, #fff)', fontSize: '0.9em', margin: '12px 0 8px 0', lineHeight: '1.5' }}>
            Fill in the blanks! Use the letter clues to guess all 7 survey answers before time runs out.
          </p>
          <ul className="instructions-list">
            <li>100 points per correct answer (max 700)</li>
            <li>Speed bonus: submit faster for up to 200 extra points</li>
            <li>All 7 correct = 300 point perfect bonus!</li>
            <li>Max per round: 1,200 points</li>
          </ul>
        </div>
      </div>

      {timer_enabled && (
        <div style={{ marginBottom: '15px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
            <span style={{ color: 'var(--text-accent)', fontWeight: 'bold' }}>Time Remaining</span>
            <span style={{ color: 'var(--text-accent)', fontWeight: 'bold', fontSize: '1.3em' }}>
              {timerMins}:{timerSecs < 10 ? '0' : ''}{timerSecs}
            </span>
          </div>
          <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{
              width: `${timerPct}%`,
              height: '100%',
              background: timerColor,
              borderRadius: '4px',
              transition: 'width 1s linear',
            }} />
          </div>
        </div>
      )}

      <form ref={formRef} id="answerForm" method="POST" action={`/play/submit?v=${cache_bust}`} onSubmit={handleSubmit}>
        <input type="hidden" name="round_id" value={round_id} />
        <input type="hidden" name="tiebreaker" value="0" />

        {Array.from({ length: num_answers }, (_, i) => i + 1).map(i => {
          const clue = clues && clues[i - 1];
          return (
            <div className="answer-group" key={i} style={{ position: 'relative' }}>
              <div className="answer-label" style={{ display: 'flex', alignItems: 'center' }}>
                <span style={{ fontFamily: "'Courier New', monospace", color: 'var(--text-accent)', fontWeight: 'bold', fontSize: '1.1em' }}>
                  {clue ? clue.letter : ''}
                </span>
                <span style={{
                  display: 'inline-block',
                  width: `${clue ? clue.length : 4}ch`,
                  borderBottom: '2px solid var(--text-accent)',
                  marginLeft: '6px',
                }} />
              </div>
              <input
                type="text"
                name={`answer${i}`}
                placeholder="Type your guess..."
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                value={answers[`answer${i}`]}
                onChange={e => handleInput(`answer${i}`, e.target.value)}
                onFocus={handleFocus}
                onBlur={handleBlur}
              />
            </div>
          );
        })}

        <button type="submit" disabled={submitting} style={{ marginTop: '10px' }}>
          {submitting ? 'Submitting...' : 'Submit Answers'}
        </button>
      </form>
    </>
  );
}
