const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const config = {
    method: 'GET',
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers || {}),
    },
  }

  const response = await fetch(`${API_BASE_URL}${path}`, config)
  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json() : await response.text()

  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null ? payload.detail : payload
    throw new Error(typeof detail === 'string' ? detail : '요청 처리 중 오류가 발생했습니다.')
  }

  return payload
}

export async function fetchDocumentStats() {
  return request('/api/documents/stats')
}

export async function fetchDocuments({ category, search, page = 1, pageSize = 8 }) {
  const params = new URLSearchParams()
  if (category) params.set('category', category)
  if (search) params.set('search', search)
  params.set('page', String(page))
  params.set('page_size', String(pageSize))
  return request(`/api/documents?${params.toString()}`)
}

export async function createDocument(payload) {
  return request('/api/documents', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateDocument(id, payload) {
  return request(`/api/documents/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteDocument(id) {
  return request(`/api/documents/${id}`, {
    method: 'DELETE',
  })
}

export async function uploadBulkCsv(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request('/api/documents/bulk', {
    method: 'POST',
    body: formData,
  })
}

export async function sendChat(payload) {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function integratedSearch({ query, category, source = 'all' }) {
  const params = new URLSearchParams({ q: query, source })
  if (category) params.set('category', category)
  return request(`/api/search?${params.toString()}`)
}

export async function fetchFavorites() {
  return request('/api/favorites')
}

export async function createFavorite(payload) {
  return request('/api/favorites', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteFavorite(favoriteId) {
  return request(`/api/favorites/${favoriteId}`, {
    method: 'DELETE',
  })
}

export async function fetchSettingsStatus() {
  return request('/api/settings')
}

export async function saveCredentials(payload) {
  return request('/api/settings/credentials', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function clearSessionSettings() {
  return request('/api/settings/session', {
    method: 'DELETE',
  })
}

export { API_BASE_URL }
