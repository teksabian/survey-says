import { useEffect } from 'react'

export default function GameOver({ data }) {
  useEffect(() => {
    if (typeof window.confetti === 'function') {
      window.confetti({ particleCount: 150, spread: 70, origin: { y: 0.6 } })
      setTimeout(() => {
        window.confetti({ particleCount: 80, spread: 100, origin: { y: 0.5 } })
      }, 400)
      setTimeout(() => {
        window.confetti({ particleCount: 100, spread: 120, origin: { y: 0.4 } })
      }, 800)
    }
  }, [])

  if (!data) return null

  const getMedal = (rank) => {
    if (rank === 1) return '🥇'
    if (rank === 2) return '🥈'
    if (rank === 3) return '🥉'
    return `${rank}.`
  }

  return (
    <div className="game-over-screen">
      <h1>Game Over!</h1>
      <p className="game-over-subtitle">Thanks for playing!</p>

      {data.winner_team && (
        <div className="game-over-winner">
          <div className="game-over-winner-label">Winner</div>
          <div className="game-over-winner-name">{data.winner_team}</div>
          <div className="game-over-winner-score">{data.winner_score} points</div>
        </div>
      )}

      {data.leaderboard && data.leaderboard.length > 0 && (
        <div className="game-over-standings" style={{ textAlign: 'left' }}>
          <h3>Final Standings</h3>
          {data.leaderboard.map((entry) => (
            <div key={entry.team_name} className="game-over-standing-row">
              <span>{getMedal(entry.rank)} {entry.team_name}</span>
              <span>{entry.total_score}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
