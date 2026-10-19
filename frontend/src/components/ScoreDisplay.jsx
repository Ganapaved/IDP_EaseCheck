import './ScoreDisplay.css'

function ScoreDisplay({ score }) {
  const getScoreColor = (s) => {
    if (s >= 80) return '#27ae60'
    if (s >= 60) return '#f39c12'
    if (s >= 40) return '#e67e22'
    return '#e74c3c'
  }

  const getScoreBand = (s) => {
    if (s >= 80) return 'Excellent'
    if (s >= 60) return 'Good'
    if (s >= 40) return 'Fair'
    return 'Needs Improvement'
  }

  const circumference = 2 * Math.PI * 45
  const offset = circumference - (score / 100) * circumference

  return (
    <div className="score-display">
      <div className="score-circle">
        <svg width="120" height="120" viewBox="0 0 120 120">
          <circle
            cx="60"
            cy="60"
            r="45"
            fill="none"
            stroke="#ecf0f1"
            strokeWidth="8"
          />
          <circle
            cx="60"
            cy="60"
            r="45"
            fill="none"
            stroke={getScoreColor(score)}
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.5s ease' }}
            transform="rotate(-90 60 60)"
          />
          <text
            x="60"
            y="65"
            textAnchor="middle"
            fontSize="32"
            fontWeight="bold"
            fill={getScoreColor(score)}
          >
            {Math.round(score)}
          </text>
        </svg>
      </div>
      <div className="score-info">
        <div className="score-value">{score.toFixed(2)}/100</div>
        <div className="score-band" style={{ color: getScoreColor(score) }}>
          {getScoreBand(score)}
        </div>
      </div>
    </div>
  )
}

export default ScoreDisplay
