import '../styles/QuestionsList.css'

function QuestionsList({ questions, onViewResults }) {
  return (
    <div className="questions-list-container">
      <h3>Questions History</h3>
      <div className="questions-grid">
        {questions.map(question => (
          <div key={question.id} className={`question-item status-${question.status}`}>
            <div className="question-content">
              <h4>{question.id}</h4>
              <p className="subject-badge">{question.subject.toUpperCase()}</p>
              <p className="status-text">
                {question.status === 'registered' && 'Registered'}
                {question.status === 'evaluated' && 'Evaluated'}
              </p>
            </div>
            {question.status === 'evaluated' && (
              <button
                className="btn-view-results"
                onClick={() => onViewResults(question.id)}
              >
                View Results
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default QuestionsList
