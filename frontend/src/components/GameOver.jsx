import React, { useEffect } from 'react';
import confetti from 'canvas-confetti';

function getMedal(rank) {
  if (rank === 1) return '\uD83E\uDD47';
  if (rank === 2) return '\uD83E\uDD48';
  if (rank === 3) return '\uD83E\uDD49';
  return `${rank}.`;
}

export default function GameOver({ data }) {
  useEffect(() => {
    confetti({ particleCount: 150, spread: 70, origin: { y: 0.6 } });
    setTimeout(() => {
      confetti({ particleCount: 80, spread: 100, origin: { y: 0.5 } });
    }, 400);
    setTimeout(() => {
      confetti({ particleCount: 100, spread: 120, origin: { y: 0.4 } });
    }, 800);
  }, []);

  return (
    <div style={{ textAlign: 'center', padding: '30px 20px', maxWidth: '500px', margin: '0 auto' }}>
      <h1 style={{ color: 'var(--text-accent)', fontSize: '2.2em', marginBottom: '10px' }}>Game Over!</h1>
      <p style={{ fontSize: '1.1em', opacity: 0.9, marginBottom: '25px' }}>Thanks for playing!</p>

      {data.winner_team && (
        <div style={{
          background: 'rgba(255,215,0,0.15)',
          border: '2px solid rgba(255,215,0,0.4)',
          borderRadius: '12px',
          padding: '20px',
          marginBottom: '25px',
        }}>
          <div style={{ fontSize: '0.9em', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.7, marginBottom: '8px' }}>
            Winner
          </div>
          <div style={{ fontSize: '1.6em', fontWeight: 'bold', color: 'var(--text-accent)' }}>
            {data.winner_team}
          </div>
          <div style={{ fontSize: '1.1em', marginTop: '5px' }}>
            {data.winner_score} points
          </div>
        </div>
      )}

      {data.leaderboard && data.leaderboard.length > 0 && (
        <div style={{ textAlign: 'left' }}>
          <h3 style={{ textAlign: 'center', marginBottom: '12px', color: 'var(--text-accent)' }}>Final Standings</h3>
          {data.leaderboard.map(entry => (
            <div key={entry.team_name} style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '8px 12px',
              marginBottom: '4px',
              background: 'rgba(255,255,255,0.05)',
              borderRadius: '8px',
            }}>
              <span>{getMedal(entry.rank)} {entry.team_name}</span>
              <span style={{ fontWeight: 'bold' }}>{entry.total_score}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
