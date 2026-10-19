import { useState } from 'react'
import '../styles/FeedbackPanel.css'

function FeedbackPanel({ feedback, llmFeedback, correctSteps, wrongSteps, strengths }) {
  const [expandedSection, setExpandedSection] = useState('llm')

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  return (
    <div className="feedback-panel">
      <h4>Detailed Feedback</h4>

      {llmFeedback && (
        <div className={`feedback-section ${expandedSection === 'llm' ? 'expanded' : ''}`}>
          <button
            className="section-header"
            onClick={() => toggleSection('llm')}
          >
            <span className="section-title">LLM Assessment</span>
            <span className="toggle-icon">{expandedSection === 'llm' ? '−' : '+'}</span>
          </button>
          {expandedSection === 'llm' && (
            <div className="section-content">
              <p>{llmFeedback}</p>
            </div>
          )}
        </div>
      )}

      {feedback && feedback.length > 0 && (
        <div className={`feedback-section ${expandedSection === 'feedback' ? 'expanded' : ''}`}>
          <button
            className="section-header"
            onClick={() => toggleSection('feedback')}
          >
            <span className="section-title">Feedback Items</span>
            <span className="toggle-icon">{expandedSection === 'feedback' ? '−' : '+'}</span>
          </button>
          {expandedSection === 'feedback' && (
            <div className="section-content">
              <ul>
                {feedback.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {correctSteps && correctSteps.length > 0 && (
        <div className={`feedback-section success ${expandedSection === 'correct' ? 'expanded' : ''}`}>
          <button
            className="section-header"
            onClick={() => toggleSection('correct')}
          >
            <span className="section-title">Correct Steps</span>
            <span className="toggle-icon">{expandedSection === 'correct' ? '−' : '+'}</span>
          </button>
          {expandedSection === 'correct' && (
            <div className="section-content">
              <ul>
                {correctSteps.map((step, idx) => (
                  <li key={idx} className="check-mark">{step}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {wrongSteps && wrongSteps.length > 0 && (
        <div className={`feedback-section error ${expandedSection === 'wrong' ? 'expanded' : ''}`}>
          <button
            className="section-header"
            onClick={() => toggleSection('wrong')}
          >
            <span className="section-title">Incorrect Steps</span>
            <span className="toggle-icon">{expandedSection === 'wrong' ? '−' : '+'}</span>
          </button>
          {expandedSection === 'wrong' && (
            <div className="section-content">
              <ul>
                {wrongSteps.map((step, idx) => (
                  <li key={idx} className="cross-mark">{step}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {strengths && strengths.length > 0 && (
        <div className={`feedback-section info ${expandedSection === 'strengths' ? 'expanded' : ''}`}>
          <button
            className="section-header"
            onClick={() => toggleSection('strengths')}
          >
            <span className="section-title">Strengths</span>
            <span className="toggle-icon">{expandedSection === 'strengths' ? '−' : '+'}</span>
          </button>
          {expandedSection === 'strengths' && (
            <div className="section-content">
              <ul>
                {strengths.map((strength, idx) => (
                  <li key={idx}>{strength}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default FeedbackPanel
