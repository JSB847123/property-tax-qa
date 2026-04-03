export const CHAT_HISTORY_STORAGE_KEY = 'tax-rag-recent-chat-v1'
export const MAX_RECENT_CHAT_EXCHANGES = 3

export function createWelcomeMessage() {
  return {
    id: 'welcome',
    role: 'assistant',
    answer:
      '질문을 입력하면 비공개 실무자료와 공개 법률자료를 함께 찾아서 답변합니다. "부담부증여"처럼 큰따옴표로 감싼 문구는 제목, 요약, 판시사항에 실제 포함된 자료만 우선 반영합니다.',
    sources: [],
    visibleSourceCount: 0,
  }
}

function sanitizeMessage(message) {
  if (!message || typeof message !== 'object') {
    return null
  }

  if (message.role === 'user') {
    const question = typeof message.question === 'string' ? message.question : ''
    if (!question.trim()) {
      return null
    }
    return {
      id: typeof message.id === 'string' ? message.id : `user-${Date.now()}`,
      role: 'user',
      question,
    }
  }

  if (message.role === 'assistant') {
    const answer = typeof message.answer === 'string' ? message.answer : ''
    return {
      id: typeof message.id === 'string' ? message.id : `assistant-${Date.now()}`,
      role: 'assistant',
      answer,
      sources: Array.isArray(message.sources) ? message.sources : [],
      visibleSourceCount: Number.isFinite(message.visibleSourceCount) ? message.visibleSourceCount : 0,
    }
  }

  return null
}

export function trimRecentChatMessages(messages, maxExchanges = MAX_RECENT_CHAT_EXCHANGES) {
  const bodyMessages = Array.isArray(messages) ? messages.filter((message) => message?.id !== 'welcome') : []
  const exchanges = []

  for (let index = 0; index < bodyMessages.length; index += 1) {
    const userMessage = sanitizeMessage(bodyMessages[index])
    if (!userMessage || userMessage.role !== 'user') {
      continue
    }

    const assistantMessage = sanitizeMessage(bodyMessages[index + 1])
    if (!assistantMessage || assistantMessage.role !== 'assistant') {
      continue
    }

    exchanges.push([userMessage, assistantMessage])
    index += 1
  }

  return [createWelcomeMessage(), ...exchanges.slice(-maxExchanges).flat()]
}

export function loadRecentChatState() {
  if (typeof window === 'undefined') {
    return {
      includePublic: true,
      messages: [createWelcomeMessage()],
    }
  }

  try {
    const raw = window.localStorage.getItem(CHAT_HISTORY_STORAGE_KEY)
    if (!raw) {
      return {
        includePublic: true,
        messages: [createWelcomeMessage()],
      }
    }

    const parsed = JSON.parse(raw)
    return {
      includePublic: typeof parsed?.includePublic === 'boolean' ? parsed.includePublic : true,
      messages: trimRecentChatMessages(parsed?.messages),
    }
  } catch {
    return {
      includePublic: true,
      messages: [createWelcomeMessage()],
    }
  }
}

export function persistRecentChatState({ includePublic, messages }) {
  if (typeof window === 'undefined') {
    return
  }

  const payload = {
    includePublic: typeof includePublic === 'boolean' ? includePublic : true,
    messages: trimRecentChatMessages(messages),
  }

  try {
    window.localStorage.setItem(CHAT_HISTORY_STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Ignore storage write failures so the chat UI keeps working normally.
  }
}

