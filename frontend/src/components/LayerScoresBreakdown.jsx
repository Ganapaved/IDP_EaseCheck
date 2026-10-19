import '../styles/LayerScoresBreakdown.css'

function LayerScoresBreakdown({ scores }) {
  if (!scores) return null

  const layers = [
    { key: 'formula_exact', label: 'Formula Exact', color: '#3498db' },
    { key: 'symbolic', label: 'Symbolic', color: '#9b59b6' },
    { key: 'step_order', label: 'Step Order', color: '#e74c3c' },
    { key: 'llm_judge', label: 'LLM Judge', color: '#27ae60' },
    { key: 'exact_match', label: 'Exact Match', color: '#3498db' },
    { key: 'semantic', label: 'Semantic', color: '#9b59b6' },
    { key: 'graph_structure', label: 'Graph Structure', color: '#e74c3c' },
  ]

  const visibleLayers = layers.filter(l => scores[l.key] !== undefined)

  return (
    <div className="layer-scores-breakdown">
      <h4>Score Breakdown by Layer</h4>
      <div className="layers-list">
        {visibleLayers.map(layer => (
          <div key={layer.key} className="layer-item">
            <div className="layer-header">
              <span className="layer-name">{layer.label}</span>
              <span className="layer-score">{scores[layer.key]?.toFixed(2) || 0}%</span>
            </div>
            <div className="layer-bar">
              <div
                className="layer-progress"
                style={{
                  width: `${scores[layer.key] || 0}%`,
                  backgroundColor: layer.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default LayerScoresBreakdown
