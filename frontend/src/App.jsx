import { useState, useEffect, useCallback, useRef } from 'react'
import useSocket from './hooks/useSocket'
import useTheme from './hooks/useTheme'
import useIdleTimer from './hooks/useIdleTimer'
import { useToasts } from './components/Toast'
import ToastContainer from './components/Toast'
import BroadcastBanner from './components/BroadcastBanner'
import FixedHeader from './components/FixedHeader'
import SettingsModal from './components/SettingsModal'
import WinnerInterstitial from './components/WinnerInterstitial'
import GameOver from './components/GameOver'
import WaitingView from './components/views/WaitingView'
import ShowdownForm from './components/views/ShowdownForm'
import CrowdSaysForm from './components/views/CrowdSaysForm'
import SubmittedView from './components/views/SubmittedView'
import RoundClosedView from './components/views/RoundClosedView'

export default function App() {
  const [gameState, setGameState] = useState(null)
  const [view, setView] = useState('loading')
  const [leaderboard, setLeaderboard] = useState([])
  const [scoresRevealed, setScoresRevealed] = useState(false)
  const [broadcast, setBroadcast] = useState(null)
  const [winnerData, setWinnerData] = useState(null)
  const [gameOverData, setGameOverData] = useState(null)
  const [checkedAnswers, setCheckedAnswers] = useState(new Set())
  const [revealedAnswers, setRevealedAnswers] = useState([])
  const [settingsOpen, setSettingsOpen] = useState(false)

  const isTypingRef = useRef(false)
  const saveAnswersRef = useRef(null)
  const formSubmittedRef = useRef(false)

  const { toasts, addToast, removeToast } = useToasts()

  const addRevealedAnswer = useCallback((answer) => {
    setRevealedAnswers(prev => [...prev, answer])
  }, [])

  // Bootstrap: fetch /play/init on mount
  useEffect(() => {
    fetch('/play/init')
      .then(r => {
        if (r.redirected) {
          window.location.href = r.url
          return null
        }
        return r.json()
      })
      .then(data => {
        if (!data) return
        setGameState(data)

        // Initialize checked answers from submission if PP mode
        if (data.mobile_experience === 'advanced_pp' && data.submission?.checked_answers) {
          const nums = new Set(
            data.submission.checked_answers.split(',').filter(Boolean).map(Number)
          )
          setCheckedAnswers(nums)
        }

        // Determine initial view
        if (data.no_active_round) {
          setView('waiting')
        } else if (data.already_submitted) {
          setView('submitted')
        } else if (data.submissions_closed) {
          setView('closed')
        } else {
          setView('form')
        }
      })
      .catch(err => {
        console.error('[INIT] Failed to fetch play data:', err)
        addToast('Failed to load game data. Please refresh.', 'error')
      })
  }, [addToast])

  // Fetch initial broadcast
  useEffect(() => {
    fetch('/api/broadcast-message')
      .then(r => r.json())
      .then(data => {
        if (data.message && data.message.trim()) {
          try {
            const dismissKey = 'broadcast_dismiss_' + btoa(data.message)
            if (localStorage.getItem(dismissKey)) return
          } catch {}
          setBroadcast(data.message)
        }
      })
      .catch(() => {})
  }, [])

  // Theme
  const { currentTheme, selectTheme, resetTheme } = useTheme(
    gameState?.themes,
    gameState?.theme_key
  )

  // Socket
  const { connected } = useSocket({
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
  })

  // Idle timer (only on form view)
  useIdleTimer()

  // Handle AJAX submission success — switch to submitted view
  const handleSubmitted = useCallback((data) => {
    setView('submitted')
    // Refresh leaderboard after submission
    fetch('/api/leaderboard')
      .then(r => r.json())
      .then(lb => {
        if (lb.scores_revealed) setScoresRevealed(true)
        if (lb.leaderboard) setLeaderboard(lb.leaderboard)
      })
      .catch(() => {})
  }, [])

  // Loading state
  if (view === 'loading' || !gameState) {
    return (
      <div className="container">
        <div className="card">
          <div className="waiting">
            <div className="loading"></div>
            <p>Loading...</p>
          </div>
        </div>
      </div>
    )
  }

  // Game over — replaces everything
  if (view === 'gameover') {
    return <GameOver data={gameOverData} />
  }

  const showHeader = view === 'form'

  return (
    <>
      <BroadcastBanner message={broadcast} onDismiss={() => setBroadcast(null)} />
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      {showHeader && (
        <FixedHeader
          roundNum={gameState.round_num}
          teamName={gameState.team_name}
          question={gameState.question}
          connected={connected}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      )}

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        themes={gameState.themes}
        currentTheme={currentTheme}
        onSelectTheme={selectTheme}
        onResetTheme={() => { resetTheme(); setSettingsOpen(false) }}
      />

      {view === 'winner' && <WinnerInterstitial data={winnerData} />}

      {view === 'waiting' && (
        <WaitingView
          teamName={gameState.team_name}
          mobileExperience={gameState.mobile_experience}
          leaderboard={leaderboard}
          scoresRevealed={scoresRevealed}
        />
      )}

      {view === 'form' && !gameState.clues && (
        <ShowdownForm
          gameState={gameState}
          leaderboard={leaderboard}
          scoresRevealed={scoresRevealed}
          connected={connected}
          addToast={addToast}
          isTypingRef={isTypingRef}
          saveAnswersRef={saveAnswersRef}
          formSubmittedRef={formSubmittedRef}
          onSubmitted={handleSubmitted}
        />
      )}

      {view === 'form' && gameState.clues && (
        <CrowdSaysForm
          gameState={gameState}
          addToast={addToast}
          isTypingRef={isTypingRef}
          saveAnswersRef={saveAnswersRef}
          formSubmittedRef={formSubmittedRef}
          onSubmitted={handleSubmitted}
        />
      )}

      {view === 'submitted' && (
        <SubmittedView
          gameState={gameState}
          leaderboard={leaderboard}
          scoresRevealed={scoresRevealed}
          checkedAnswers={checkedAnswers}
          revealedAnswers={revealedAnswers}
        />
      )}

      {view === 'closed' && (
        <RoundClosedView
          teamName={gameState.team_name}
          mobileExperience={gameState.mobile_experience}
          leaderboard={leaderboard}
          scoresRevealed={scoresRevealed}
        />
      )}
    </>
  )
}
