import React from 'react';
import Leaderboard from './Leaderboard';

export default function SubmittedView({
  gameState,
  leaderboard,
  scoresRevealed,
  checkedAnswers,
  revealedAnswers,
}) {
  const { team_name, round_num, num_answers, submission, mobile_experience, submissions_closed } = gameState;

  return (
    <div className="container">
      <div className="card">
        <div className="brand-logo-submitted">
          <img src="/static/logo.png" alt="Game Night Guild" />
          <div className="game-title-submitted">Survey Says</div>
          <div className="round-complete-text">Round {round_num}</div>
        </div>

        <p style={{ color: 'var(--success)', fontSize: '1em', textAlign: 'center', margin: 0 }}>
          {'\u2705'} Submitted
        </p>

        {mobile_experience !== 'basic' && (
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
                        display: 'flex', alignItems: 'center', padding: '8px 10px',
                        borderRadius: '6px',
                        background: 'color-mix(in srgb, var(--text) 4%, transparent)',
                        border: '1px solid color-mix(in srgb, var(--text) 8%, transparent)',
                        fontSize: '0.9em',
                      }}>
                        <span style={{ color: 'var(--text-muted)', marginRight: '8px', fontWeight: 'bold' }}>#{i}</span>
                        <span style={{ flex: 1, color: 'var(--text-muted)' }}>
                          {submission[`answer${i}`] || '\u2014'}
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
                      {revealedAnswers.map((r) => {
                        const gotIt = checkedAnswers.has(r.answerNum);
                        return (
                          <div key={r.answerNum} style={{
                            display: 'flex', alignItems: 'center', padding: '8px 10px',
                            borderRadius: '6px', fontSize: '0.9em',
                            animation: 'ppRevealSlide 0.4s ease-out',
                            background: gotIt ? 'rgba(76,175,80,0.15)' : 'color-mix(in srgb, var(--accent) 8%, transparent)',
                            border: gotIt ? '1px solid rgba(76,175,80,0.3)' : '1px solid var(--card-border)',
                          }}>
                            <span style={{ fontSize: '1.1em', marginRight: '8px' }}>
                              {gotIt ? '\u2705' : '\u274C'}
                            </span>
                            <span style={{ color: 'var(--text-muted)', marginRight: '8px', fontWeight: 'bold' }}>
                              #{r.answerNum}
                            </span>
                            <span style={{
                              flex: 1,
                              color: gotIt ? '#4caf50' : 'var(--text-muted)',
                              fontWeight: gotIt ? 'bold' : 'normal',
                            }}>
                              {r.text}
                            </span>
                            {gotIt && (
                              <span style={{ color: '#4caf50', fontWeight: 'bold', fontSize: '0.85em' }}>
                                +{r.points} pts
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            )}

            <Leaderboard
              leaderboard={leaderboard}
              teamName={team_name}
              mobileExperience={mobile_experience}
              scoresRevealed={scoresRevealed}
            />

            <div className="waiting" style={{ padding: '20px 0' }}>
              <div className="loading"></div>
              <p>Survey Says...</p>
            </div>
          </>
        )}

        {mobile_experience === 'basic' && (
          <>
            {submissions_closed ? (
              <div style={{ padding: '20px', background: 'rgba(220,53,69,0.2)', border: '2px solid #dc3545', borderRadius: '10px', margin: '20px 0' }}>
                <h3 style={{ color: '#dc3545', marginBottom: '10px' }}>{'\u23F0'} Round Has Ended</h3>
                <p style={{ margin: 0 }}>The host is now scoring. Wait for the next round!</p>
              </div>
            ) : (
              <>
                <div className="warning">
                  {'\u26A0\uFE0F'} Do not manually refresh the page
                </div>
                <div className="waiting" style={{ padding: '20px 0' }}>
                  <div className="loading"></div>
                  <p>Waiting for next round...</p>
                  <p style={{ fontSize: '0.85em', opacity: 0.8, marginTop: '10px' }}>This page will refresh automatically</p>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
