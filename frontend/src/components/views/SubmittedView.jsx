import Leaderboard from '../Leaderboard'

export default function SubmittedView({
  gameState,
  leaderboard,
  scoresRevealed,
  checkedAnswers,
  revealedAnswers,
}) {
  const { team_name, round_num, num_answers, submission, mobile_experience, submissions_closed } = gameState

  return (
    <div className="container">
      <div className="card">
        {/* Brand logo header */}
        <div className="brand-logo-submitted">
          <img src="/static/logo.png" alt="Game Night Guild" />
          <div className="game-title-submitted">Survey Says</div>
          <div className="round-complete-text">Round {round_num}</div>
        </div>

        <p style={{ color: 'var(--success)', fontSize: '1em', textAlign: 'center', margin: 0 }}>
          ✅ Submitted
        </p>

        {mobile_experience !== 'basic' ? (
          <>
            {mobile_experience === 'advanced_pp' && submission && (
              <>
                {/* Your Answers */}
                <div style={{ marginTop: '15px' }}>
                  <div style={{ fontSize: '0.9em', fontWeight: 'bold', color: 'var(--text, #fff)', marginBottom: '8px', textAlign: 'center' }}>
                    Your Answers
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '12px' }}>
                    {Array.from({ length: num_answers }, (_, i) => i + 1).map(i => (
                      <div key={i} style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '8px 10px',
                        borderRadius: '6px',
                        background: 'color-mix(in srgb, var(--text) 4%, transparent)',
                        border: '1px solid color-mix(in srgb, var(--text) 8%, transparent)',
                        fontSize: '0.9em',
                      }}>
                        <span style={{ color: 'var(--text-muted)', marginRight: '8px', fontWeight: 'bold' }}>#{i}</span>
                        <span style={{ flex: 1, color: 'var(--text-muted)' }}>
                          {submission[`answer${i}`] || '—'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Reveal Tracker */}
                {revealedAnswers.length > 0 && (
                  <div style={{ marginTop: '10px' }}>
                    <div style={{ fontSize: '0.9em', fontWeight: 'bold', color: 'var(--text-accent, #ffd700)', marginBottom: '8px', textAlign: 'center' }}>
                      Survey Answers
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                      {revealedAnswers.map(answer => {
                        const gotIt = checkedAnswers.has(answer.answerNum)
                        return (
                          <div key={answer.answerNum} className={`reveal-entry${gotIt ? ' got-it' : ''}`}>
                            <span style={{ fontSize: '1.1em', marginRight: '8px' }}>
                              {gotIt ? '✅' : '❌'}
                            </span>
                            <span style={{ color: 'var(--text-muted)', marginRight: '8px', fontWeight: 'bold' }}>
                              #{answer.answerNum}
                            </span>
                            <span style={{
                              flex: 1,
                              color: gotIt ? '#4caf50' : 'var(--text-muted)',
                              fontWeight: gotIt ? 'bold' : 'normal',
                            }}>
                              {answer.text}
                            </span>
                            {gotIt && (
                              <span style={{ color: '#4caf50', fontWeight: 'bold', fontSize: '0.85em' }}>
                                +{answer.points} pts
                              </span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Leaderboard */}
            <Leaderboard
              leaderboard={leaderboard}
              teamName={team_name}
              scoresRevealed={scoresRevealed}
              mobileExperience={mobile_experience}
            />

            <div className="waiting" style={{ padding: '20px 0' }}>
              <div className="loading"></div>
              <p>Survey Says...</p>
            </div>
          </>
        ) : (
          <>
            {submissions_closed ? (
              <div style={{
                padding: '20px',
                background: 'rgba(220,53,69,0.2)',
                border: '2px solid #dc3545',
                borderRadius: '10px',
                margin: '20px 0',
              }}>
                <h3 style={{ color: '#dc3545', marginBottom: '10px' }}>⏰ Round Has Ended</h3>
                <p style={{ margin: 0 }}>The host is now scoring. Wait for the next round!</p>
              </div>
            ) : (
              <>
                <div className="warning">⚠️ Do not manually refresh the page</div>
                <div className="waiting" style={{ padding: '20px 0' }}>
                  <div className="loading"></div>
                  <p>Waiting for next round...</p>
                  <p style={{ fontSize: '0.85em', opacity: 0.8, marginTop: '10px' }}>
                    This page will refresh automatically
                  </p>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
