const API_BASE = 'http://localhost:8000'

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || `Request failed: ${response.status}`)
  }
  return response.json()
}

function formData(data) {
  const fd = new FormData()
  for (const [key, value] of Object.entries(data)) {
    if (value !== undefined && value !== null && value !== '') {
      fd.append(key, value)
    }
  }
  return fd
}

export function registerSubject(questionId, subject) {
  return apiFetch('/subject', {
    method: 'POST',
    body: formData({ question_id: questionId, subject }),
  })
}

export function uploadSchema(questionId, image, extraText) {
  return apiFetch('/schema/upload', {
    method: 'POST',
    body: formData({ question_id: questionId, image, extra_text: extraText }),
  })
}

export function uploadStudent(questionId, studentId, image, extraText) {
  return apiFetch('/student/upload', {
    method: 'POST',
    body: formData({ question_id: questionId, student_id: studentId, image, extra_text: extraText }),
  })
}

export function evaluateAnswer(questionId, studentId, skipLlm) {
  return apiFetch(`/evaluate/${questionId}`, {
    method: 'POST',
    body: formData({ student_id: studentId, skip_llm: skipLlm }),
  })
}

export function getResults(questionId) {
  return apiFetch(`/results/${questionId}`)
}
