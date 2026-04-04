import React from 'react';
import Leaderboard from './Leaderboard';

export default function RoundClosedView({ roundNum, leaderboard, teamName, mobileExperience, scoresRevealed }) {
  return (
    <div className="container">
      <div className="card">
        <div className="waiting">
          <h2>{'\u23F0'} Round {roundNum} Has Ended</h2>
          <div className="loading"></div>
          <p>Submissions are closed for this round.</p>
          <p>Wait for the next round to begin!</p>
          <div className="warning" style={{ marginTop: '20px' }}>
            {'\u26A0\uFE0F'} Do not manually refresh the page
          </div>
          <p style={{ fontSize: '0.85em', opacity: 0.8, marginTop: '10px' }}>This page refreshes automatically...</p>
        </div>

        {mobileExperience !== 'basic' && (
          <Leaderboard
            leaderboard={leaderboard}
            teamName={teamName}
            mobileExperience={mobileExperience}
            scoresRevealed={scoresRevealed}
          />
        )}
      </div>
    </div>
  );
}
