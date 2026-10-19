import { useState } from 'react'
import { uploadStudent } from '../api'
import '../styles/StudentUpload.css'

function StudentUpload({ questionId, onUploaded }) {
  const [studentId, setStudentId] = useState('')
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

    if (!studentId.trim()) {
      setError('Please enter a student ID')
      return
    }

    if (!image && !extraText.trim()) {
      setError('Please provide at least an image or text content')
      return
    }

    try {
      setLoading(true)
      const response = await uploadStudent(questionId, studentId, image, extraText)
      if(onUploaded){
        onUploaded(response)
      }
      setStudentId('')
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
        <h3>Step 3: Upload Student Answer</h3>
        <p className="form-description">Upload the student's answer for evaluation</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="studentId">Student ID</label>
            <input
              id="studentId"
              type="text"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              placeholder="e.g., STU001"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <div className="file-input-wrapper">
              <input
                id="student-image"
                type="file"
                onChange={handleImageChange}
                accept="image/*"
                disabled={loading}
              />
              <label htmlFor="student-image" className="file-input-label">
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
              placeholder="Enter the student's answer in text or LaTeX format..."
              disabled={loading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Uploading...' : 'Upload Student Answer'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default StudentUpload
