export default function Leaderboard({ leaderboard, teamName, scoresRevealed, mobileExperience }) {
  if (!leaderboard || leaderboard.length === 0) return null

  const hideScores = mobileExperience === 'advanced_pp' && !scoresRevealed

  return (
    <div style={{ marginTop: '15px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '12px' }}>
        <span style={{ fontSize: '1.1em', fontWeight: 'bold', color: 'var(--text, #fff)' }}>Leaderboard</span>
        <span style={{
          fontSize: '0.7em',
          padding: '2px 8px',
          background: 'rgba(76,175,80,0.25)',
          color: '#4caf50',
          border: '1px solid rgba(76,175,80,0.4)',
          borderRadius: '10px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}>Live</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {leaderboard.map((entry, i) => {
          const isYou = entry.team_name === teamName || entry.is_you

          let scoreDisplay
          if (entry.pending) {
            scoreDisplay = '\u231B'
          } else if (hideScores) {
            scoreDisplay = '???'
          } else {
            scoreDisplay = entry.total_score
          }

          const rankClass = i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : i === 2 ? 'rank-3' : ''

          return (
            <div key={entry.team_name} className={`leaderboard-entry${isYou ? ' is-you' : ''}`}>
              <span className={`leaderboard-rank ${rankClass}`}>{entry.rank}</span>
              <span className="leaderboard-team">
                {isYou ? `${entry.team_name} (You)` : entry.team_name}
              </span>
              <span className={`leaderboard-score${hideScores ? ' hidden-score' : ''}`}>
                {scoreDisplay}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
