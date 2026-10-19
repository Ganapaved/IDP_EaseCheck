import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css'; 

function EvaluationResults({ 
  questionId, 
  evaluationData, 
  schemaExtraction, 
  studentExtraction, 
  onBack 
}) {
  const [activeView, setActiveView] = useState('report');

  // String sanitizer to compress stringified double backslashes for LaTeX rendering
  const formatLaTeXString = (rawStr) => {
    if (!rawStr || typeof rawStr !== 'string') return '';
    return rawStr
      .replace(/\\\\\\\\/g, '\\') 
      .replace(/\\\\/g, '\\')     
      .replace(/\\dots/g, '...')  
      .trim();
  };

  // --- SAFE FALLBACK DATA NORMALIZATION ---
  const reportData = evaluationData?.report || evaluationData || {};
  const scoreMetrics = reportData?.layer_scores || {};
  const layerDetails = reportData?.layer_details || {};

  // FIXED Unpacking Logic: Keep step variables strictly arrays or empty arrays
  const getArraySteps = (extractionObj) => {
    if (!extractionObj) return [];
    if (Array.isArray(extractionObj)) return extractionObj;
    if (Array.isArray(extractionObj.steps)) return extractionObj.steps;
    if (Array.isArray(extractionObj.extracted?.steps)) return extractionObj.extracted.steps;
    return []; // Don't return the raw object here if it's an automata dictionary
  };

  const finalSchemaSteps = getArraySteps(schemaExtraction || reportData?.schema_extraction);
  const finalStudentSteps = getArraySteps(studentExtraction || reportData?.student_extraction);

  // Helper utility to render arbitrary metadata lists (TOC feedback, strengths, weaknesses, etc.)
  const renderDynamicMetadataList = (title, dataItem, badgeColor = '#34495e') => {
    if (!dataItem || (Array.isArray(dataItem) && dataItem.length === 0)) return null;

    const items = Array.isArray(dataItem) ? dataItem : [dataItem];
    return (
      <div style={{ marginBottom: '20px', background: '#fdfefe', padding: '15px', borderRadius: '6px', borderLeft: `4px solid ${badgeColor}`, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <h4 style={{ margin: '0 0 10px 0', color: badgeColor, textTransform: 'uppercase', fontSize: '13px', letterSpacing: '0.5px' }}>{title}</h4>
        <ul style={{ margin: 0, paddingLeft: '20px', lineHeight: '1.6', color: '#2c3e50' }}>
          {items.map((item, idx) => (
            <li key={`${title}-${idx}`} style={{ marginBottom: '4px' }}>
              {typeof item === 'object' ? JSON.stringify(item) : item.toString()}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  const renderAutomatonDetails = (data) => {
    if (!data || typeof data !== 'object') return null;
    
    // Safely check inner scopes if wrapped in another payload key
    const targetData = data?.extracted || data;
    const { Q, Sigma, q0, F, delta } = targetData || {};

    // If none of these core TOC keys exist, cleanly exit without rendering empty table layouts
    if (!Q && !Sigma && !delta && !q0) return null;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '25px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
          <div style={{ background: '#f7fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <strong style={{ color: '#4a5568', fontSize: '12px', textTransform: 'uppercase' }}>States (Q)</strong>
            <div style={{ fontSize: '16px', fontWeight: 'bold', marginTop: '5px', color: '#2d3748' }}>
              {Array.isArray(Q) ? Q.join(', ') : String(Q || 'None')}
            </div>
          </div>
          <div style={{ background: '#f7fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <strong style={{ color: '#4a5568', fontSize: '12px', textTransform: 'uppercase' }}>Alphabet (Σ)</strong>
            <div style={{ fontSize: '16px', fontWeight: 'bold', marginTop: '5px', color: '#2d3748' }}>
              {Array.isArray(Sigma) ? Sigma.join(', ') : String(Sigma || 'None')}
            </div>
          </div>
          <div style={{ background: '#f7fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <strong style={{ color: '#4a5568', fontSize: '12px', textTransform: 'uppercase' }}>Start State (q₀)</strong>
            <div style={{ fontSize: '16px', fontWeight: 'bold', marginTop: '5px', color: '#2d3748' }}>
              {String(q0 || 'None')}
            </div>
          </div>
          <div style={{ background: '#f7fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <strong style={{ color: '#4a5568', fontSize: '12px', textTransform: 'uppercase' }}>Final States (F)</strong>
            <div style={{ fontSize: '16px', fontWeight: 'bold', marginTop: '5px', color: '#e53e3e' }}>
              {Array.isArray(F) ? F.join(', ') : String(F || 'None')}
            </div>
          </div>
        </div>

        {delta && typeof delta === 'object' && !Array.isArray(delta) && (
          <div style={{ border: '1px solid #e2e8f0', borderRadius: '6px', background: '#fff' }}>
            <div style={{ background: '#edf2f7', padding: '10px 15px', fontWeight: 'bold', color: '#4a5568', borderBottom: '1px solid #e2e8f0' }}>
              Transition Matrix (δ)
            </div>
            <div style={{ overflowX: 'auto', padding: '10px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                    <th style={{ padding: '8px', color: '#718096' }}>State</th>
                    <th style={{ padding: '8px', color: '#718096' }}>Input Symbol → Next State</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(delta).map(([state, paths]) => (
                    <tr key={state} style={{ borderBottom: '1px solid #edf2f7' }}>
                      <td style={{ padding: '8px', fontWeight: 'bold', color: '#2d3748' }}>{state}</td>
                      <td style={{ padding: '8px' }}>
                        {paths && typeof paths === 'object' ? (
                          Object.entries(paths).map(([symbol, targetState]) => (
                            <span key={symbol} style={{ display: 'inline-block', background: '#ebf8ff', color: '#2b6cb0', padding: '4px 8px', borderRadius: '4px', marginRight: '8px', fontSize: '13px', marginBottom: '4px' }}>
                              <strong>'{symbol}'</strong> → {String(targetState)}
                            </span>
                          ))
                        ) : (
                          <span style={{ color: '#a0aec0' }}>No transitions</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Helper utility to dynamically traverse pipeline structures recursively (layer_details)
  const renderNestedPipelineObjects = (obj) => {
    if (!obj || typeof obj !== 'object') return null;

    return Object.entries(obj).map(([key, value]) => {
      const humanReadableKey = key.replace(/_/g, ' ').toUpperCase();
      if (value === null || value === undefined) return null;

      if (Array.isArray(value)) {
        if (value.length === 0) return null;
        return (
          <div key={key} style={{ marginTop: '12px', background: '#fff', padding: '12px', borderRadius: '6px', border: '1px solid #edf2f7' }}>
            <strong style={{ color: '#e74c3c', fontSize: '13px' }}>⚠️ {humanReadableKey}:</strong>
            <ul style={{ paddingLeft: '20px', marginTop: '8px', marginBottom: 0 }}>
              {value.map((item, idx) => {
                const textVal = typeof item === 'object' ? JSON.stringify(item) : item.toString();
                const hasMath = textVal.includes('\\') || textVal.includes('$');
                return (
                  <li key={idx} style={{ marginBottom: '8px', color: '#4a5568' }}>
                    {hasMath ? (
                      <div style={{ background: '#f7fafc', padding: '6px 10px', borderRadius: '4px', display: 'inline-block', maxWidth: '100%' }}>
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                          {textVal.includes('$') ? textVal : `$$${formatLaTeXString(textVal)}$$`}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <span>{textVal}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        );
      }

      if (typeof value === 'object') {
        return (
          <div key={key} style={{ margin: '15px 0', padding: '15px', background: '#f8fafc', borderRadius: '8px', borderLeft: '4px solid #cbd5e0' }}>
            <h5 style={{ margin: '0 0 10px 0', color: '#4a5568', fontSize: '14px' }}>{humanReadableKey}</h5>
            {renderNestedPipelineObjects(value)}
          </div>
        );
      }

      return (
        <div key={key} style={{ display: 'inline-block', marginRight: '20px', marginBottom: '10px', background: '#edf2f7', padding: '6px 12px', borderRadius: '20px', fontSize: '13px', color: '#2d3748' }}>
          <strong>{humanReadableKey}:</strong> {value.toString()}
        </div>
      );
    });
  };

  return (
    <div className="evaluation-results-page" style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto', fontFamily: 'sans-serif', backgroundColor: '#f7fafc', minHeight: '100vh' }}>
      
      {/* Header Actions Area */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <button onClick={onBack} style={{ padding: '10px 16px', cursor: 'pointer', borderRadius: '4px', border: '1px solid #cbd5e0', background: '#fff', fontWeight: '500', color: '#4a5568' }}>
          ← Back to Dashboard
        </button>
        <h2 style={{ margin: 0, color: '#2d3748', fontSize: '22px' }}>Evaluation Details: {questionId}</h2>
        <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2d3748' }}>
          Final Score: <span style={{ color: '#27ae60' }}>{reportData?.final_score ?? '0'}%</span>
        </div>
      </div>

      {/* Navigation View Tabs */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '25px', borderBottom: '2px solid #e2e8f0', paddingBottom: '10px' }}>
        <button 
          onClick={() => setActiveView('report')} 
          style={{
            padding: '10px 20px', fontSize: '15px', cursor: 'pointer', border: 'none', borderRadius: '4px', fontWeight: '500',
            backgroundColor: activeView === 'report' ? '#3182ce' : '#edf2f7', color: activeView === 'report' ? '#fff' : '#4a5568'
          }}
        >
          📊 Comprehensive Evaluation Report
        </button>
        <button 
          onClick={() => setActiveView('schema')} 
          style={{
            padding: '10px 20px', fontSize: '15px', cursor: 'pointer', border: 'none', borderRadius: '4px', fontWeight: '500',
            backgroundColor: activeView === 'schema' ? '#dd6b20' : '#edf2f7', color: activeView === 'schema' ? '#fff' : '#4a5568'
          }}
        >
          🔑 Master Schema Extraction
        </button>
        <button 
          onClick={() => setActiveView('student')} 
          style={{
            padding: '10px 20px', fontSize: '15px', cursor: 'pointer', border: 'none', borderRadius: '4px', fontWeight: '500',
            backgroundColor: activeView === 'student' ? '#38a169' : '#edf2f7', color: activeView === 'student' ? '#fff' : '#4a5568'
          }}
        >
          📝 Student Submission Extraction
        </button>
      </div>

      {/* Main Panel Content Display */}
      <div style={{ background: '#fff', padding: '25px', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
        
        {/* TAB 1: DYNAMIC REPORT PACKAGES */}
        {activeView === 'report' && (
          <div>
            <h3 style={{ marginTop: 0, marginBottom: '20px', color: '#2d3748' }}>Pipeline Analytics Summary</h3>
            
            {Object.keys(scoreMetrics).length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '15px', marginBottom: '30px' }}>
                {Object.entries(scoreMetrics).map(([key, val]) => (
                  <div key={key} style={{ padding: '15px', background: '#f7fafc', borderRadius: '6px', textAlign: 'center', borderTop: '4px solid #3182ce', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
                    <div style={{ fontSize: '11px', color: '#718096', textTransform: 'uppercase', fontWeight: 'bold' }}>{key.replace(/_/g, ' ')}</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', marginTop: '5px', color: '#2d3748' }}>{val ?? 0}%</div>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: '#718096', fontStyle: 'italic' }}>No score tracking matrix provided by pipeline modules.</p>
            )}

            {reportData?.llm_feedback && (
              <div style={{ background: '#ebf8ff', padding: '15px', borderRadius: '6px', marginBottom: '25px', borderLeft: '4px solid #3182ce' }}>
                <h4 style={{ margin: '0 0 8px 0', color: '#2b6cb0' }}>AI Qualitative Reasoning Assessment</h4>
                <p style={{ margin: 0, fontStyle: 'italic', color: '#2d3748', lineHeight: '1.5' }}>"{reportData.llm_feedback}"</p>
              </div>
            )}

            {renderDynamicMetadataList('Pipeline Engine Feedback logs', reportData?.feedback, '#3182ce')}
            {renderDynamicMetadataList('Student Demonstration Strengths', reportData?.strengths, '#38a169')}
            {renderDynamicMetadataList('Identified Concepts / Structural Weaknesses', reportData?.weaknesses, '#e53e3e')}

            {Object.keys(layerDetails).length > 0 && (
              <div style={{ marginTop: '30px' }}>
                <h4 style={{ borderBottom: '2px solid #edf2f7', paddingBottom: '8px', color: '#4a5568' }}>Structural Integrity Traces</h4>
                {renderNestedPipelineObjects(layerDetails)}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: MASTER SCHEMA EXTRACTION PANEL */}
        {activeView === 'schema' && (
          <div>
            <h3 style={{ marginTop: 0, color: '#2d3748' }}>Master Target Structural Profiles</h3>
            <p style={{ color: '#718096', fontSize: '14px', marginBottom: '20px' }}>Ground truth token execution map parsed from the instructor reference script.</p>
            
            {/* Renders Automaton Tables safely if data is present */}
            {renderAutomatonDetails(schemaExtraction)} 

            {/* Renders Mathematics steps if array data is present */}
            {finalSchemaSteps.length > 0 ? (
              finalSchemaSteps.map((card, idx) => (
                <div key={card.step || idx} style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '15px', marginBottom: '15px', background: '#f7fafc' }}>
                  <h5 style={{ margin: '0 0 10px 0', fontSize: '15px', color: '#dd6b20' }}>Reference Profile Element Step {card.step ?? (idx + 1)}</h5>
                  <div style={{ background: '#fff', padding: '12px', borderRadius: '4px', border: '1px solid #e2e8f0', overflowX: 'auto' }}>
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                      {formatLaTeXString(card.content || (typeof card === 'string' ? card : JSON.stringify(card)))}
                    </ReactMarkdown>
                  </div>
                </div>
              ))
            ) : (!schemaExtraction?.Q && !schemaExtraction?.extracted?.Q && (
              <div style={{ textAlign: 'center', padding: '40px', color: '#a0aec0', border: '2px dashed #e2e8f0', borderRadius: '6px' }}>
                No active derivation steps or reference items found for this evaluation run.
              </div>
            ))}
          </div>
        )}

        {/* TAB 3: STUDENT ANSWER SHEET EXTRACTION PANEL */}
        {activeView === 'student' && (
          <div>
            <h3 style={{ marginTop: 0, color: '#2d3748' }}>Student Submission Extraction Maps</h3>
            <p style={{ color: '#718096', fontSize: '14px', marginBottom: '20px' }}>Structural execution tokens extracted directly from the student target layout script.</p>
            
            {/* Renders Automaton Tables safely if data is present */}
            {renderAutomatonDetails(studentExtraction)}

            {/* Renders Mathematics steps if array data is present */}
            {finalStudentSteps.length > 0 ? (
              finalStudentSteps.map((card, idx) => (
                <div key={card.step || idx} style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '15px', marginBottom: '15px', background: '#f7fafc' }}>
                  <h5 style={{ margin: '0 0 10px 0', fontSize: '15px', color: '#38a169' }}>Student Submission Element Step {card.step ?? (idx + 1)}</h5>
                  <div style={{ background: '#fff', padding: '12px', borderRadius: '4px', border: '1px solid #e2e8f0', overflowX: 'auto' }}>
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                      {formatLaTeXString(card.content || (typeof card === 'string' ? card : JSON.stringify(card)))}
                    </ReactMarkdown>
                  </div>
                </div>
              ))
            ) : (!studentExtraction?.Q && !studentExtraction?.extracted?.Q && (
              <div style={{ textAlign: 'center', padding: '40px', color: '#a0aec0', border: '2px dashed #e2e8f0', borderRadius: '6px' }}>
                No active derivation steps or reference items found for this student run.
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}

export default EvaluationResults;