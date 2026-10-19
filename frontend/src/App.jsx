import { useState } from 'react'
import './App.css'
import Dashboard from './pages/Dashboard'
import EvaluationResults from './pages/EvaluationResults'
import {TestEvaluationPage} from './pages/testEvaluation'

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')
  const [selectedQuestion, setSelectedQuestion] = useState(null)
  const [evalData, setEvalData] = useState(null);
  const [schemaExt, setSchemaExt] = useState(null);
  const [studentExt, setStudentExt] = useState(null);

  const handleViewResults = (questionId, report, schema, student) => {
    setSelectedQuestion(questionId)
    setEvalData(report); // Result from POST /evaluate/{qid}
    setSchemaExt(schema); // Result from POST /schema/upload
    setStudentExt(student); // Result from POST /student/upload
    setCurrentPage('results')
  }

  const handleBackToDashboard = () => {
    setCurrentPage('dashboard')
    setSelectedQuestion(null)
    setEvalData(null)
    setSchemaExt(null)
    setStudentExt(null)
  }

  return (
    <div className="app">
      <nav className="navbar">
        <div className="nav-container">
          <div className="nav-brand">
            <h1 className="nav-title">ExamEval</h1>
            <p className="nav-subtitle">Automated Answer Evaluation</p>
          </div>
          <div className="nav-links">
            <button
              className={`nav-link ${currentPage === 'dashboard' ? 'active' : ''}`}
              onClick={handleBackToDashboard}
            >
              Dashboard
            </button>
            <button
              className={`nav-link ${currentPage === 'test' ? 'active' : ''}`}
              onClick={() => setCurrentPage('test')}
              >
                Run Tests
            </button>
          </div>
        </div>
      </nav>

      <main className="main-content">
        {currentPage === 'dashboard' && (
          <Dashboard onViewResults={handleViewResults} />
        )}
        {currentPage === 'test' && (
          <TestEvaluationPage/>
        )}
        {currentPage === 'results' && selectedQuestion && (
          <EvaluationResults
            questionId={selectedQuestion}
            evaluationData={evalData}
            schemaExtraction={schemaExt}
            studentExtraction={studentExt}
            onBack={handleBackToDashboard}
          />
        )}
      </main>
    </div>
  )
}

export default App
