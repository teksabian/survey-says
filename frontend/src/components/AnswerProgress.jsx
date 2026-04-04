export default function AnswerProgress({ filled, total }) {
  const pct = total > 0 ? (filled / total * 100) : 0
  const isComplete = filled === total && total > 0

  return (
    <div className="answer-progress" id="answerProgress">
      <span>{filled} of {total} answers</span>
      <div className="answer-progress-bar">
        <div
          className={`answer-progress-fill${isComplete ? ' complete' : ''}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
