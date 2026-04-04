import { useEffect, useRef, useState, useCallback } from 'react'
import { io } from 'socket.io-client'

export default function useSocket({
  setView,
  setLeaderboard,
  setScoresRevealed,
  setBroadcast,
  setWinnerData,
  setGameOverData,
  setCheckedAnswers,
  addRevealedAnswer,
  addToast,
  gameState,
  isTypingRef,
  saveAnswersRef,
  formSubmittedRef,
}) {
  const socketRef = useRef(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const socket = io()
    socketRef.current = socket

    socket.on('connect', async () => {
      console.log('[WS] Connected, transport:', socket.io.engine.transport.name)
      setConnected(true)

      try {
        const response = await fetch('/api/check-round-status')
        const data = await response.json()
        if (response.status === 401 && data.reload) {
          window.location.reload()
          return
        }
      } catch (e) {
        console.warn('[WS] Reconnect sync failed:', e)
      }

      // Refresh leaderboard on reconnect
      try {
        const r = await fetch('/api/leaderboard')
        const data = await r.json()
        if (data.scores_revealed) setScoresRevealed(true)
        if (data.leaderboard) setLeaderboard(data.leaderboard)
      } catch {}
    })

    socket.on('disconnect', (reason) => {
      console.log('[WS] Disconnected:', reason)
      setConnected(false)
    })

    socket.on('round:started', (data) => {
      console.log('[WS] round:started', data)
      setScoresRevealed(false)

      const mode = data.mobile_experience || 'advanced_no_pp'

      if (mode === 'basic') {
        window.location.href = '/play'
      } else if (data.previous_winner_team) {
        setWinnerData({
          teamName: data.previous_winner_team,
          score: data.previous_winner_score,
          roundNum: data.previous_round_number || '',
          question: data.previous_question,
          answers: data.previous_answers,
          wonOnTiebreaker: data.previous_won_on_tiebreaker,
          tiebreakerAnswer: data.previous_tiebreaker_answer,
          hideDetails: mode === 'advanced_pp',
        })
        setView('winner')
      } else if (mode === 'advanced_no_pp' && data.leaderboard) {
        setLeaderboard(data.leaderboard)
        setTimeout(() => { window.location.href = '/play' }, 5000)
      } else {
        window.location.href = '/play'
      }
    })

    socket.on('round:closed', (data) => {
      console.log('[WS] round:closed', data)
      if (formSubmittedRef.current) return

      if (isTypingRef.current) {
        if (saveAnswersRef.current) saveAnswersRef.current()
        if (addToast) {
          addToast('Round has closed. Your answers were saved but not submitted.', 'warning', 8000)
        }
        setTimeout(() => { window.location.reload() }, 5000)
      } else {
        if (saveAnswersRef.current) saveAnswersRef.current()
        window.location.reload()
      }
    })

    socket.on('round:ended', (data) => {
      console.log('[WS] round:ended (legacy)', data)
      window.location.reload()
    })

    socket.on('leaderboard:update', (data) => {
      console.log('[WS] leaderboard:update', data)
      if (data.scores_revealed !== undefined) {
        setScoresRevealed(data.scores_revealed)
      }
      if (data.leaderboard) {
        setLeaderboard(data.leaderboard)
      }
    })

    socket.on('scoring:your_results', (data) => {
      console.log('[WS] scoring:your_results', data)
      if (data.checked_answers) {
        const nums = new Set(
          data.checked_answers.split(',').filter(Boolean).map(Number)
        )
        setCheckedAnswers(nums)
      }
    })

    socket.on('tv:reveal', (data) => {
      console.log('[WS] tv:reveal', data)
      if (data.answer_num) {
        addRevealedAnswer({
          answerNum: data.answer_num,
          text: data.text || '',
          count: data.count || 0,
          points: data.points || 0,
        })
      }
    })

    socket.on('leaderboard:scores_revealed', () => {
      console.log('[WS] leaderboard:scores_revealed')
      setScoresRevealed(true)
    })

    socket.on('broadcast:message', (data) => {
      if (data.message && data.message.trim()) {
        try {
          const dismissKey = 'broadcast_dismiss_' + btoa(data.message)
          if (localStorage.getItem(dismissKey)) return
        } catch {}
        setBroadcast(data.message)
      } else {
        setBroadcast(null)
      }
    })

    socket.on('game:reset', () => {
      console.log('[WS] game:reset')
      try {
        Object.keys(localStorage).forEach(key => {
          if (key.startsWith('feud_answers_')) localStorage.removeItem(key)
        })
      } catch {}
      window.location.href = '/'
    })

    socket.on('game:over', (data) => {
      console.log('[WS] game:over', data)
      try {
        Object.keys(localStorage).forEach(key => {
          if (key.startsWith('feud_answers_')) localStorage.removeItem(key)
        })
      } catch {}
      socket.disconnect()
      setGameOverData(data)
      setView('gameover')
    })

    // Proactively disconnect on page hide
    const handlePageHide = () => socket.disconnect()
    const handleVisibility = () => {
      if (document.visibilityState === 'hidden') {
        socket.disconnect()
      } else {
        socket.connect()
      }
    }
    window.addEventListener('pagehide', handlePageHide)
    window.addEventListener('beforeunload', handlePageHide)
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      window.removeEventListener('pagehide', handlePageHide)
      window.removeEventListener('beforeunload', handlePageHide)
      document.removeEventListener('visibilitychange', handleVisibility)
      socket.disconnect()
    }
  }, [])

  return { socketRef, connected }
}
