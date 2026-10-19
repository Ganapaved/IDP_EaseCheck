import { useState } from 'react'
import SubjectForm from '../components/SubjectForm'
import SchemaUpload from '../components/SchemaUpload'
import StudentUpload from '../components/StudentUpload'
import EvaluationForm from '../components/EvaluationForm'
import QuestionsList from '../components/QuestionsList'
import '../styles/Dashboard.css'



function Dashboard({ onViewResults }) {
  const [questions, setQuestions] = useState([])
  const [activeStep, setActiveStep] = useState('select-subject')
  const [selectedQuestion, setSelectedQuestion] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [schemaExt, setSchemaExt] = useState(null);
  const [studentExt, setStudentExt] = useState(null);

  const handleQuestionRegistered = (questionId, subject) => {
    setSelectedQuestion({ id: questionId, subject })
    setQuestions(prev => [
      ...prev,
      { id: questionId, subject, status: 'registered' }
    ])
    setActiveStep('upload-schema')
    setMessage({ type: 'success', text: `Question "${questionId}" registered as ${subject.toUpperCase()}` })
    setTimeout(() => setMessage(null), 4000)
  }

  const handleSchemaUploaded = (data) => {
    if(data?.extracted) setSchemaExt(data.extracted)
    setActiveStep('upload-student')
    setMessage({ type: 'success', text: 'Schema uploaded successfully' })
    setTimeout(() => setMessage(null), 4000)
  }

  const handleStudentUploaded = (data) => {
    if (data?.extracted) setStudentExt(data.extracted);
    setActiveStep('evaluate')
    setMessage({ type: 'success', text: 'Student answer uploaded successfully' })
    setTimeout(() => setMessage(null), 4000)
  }

  const handleEvaluationComplete = (questionId,evaluationReport) => {
    setQuestions(prev =>
      prev.map(q =>
        q.id === questionId ? { ...q, status: 'evaluated' } : q
      )
    )
    setMessage({ type: 'success', text: 'Evaluation complete!' })
    setTimeout(() => setMessage(null), 4000)
    onViewResults(questionId, evaluationReport, schemaExt, studentExt);
  }

  const handleStartNew = () => {
    setActiveStep('select-subject')
    setSelectedQuestion(null)
    setMessage(null)
  }

  return (
    <div className="dashboard">
      <div className="dashboard-container">
        <div className="dashboard-header">
          <h2>Answer Evaluation System</h2>
          <p>Automated assessment using knowledge graphs and LLM analysis</p>
        </div>

        {message && (
          <div className={`message message-${message.type}`}>
            {message.text}
          </div>
        )}

        <div className="workflow-container">
          <div className="steps-indicator">
            <div className={`step ${activeStep === 'select-subject' ? 'active' : ''}`}>
              <div className="step-number">1</div>
              <div className="step-label">Select Subject</div>
            </div>
            <div className="step-connector"></div>
            <div className={`step ${activeStep === 'upload-schema' ? 'active' : ''}`}>
              <div className="step-number">2</div>
              <div className="step-label">Upload Schema</div>
            </div>
            <div className="step-connector"></div>
            <div className={`step ${activeStep === 'upload-student' ? 'active' : ''}`}>
              <div className="step-number">3</div>
              <div className="step-label">Upload Student</div>
            </div>
            <div className="step-connector"></div>
            <div className={`step ${activeStep === 'evaluate' ? 'active' : ''}`}>
              <div className="step-number">4</div>
              <div className="step-label">Evaluate</div>
            </div>
          </div>

          <div className="forms-container">
            {activeStep === 'select-subject' && (
              <SubjectForm onQuestionRegistered={handleQuestionRegistered} />
            )}

            {activeStep === 'upload-schema' && selectedQuestion && (
              <>
                <SchemaUpload
                  questionId={selectedQuestion.id}
                  onUploaded={handleSchemaUploaded}
                />
                <button className="btn-secondary" onClick={handleStartNew}>
                  Start New Question
                </button>
              </>
            )}

            {activeStep === 'upload-student' && selectedQuestion && (
              <>
                <StudentUpload
                  questionId={selectedQuestion.id}
                  onUploaded={handleStudentUploaded}
                />
                <button className="btn-secondary" onClick={handleStartNew}>
                  Start New Question
                </button>
              </>
            )}

            {activeStep === 'evaluate' && selectedQuestion && (
              <>
                <EvaluationForm
                  questionId={selectedQuestion.id}
                  onEvaluationComplete={(report) => {
                    handleEvaluationComplete(selectedQuestion.id,report)
                    
                  }}
                />
                <button className="btn-secondary" onClick={handleStartNew}>
                  Start New Question
                </button>
              </>
            )}
          </div>
        </div>

        {questions.length > 0 && (
          <QuestionsList
            questions={questions}
            onViewResults={(qid) => onViewResults(qid, null, null, null)}
          />
        )}
      </div>
    </div>
  )
}

export default Dashboard
