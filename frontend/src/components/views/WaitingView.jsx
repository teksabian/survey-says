import Leaderboard from '../Leaderboard'

export default function WaitingView({ teamName, mobileExperience, leaderboard, scoresRevealed }) {
  return (
    <div className="container">
      <div className="card">
        <div className="waiting">
          <h2>⏳ Waiting for the Round to Start</h2>
          <div className="loading"></div>
          <p>The host will start the next round soon.</p>
          <div className="warning">
            ⚠️ Do not manually refresh the page
          </div>
          <p style={{ fontSize: '0.85em', opacity: 0.8, marginTop: '10px' }}>
            This page refreshes automatically...
          </p>
        </div>

        {mobileExperience !== 'basic' && (
          <Leaderboard
            leaderboard={leaderboard}
            teamName={teamName}
            scoresRevealed={scoresRevealed}
            mobileExperience={mobileExperience}
          />
        )}
      </div>
    </div>
  )
}
