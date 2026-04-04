import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ToastProvider, useToast } from './components/Toast';
import useTheme from './hooks/useTheme';
import useSocket from './hooks/useSocket';
import useAutoSave from './hooks/useAutoSave';
import useIdleTimer from './hooks/useIdleTimer';
import FixedHeader from './components/FixedHeader';
import BroadcastBanner from './components/BroadcastBanner';
import SettingsModal from './components/SettingsModal';
import WaitingView from './components/WaitingView';
import ShowdownForm from './components/ShowdownForm';
import CrowdSaysForm from './components/CrowdSaysForm';
import SubmittedView from './components/SubmittedView';
import RoundClosedView from './components/RoundClosedView';
import WinnerInterstitial from './components/WinnerInterstitial';
import GameOver from './components/GameOver';
import Leaderboard from './components/Leaderboard';

function AppInner() {
  const [gameState, setGameState] = useState(null);
  const [view, setView] = useState('loading');
  const [leaderboard, setLeaderboard] = useState([]);
  const [scoresRevealed, setScoresRevealed] = useState(false);
  const [broadcast, setBroadcast] = useState(null);
  const [connected, setConnected] = useState(false);
  const [winnerData, setWinnerData] = useState(null);
  const [gameOverData, setGameOverData] = useState(null);
  const [checkedAnswers, setCheckedAnswers] = useState(new Set());
  const [revealedAnswers, setRevealedAnswers] = useState([]);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const gameStateRef = useRef(null);
  const typingRef = useRef(false);
  const formSubmittedRef = useRef(false);

  const addToast = useToast();

  // Bootstrap: fetch /play/init on mount
  useEffect(() => {
    fetch('/play/init')
      .then(r => {
        if (r.status === 401) {
          window.location.href = '/join';
          return null;
        }
        return r.json();
      })
      .then(data => {
        if (!data) return;
        setGameState(data);
        gameStateRef.current = data;

        if (data.no_active_round) {
          setView('waiting');
        } else if (data.already_submitted) {
          setView('submitted');
          // Parse checked_answers from submission
          if (data.submission && data.submission.checked_answers) {
            setCheckedAnswers(new Set(
              data.submission.checked_answers.split(',').filter(Boolean).map(Number)
            ));
          }
        } else if (data.submissions_closed) {
          setView('closed');
        } else {
          setView('form');
        }
      })
      .catch(err => {
        console.error('[INIT] Failed to load:', err);
      });
  }, []);

  // Fetch initial leaderboard + broadcast
  useEffect(() => {
    if (!gameState) return;

    fetch('/api/leaderboard')
      .then(r => r.json())
      .then(data => {
        if (data.scores_revealed) setScoresRevealed(true);
        if (data.leaderboard) setLeaderboard(data.leaderboard);
      })
      .catch(() => {});

    fetch('/api/broadcast-message')
      .then(r => r.json())
      .then(data => {
        if (data.message && data.message.trim()) {
          try {
            const dismissKey = 'broadcast_dismiss_' + btoa(data.message);
            if (!localStorage.getItem(dismissKey)) {
              setBroadcast(data.message);
            }
          } catch {
            setBroadcast(data.message);
          }
        }
      })
      .catch(() => {});
  }, [gameState]);

  // Theme
  const { currentTheme, selectTheme, resetTheme } = useTheme(
    gameState?.themes,
    gameState?.theme_key
  );

  // Auto-save
  const autoSave = useAutoSave(
    gameState?.code || '',
    gameState?.cache_bust || '',
    gameState?.round_id || ''
  );

  // Save function for socket to call
  const saveAnswersNow = useCallback(() => {
    // Auto-save triggers on input, this is a final flush
    // The actual save is debounced in the hook
  }, []);

  // Socket
  useSocket({
    setConnected,
    setView,
    setLeaderboard,
    setScoresRevealed,
    setBroadcast,
    setWinnerData,
    setGameOverData,
    setCheckedAnswers,
    setRevealedAnswers,
    addToast,
    gameStateRef,
    answersRef: { current: {} },
    typingRef,
    formSubmittedRef,
    saveAnswers: saveAnswersNow,
  });

  // Idle timer (only when form is active)
  useIdleTimer();

  // Handle AJAX submission success -> switch to submitted view
  const handleSubmitted = useCallback((data) => {
    formSubmittedRef.current = true;
    setView('submitted');
    // Update gameState to reflect submission
    setGameState(prev => ({
      ...prev,
      already_submitted: true,
      submission: data.answers ? {
        ...Object.fromEntries(
          Object.entries(data.answers).map(([k, v]) => [k, v])
        ),
        tiebreaker: data.tiebreaker,
      } : prev.submission,
    }));

    // Refresh leaderboard
    fetch('/api/leaderboard')
      .then(r => r.json())
      .then(d => {
        if (d.leaderboard) setLeaderboard(d.leaderboard);
      })
      .catch(() => {});
  }, []);

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
    );
  }

  // Game over replaces everything
  if (view === 'gameover' && gameOverData) {
    return <GameOver data={gameOverData} />;
  }

  // Winner interstitial
  if (view === 'winner' && winnerData) {
    return <WinnerInterstitial data={winnerData} />;
  }

  const showHeader = view === 'form';

  return (
    <>
      <BroadcastBanner message={broadcast} onDismiss={() => setBroadcast(null)} />

      {showHeader && (
        <FixedHeader
          roundNum={gameState.round_num}
          teamName={gameState.team_name}
          question={gameState.question}
          connected={connected}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      )}

      {view === 'waiting' && (
        <WaitingView
          leaderboard={leaderboard}
          teamName={gameState.team_name}
          mobileExperience={gameState.mobile_experience}
          scoresRevealed={scoresRevealed}
        />
      )}

      {view === 'form' && (
        <div className="container">
          <div className="card">
            {gameState.clues ? (
              <CrowdSaysForm
                gameState={gameState}
                autoSave={autoSave}
                onSubmitted={handleSubmitted}
                typingRef={typingRef}
                formSubmittedRef={formSubmittedRef}
              />
            ) : (
              <ShowdownForm
                gameState={gameState}
                autoSave={autoSave}
                onSubmitted={handleSubmitted}
                typingRef={typingRef}
                formSubmittedRef={formSubmittedRef}
              />
            )}
          </div>
        </div>
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
          roundNum={gameState.round_num}
          leaderboard={leaderboard}
          teamName={gameState.team_name}
          mobileExperience={gameState.mobile_experience}
          scoresRevealed={scoresRevealed}
        />
      )}

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        themes={gameState.themes}
        currentTheme={currentTheme}
        onSelectTheme={(key) => { selectTheme(key); }}
        onResetTheme={() => { resetTheme(); setSettingsOpen(false); }}
      />
    </>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}
