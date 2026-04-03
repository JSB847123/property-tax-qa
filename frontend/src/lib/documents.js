export function createEmptyDocumentForm() {
  return {
    category: 'civil',
    title: '',
    source: '',
    date: new Date().toISOString().slice(0, 10),
    content: '',
    practical: '',
    tagText: '',
  }
}

export function documentToForm(document) {
  return {
    category: document.category || 'civil',
    title: document.title || '',
    source: document.source || '',
    date: document.date || new Date().toISOString().slice(0, 10),
    content: document.content || '',
    practical: document.practical || '',
    tagText: Array.isArray(document.tags) ? document.tags.join('; ') : '',
  }
}

export function formToPayload(form) {
  return {
    category: form.category,
    title: form.title.trim(),
    source: form.source.trim(),
    date: form.date,
    content: form.content.trim(),
    practical: form.practical.trim() || null,
    tags: form.tagText
      .split(/[;,]/)
      .map((item) => item.trim())
      .filter(Boolean),
    is_private: true,
  }
}

export function summarizeText(value, limit = 170) {
  const text = (value || '').replace(/\s+/g, ' ').trim()
  if (text.length <= limit) {
    return text
  }
  return `${text.slice(0, limit - 1)}…`
}
