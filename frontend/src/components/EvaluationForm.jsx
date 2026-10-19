import { useState } from 'react'
import { evaluateAnswer } from '../api'
import '../styles/EvaluationForm.css'

function EvaluationForm({ questionId, onEvaluationComplete }) {
  const [studentId, setStudentId] = useState('')
  const [skipLlm, setSkipLlm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (!studentId.trim()) {
      setError('Please enter a student ID to evaluate')
      return
    }

    try {
      setLoading(true)
      const response = await evaluateAnswer(questionId, studentId, skipLlm)
      if(onEvaluationComplete)
        onEvaluationComplete(response)
      setStudentId('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="eval-form">
      <div className="form-card">
        <h3>Step 4: Evaluate Answer</h3>
        <p className="form-description">Run the evaluation pipeline on the student's answer</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="evalStudentId">Student ID</label>
            <input
              id="evalStudentId"
              type="text"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              placeholder="Enter the student ID to evaluate"
              disabled={loading}
            />
          </div>

          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                checked={skipLlm}
                onChange={(e) => setSkipLlm(e.target.checked)}
                disabled={loading}
              />
              <span>Skip LLM Judge (saves API quota)</span>
            </label>
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Evaluating...' : 'Start Evaluation'}
          </button>
        </form>

        <div className="eval-info">
          <h4>Evaluation Metrics</h4>
          <ul>
            <li><strong>Exact Match</strong>: Node and edge matching</li>
            <li><strong>Semantic</strong>: Semantic similarity analysis</li>
            <li><strong>Graph Structure</strong>: Weisfeiler-Leman kernel & GED</li>
            <li><strong>LLM Judge</strong>: Advanced reasoning assessment</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default EvaluationForm
