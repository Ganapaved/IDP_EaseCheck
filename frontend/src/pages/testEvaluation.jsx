// testEvaluation.jsx
import React from 'react';
import EvaluationResults from './EvaluationResults'; // Ensure path is correct
import { mockevaluation, mockmath,mocktocext,mocktoceval,mocktoc2 } from './mockdata';

export function TestEvaluationPage() {
  const handleBack = () => {
    alert("Back button clicked successfully!");
  };

  return (
    <div style={{ background: '#f0f2f5', minHeight: '100vh', padding: '20px' }}>
      <div style={{ marginBottom: '15px', padding: '10px', background: '#fff3cd', border: '1px solid #ffeeba', borderRadius: '4px', textAlign: 'center' }}>
        <strong>Development Mode:</strong> Rendering UI with static JSON caches.
      </div>
      
      <EvaluationResults 
        questionId="TOC_Q1_TEST"
        evaluationData={mocktoc2}
        schemaExtraction={mocktocext}  // Populates the Student Tab (Reuse mock to check formatting)
        studentExtraction={mockmath}
        onBack={handleBack}
      />
    </div>
  );
}

