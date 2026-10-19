import { useState } from 'react'
import { uploadSchema } from '../api'
import '../styles/SchemaUpload.css'

function SchemaUpload({ questionId, onUploaded }) {
  const [image, setImage] = useState(null)
  const [extraText, setExtraText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleImageChange = (e) => {
    setImage(e.target.files[0])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (!image && !extraText.trim()) {
      setError('Please provide at least an image or text content')
      return
    }

    try {
      setLoading(true)
      const response = await uploadSchema(questionId, image, extraText)
      if(onUploaded)
        onUploaded(response)
      setImage(null)
      setExtraText('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="upload-form">
      <div className="form-card">
        <h3>Step 2: Upload Correct Answer (Schema)</h3>
        <p className="form-description">Upload the correct answer in image or text format</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <div className="file-input-wrapper">
              <input
                id="schema-image"
                type="file"
                onChange={handleImageChange}
                accept="image/*"
                disabled={loading}
              />
              <label htmlFor="schema-image" className="file-input-label">
                {image ? image.name : 'Choose image...'}
              </label>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="extraText">Text/LaTeX Content (Optional)</label>
            <textarea
              id="extraText"
              value={extraText}
              onChange={(e) => setExtraText(e.target.value)}
              placeholder="Enter LaTeX formulas, text content, or additional information..."
              disabled={loading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Uploading...' : 'Upload Schema'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default SchemaUpload
