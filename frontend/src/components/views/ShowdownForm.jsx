import { useState, useEffect, useCallback, useRef } from 'react'
import AnswerProgress from '../AnswerProgress'
import Leaderboard from '../Leaderboard'
import useAutoSave from '../../hooks/useAutoSave'

export default function ShowdownForm({
  gameState,
  leaderboard,
  scoresRevealed,
  connected,
  addToast,
  isTypingRef,
  saveAnswersRef,
  formSubmittedRef,
  onSubmitted,
}) {
  const { num_answers, round_id, code, cache_bust, question, team_name, mobile_experience } = gameState
  const { saveAnswers, restoreAnswers, clearSaved, saveAnswersImmediate } = useAutoSave(code, cache_bust, round_id)

  const [answers, setAnswers] = useState(() => {
    const initial = {}
    for (let i = 1; i <= num_answers; i++) {
      initial[`answer${i}`] = ''
    }
    initial.tiebreaker = ''
    return initial
  })
  const [submitting, setSubmitting] = useState(false)
  const typingTimeout = useRef(null)

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

    // Mark typing
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

    // Count blank answers
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
    formData.append('tiebreaker', answers.tiebreaker || '0')

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
      // Fallback: create a real form and submit it
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

  return (
    <div className="container">
      <div className="card">
        {/* Collapsible Instructions */}
        <InstructionsToggle numAnswers={num_answers} />

        <AnswerProgress filled={filledCount} total={num_answers} />

        <form id="answerForm" onSubmit={handleSubmit}>
          <input type="hidden" name="round_id" value={round_id} />

          {Array.from({ length: num_answers }, (_, i) => i + 1).map(i => (
            <div className="answer-group" key={i}>
              <div className="answer-label">Answer #{i}</div>
              <input
                type="text"
                name={`answer${i}`}
                placeholder={`Your answer #${i}...`}
                autoComplete="off"
                value={answers[`answer${i}`] || ''}
                onChange={(e) => handleInputChange(`answer${i}`, e.target.value)}
                onFocus={handleFocus}
              />
            </div>
          ))}

          {/* Tiebreaker */}
          <div className="tiebreaker-box">
            <h3>🎯 Tiebreaker</h3>
            <input
              type="number"
              name="tiebreaker"
              placeholder="0-100"
              min="0"
              max="100"
              value={answers.tiebreaker || ''}
              onChange={(e) => handleInputChange('tiebreaker', e.target.value)}
              onFocus={handleFocus}
            />
            <p>How many out of 100 people gave the #1 answer?</p>
          </div>

          <button type="submit" disabled={submitting}>
            {submitting ? 'Submitting...' : 'Submit Answers'}
          </button>
        </form>
      </div>
    </div>
  )
}

function InstructionsToggle({ numAnswers }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="instructions-toggle" onClick={() => setExpanded(!expanded)}>
      <div className="instructions-header">
        <span>How Scoring Works (Tap to Expand)</span>
        <span className={`toggle-icon${expanded ? ' expanded' : ''}`}>▼</span>
      </div>
      <div className={`instructions-content${expanded ? ' show' : ''}`}>
        <p style={{ color: 'var(--text, #fff)', fontSize: '0.9em', margin: '12px 0 8px 0', lineHeight: 1.5 }}>
          Each survey question was posed to 100 people, you're trying to match their top answers!
        </p>
        <ul className="instructions-list">
          <li>Order doesn't matter - just guess the answers!</li>
          <li>Most popular answer = {numAnswers} points</li>
          <li>Points decrease down to 1 point</li>
          <li>Tiebreaker: How many out of 100 people gave the #1 answer?</li>
        </ul>
      </div>
    </div>
  )
}
