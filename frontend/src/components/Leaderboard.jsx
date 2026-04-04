import React from 'react';

function getRankStyle(i) {
  if (i === 0) return { background: 'rgba(255,215,0,0.25)', color: '#ffd700', border: '1px solid rgba(255,215,0,0.4)' };
  if (i === 1) return { background: 'rgba(192,192,192,0.2)', color: '#c0c0c0', border: '1px solid rgba(192,192,192,0.3)' };
  if (i === 2) return { background: 'rgba(205,127,50,0.2)', color: '#cd7f32', border: '1px solid rgba(205,127,50,0.3)' };
  return { background: 'color-mix(in srgb, var(--text-muted) 15%, transparent)', color: 'var(--text-muted)', border: '1px solid var(--card-border)' };
}

export default function Leaderboard({ leaderboard, teamName, mobileExperience, scoresRevealed }) {
  if (!leaderboard || leaderboard.length === 0) return null;

  const hideScores = mobileExperience === 'advanced_pp' && !scoresRevealed;

  return (
    <div style={{ marginTop: '15px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '12px' }}>
        <span style={{ fontSize: '1.1em', fontWeight: 'bold', color: 'var(--text, #fff)' }}>Leaderboard</span>
        <span style={{ fontSize: '0.7em', padding: '2px 8px', background: 'rgba(76,175,80,0.25)', color: '#4caf50', border: '1px solid rgba(76,175,80,0.4)', borderRadius: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Live</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {leaderboard.map((entry, i) => {
          const isYou = entry.team_name === teamName || entry.is_you;
          let scoreDisplay;
          if (entry.pending) scoreDisplay = '\u231B';
          else if (hideScores) scoreDisplay = '???';
          else scoreDisplay = entry.total_score;

          return (
            <div
              key={entry.team_name}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '10px 12px',
                borderRadius: '8px',
                transition: 'all 0.5s ease',
                background: isYou ? 'rgba(76,175,80,0.15)' : 'color-mix(in srgb, var(--accent) 8%, transparent)',
                border: isYou ? '1px solid rgba(76,175,80,0.3)' : '1px solid var(--card-border)',
              }}
            >
              <span style={{
                minWidth: '28px', height: '28px', display: 'flex', alignItems: 'center',
                justifyContent: 'center', borderRadius: '50%', fontWeight: 'bold',
                fontSize: '0.85em', flexShrink: 0, ...getRankStyle(i),
              }}>
                {entry.rank}
              </span>
              <span style={{
                flex: 1, marginLeft: '10px',
                color: isYou ? '#4caf50' : 'var(--text)',
                fontSize: '0.95em', fontWeight: isYou ? 'bold' : 'normal',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {isYou ? `${entry.team_name} (You)` : entry.team_name}
              </span>
              <span style={{
                fontWeight: 'bold',
                color: hideScores ? '#ffd700' : (isYou ? '#4caf50' : 'var(--text)'),
                fontSize: '1em', marginLeft: '8px',
              }}>
                {scoreDisplay}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
