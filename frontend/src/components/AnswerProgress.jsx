import React from 'react';

export default function AnswerProgress({ filled, total }) {
  const pct = total > 0 ? (filled / total * 100) : 0;
  const complete = filled === total;

  return (
    <div className="answer-progress">
      <span>{filled} of {total} answers</span>
      <div className="answer-progress-bar">
        <div
          className={`answer-progress-fill${complete ? ' complete' : ''}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
