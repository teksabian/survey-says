import { useState, useEffect, useCallback, useRef } from 'react'
import AnswerProgress from '../AnswerProgress'
import useAutoSave from '../../hooks/useAutoSave'

export default function CrowdSaysForm({
  gameState,
  addToast,
  isTypingRef,
  saveAnswersRef,
  formSubmittedRef,
  onSubmitted,
}) {
  const {
    num_answers, round_id, code, cache_bust, clues,
    timer_enabled, timer_seconds,
  } = gameState

  const { saveAnswers, restoreAnswers, clearSaved, saveAnswersImmediate } = useAutoSave(code, cache_bust, round_id)

  const [answers, setAnswers] = useState(() => {
    const initial = {}
    for (let i = 1; i <= num_answers; i++) {
      initial[`answer${i}`] = ''
    }
    return initial
  })
  const [submitting, setSubmitting] = useState(false)
  const [timeRemaining, setTimeRemaining] = useState(timer_seconds || 45)
  const timerStarted = useRef(false)
  const typingTimeout = useRef(null)
  const formRef = useRef(null)

  // Restore saved answers on mount
  useEffect(() => {
    const saved = restoreAnswers()
    if (saved) {
      setAnswers(prev => ({ ...prev, ...saved }))
    }
  }, [restoreAnswers])

  // Expose save function to socket handler
  useEffect(() => {
    saveAnswersRef.current = () => saveAnswersImmediate(answers)
  }, [answers, saveAnswersRef, saveAnswersImmediate])

  // Timer countdown
  useEffect(() => {
    if (!timer_enabled || timerStarted.current) return
    timerStarted.current = true

    const interval = setInterval(() => {
      setTimeRemaining(prev => {
        if (prev <= 1) {
          clearInterval(interval)
          // Auto-submit
          if (!formSubmittedRef.current) {
            formSubmittedRef.current = true
            // Submit via form POST for auto-submit
            if (formRef.current) formRef.current.submit()
          }
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [timer_enabled, formSubmittedRef])

  const filledCount = Object.entries(answers)
    .filter(([key]) => key.startsWith('answer'))
    .filter(([, val]) => val.trim() !== '')
    .length

  const handleInputChange = useCallback((name, value) => {
    setAnswers(prev => {
      const next = { ...prev, [name]: value }
      saveAnswers(next)
      return next
    })

    isTypingRef.current = true
    clearTimeout(typingTimeout.current)
    typingTimeout.current = setTimeout(() => {
      isTypingRef.current = false
    }, 2000)
  }, [saveAnswers, isTypingRef])

  const handleFocus = useCallback((e) => {
    setTimeout(() => {
      e.target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 300)
  }, [])

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault()

    let blankCount = 0
    for (let i = 1; i <= num_answers; i++) {
      if (!answers[`answer${i}`]?.trim()) blankCount++
    }

    if (blankCount > 0) {
      const plural = blankCount === 1 ? 'answer is' : 'answers are'
      if (!window.confirm(`Warning: ${blankCount} ${plural} blank!\n\nAre you sure you want to submit?`)) {
        return
      }
    }

    setSubmitting(true)

    const formData = new FormData()
    formData.append('round_id', round_id)
    for (let i = 1; i <= num_answers; i++) {
      formData.append(`answer${i}`, answers[`answer${i}`] || '')
    }
    formData.append('tiebreaker', '0')

    try {
      const response = await fetch(`/play/submit?v=${cache_bust}`, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
        },
      })
      const data = await response.json()

      if (data.success) {
        formSubmittedRef.current = true
        clearSaved()
        onSubmitted(data)
      } else {
        addToast(data.error || 'Submission failed. Please try again.', 'error')
        setSubmitting(false)
      }
    } catch (err) {
      console.error('[SUBMIT] AJAX failed:', err)
      const form = document.createElement('form')
      form.method = 'POST'
      form.action = `/play/submit?v=${cache_bust}`
      formData.forEach((value, key) => {
        const input = document.createElement('input')
        input.type = 'hidden'
        input.name = key
        input.value = value
        form.appendChild(input)
      })
      document.body.appendChild(form)
      form.submit()
    }
  }, [answers, num_answers, round_id, cache_bust, clearSaved, addToast, formSubmittedRef, onSubmitted])

  // Timer display
  const timerMins = Math.floor(timeRemaining / 60)
  const timerSecs = timeRemaining % 60
  const timerPct = timer_seconds > 0 ? (timeRemaining / timer_seconds * 100) : 100
  let timerColor = 'var(--success, #28a745)'
  if (timeRemaining <= 10) timerColor = '#dc3545'
  else if (timeRemaining <= 20) timerColor = '#ffc107'

  return (
    <div className="container">
      <div className="card">
        {/* Instructions */}
        <CrowdSaysInstructions />

        {/* Timer */}
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

        <AnswerProgress filled={filledCount} total={num_answers} />

        <form
          ref={formRef}
          id="answerForm"
          method="POST"
          action={`/play/submit?v=${cache_bust}`}
          onSubmit={handleSubmit}
        >
          <input type="hidden" name="round_id" value={round_id} />
          <input type="hidden" name="tiebreaker" value="0" />

          {Array.from({ length: num_answers }, (_, i) => i + 1).map(i => {
            const clue = clues && clues[i - 1]
            return (
              <div className="answer-group cs-answer-group" key={i} style={{ position: 'relative' }}>
                <div className="answer-label" style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ fontFamily: "'Courier New', monospace", color: 'var(--text-accent)', fontWeight: 'bold', fontSize: '1.1em' }}>
                    {clue?.letter || ''}
                  </span>
                  <span style={{
                    display: 'inline-block',
                    width: `${clue?.length || 0}ch`,
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
                  className="cs-input"
                  value={answers[`answer${i}`] || ''}
                  onChange={(e) => handleInputChange(`answer${i}`, e.target.value)}
                  onFocus={handleFocus}
                />
              </div>
            )
          })}

          <button type="submit" disabled={submitting} style={{ marginTop: '10px' }}>
            {submitting ? 'Submitting...' : 'Submit Answers'}
          </button>
        </form>
      </div>
    </div>
  )
}

function CrowdSaysInstructions() {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="instructions-toggle" onClick={() => setExpanded(!expanded)}>
      <div className="instructions-box">
        <div className="instructions-header">
          <span>How Scoring Works (Tap to Expand)</span>
          <span className={`toggle-icon${expanded ? ' expanded' : ''}`}>▼</span>
        </div>
        <div className={`instructions-content${expanded ? ' show' : ''}`}>
          <p style={{ color: 'var(--text, #fff)', fontSize: '0.9em', margin: '12px 0 8px 0', lineHeight: 1.5 }}>
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
    </div>
  )
}
