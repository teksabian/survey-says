import { useEffect } from 'react'

export default function WinnerInterstitial({ data }) {
  useEffect(() => {
    if (typeof window.confetti === 'function') {
      window.confetti({ particleCount: 150, spread: 70, origin: { y: 0.6 } })
      setTimeout(() => {
        window.confetti({ particleCount: 80, spread: 100, origin: { y: 0.5 } })
      }, 400)
    }
  }, [])

  if (!data) return null

  const { teamName, score, roundNum, question, answers, wonOnTiebreaker, tiebreakerAnswer, hideDetails } = data

  return (
    <div className="container">
      <div className="card">
        <div className="winner-interstitial show">
          <div className="winner-trophy">🏆</div>
          <div className="winner-round-label">Round {roundNum}</div>
          <div className="winner-heading">WINNER</div>
          <div className="winner-name">{teamName}</div>

          {!hideDetails && (
            <div className="winner-score"><span>{score}</span> Points</div>
          )}

          {!hideDetails && wonOnTiebreaker && (
            <div className="winner-tiebreaker">Won on Tiebreaker!</div>
          )}

          {!hideDetails && question && answers && answers.length > 0 && (
            <div className="winner-answers">
              <div className="winner-answers-question">{question}</div>
              <ol>
                {answers.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ol>
              {tiebreakerAnswer != null && (
                <div className="winner-tiebreaker-answer">
                  Tiebreaker: <span>{tiebreakerAnswer}</span>
                </div>
              )}
            </div>
          )}

          <button className="winner-next-btn" onClick={() => { window.location.href = '/play' }}>
            Next Round &rarr;
          </button>
        </div>
      </div>
    </div>
  )
}
