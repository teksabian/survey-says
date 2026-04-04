import React from 'react';
import Leaderboard from './Leaderboard';

export default function WaitingView({ leaderboard, teamName, mobileExperience, scoresRevealed }) {
  return (
    <div className="container">
      <div className="card">
        <div className="waiting">
          <h2>{'\u23F3'} Waiting for the Round to Start</h2>
          <div className="loading"></div>
          <p>The host will start the next round soon.</p>
          <div className="warning">
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
