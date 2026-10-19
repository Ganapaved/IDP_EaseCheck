import { useState } from 'react'
import { registerSubject } from '../api'
import '../styles/SubjectForm.css'

function SubjectForm({ onQuestionRegistered }) {
  const [questionId, setQuestionId] = useState('')
  const [subject, setSubject] = useState('toc')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (!questionId.trim()) {
      setError('Please enter a question ID')
      return
    }

    try {
      setLoading(true)
      await registerSubject(questionId, subject)
      onQuestionRegistered(questionId, subject)
      setQuestionId('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="subject-form">
      <div className="form-card">
        <h3>Step 1: Select Subject</h3>
        <p className="form-description">Choose the subject type for this question</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="questionId">Question ID</label>
            <input
              id="questionId"
              type="text"
              value={questionId}
              onChange={(e) => setQuestionId(e.target.value)}
              placeholder="e.g., q1, q2_integration"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>Subject Type</label>
            <div className="subject-options">
              <label className={`option ${subject === 'toc' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="subject"
                  value="toc"
                  checked={subject === 'toc'}
                  onChange={(e) => setSubject(e.target.value)}
                  disabled={loading}
                />
                <span className="option-label">
                  <span className="option-title">Theory of Computation</span>
                  <span className="option-desc">DFA, NFA, TM, CFG, etc.</span>
                </span>
              </label>

              <label className={`option ${subject === 'math' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="subject"
                  value="math"
                  checked={subject === 'math'}
                  onChange={(e) => setSubject(e.target.value)}
                  disabled={loading}
                />
                <span className="option-label">
                  <span className="option-title">Mathematics</span>
                  <span className="option-desc">Formulas, derivatives, integrals, etc.</span>
                </span>
              </label>
            </div>
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Registering...' : 'Register Question'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default SubjectForm
