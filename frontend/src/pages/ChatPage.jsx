import { useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

import SourceCard from '../components/SourceCard'
import { createFavorite, deleteFavorite, sendChat } from '../lib/api'
import { loadRecentChatState, persistRecentChatState, trimRecentChatMessages } from '../lib/chatHistory'

const starterPrompts = [
  '사실상 취득의 판단 기준을 정리해줘.',
  '다주택자 중과세 예외 검토 포인트를 알려줘.',
  '재산세 과세표준 산정 시 전산 확인 순서를 알려줘.',
]
const SOURCE_PAGE_SIZE = 8

function splitAnswerSections(answer) {
  const lines = answer.split(/\r?\n/)
  const sections = []
  let current = null

  lines.forEach((line) => {
    const trimmed = line.trim()
    if (!trimmed) {
      if (current) current.lines.push('')
      return
    }

    if (/^[📋🖥️🗣️📌]/.test(trimmed)) {
      current = { title: trimmed, lines: [] }
      sections.push(current)
      return
    }

    if (!current) {
      current = { title: '답변', lines: [] }
      sections.push(current)
    }
    current.lines.push(trimmed)
  })

  return sections.length ? sections : [{ title: '답변', lines: [answer] }]
}

function MessageSections({ answer }) {
  const sections = useMemo(() => splitAnswerSections(answer), [answer])

  return (
    <div className="space-y-4">
      {sections.map((section, index) => {
        const isPractical = section.title.includes('🖥️')
        const boxClass = isPractical
          ? 'border-emerald-200 bg-emerald-50/90'
          : section.title.includes('📌')
            ? 'border-amber-200 bg-amber-50/80'
            : 'border-slate-200 bg-white/80'

        return (
          <section key={`${section.title}-${index}`} className={`rounded-[24px] border p-5 ${boxClass}`}>
            <h4 className="text-base font-semibold text-ink">{section.title}</h4>
            <div className="mt-3 space-y-3 text-sm leading-7 text-slate-700">
              {section.lines
                .filter((line, lineIndex, source) => !(line === '' && source[lineIndex - 1] === ''))
                .map((line, lineIndex) =>
                  line ? <p key={lineIndex}>{line}</p> : <div key={lineIndex} className="h-1" />,
                )}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function initialSourceCount(sources) {
  return Math.min(sources?.length || 0, SOURCE_PAGE_SIZE)
}

export default function ChatPage() {
  const { favorites = [], refreshFavorites } = useOutletContext()
  const [initialChatState] = useState(loadRecentChatState)
  const [includePublic, setIncludePublic] = useState(initialChatState.includePublic)
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState(initialChatState.messages)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [favoriteError, setFavoriteError] = useState('')
  const [favoritePendingIds, setFavoritePendingIds] = useState({})

  const favoriteIdSet = useMemo(() => new Set(favorites.map((item) => item.favorite_id)), [favorites])
  const recentAnswerCount = useMemo(
    () => messages.filter((message) => message.role === 'assistant' && message.id !== 'welcome').length,
    [messages],
  )

  useEffect(() => {
    persistRecentChatState({ includePublic, messages })
  }, [includePublic, messages])

  async function handleSubmit(event) {
    event.preventDefault()
    const question = draft.trim()
    if (!question || submitting) {
      return
    }

    const requestId = `${Date.now()}-${Math.random()}`
    setMessages((current) => [...current, { id: `${requestId}-user`, role: 'user', question }])
    setDraft('')
    setSubmitting(true)
    setError('')

    try {
      const response = await sendChat({ question, include_public: includePublic })
      const nextSources = response.sources || []
      setMessages((current) =>
        trimRecentChatMessages([
          ...current,
          {
            id: `${requestId}-assistant`,
            role: 'assistant',
            answer: response.answer,
            sources: nextSources,
            visibleSourceCount: initialSourceCount(nextSources),
          },
        ]),
      )
    } catch (requestError) {
      setError(requestError.message)
      setMessages((current) =>
        trimRecentChatMessages([
          ...current,
          {
            id: `${requestId}-assistant-error`,
            role: 'assistant',
            answer: '답변 생성에 실패했습니다. 잠시 후 다시 시도하거나 공개 데이터 포함 여부를 조정해 주세요.',
            sources: [],
            visibleSourceCount: 0,
          },
        ]),
      )
    } finally {
      setSubmitting(false)
    }
  }

  async function handleToggleFavorite(source) {
    const favoriteId = source.favorite_id
    if (!favoriteId) {
      return
    }

    const shouldRemove = favoriteIdSet.has(favoriteId)
    setFavoritePendingIds((current) => ({ ...current, [favoriteId]: true }))
    setFavoriteError('')

    try {
      if (shouldRemove) {
        await deleteFavorite(favoriteId)
      } else {
        await createFavorite(source)
      }
      await refreshFavorites()
    } catch (requestError) {
      setFavoriteError(requestError.message)
    } finally {
      setFavoritePendingIds((current) => {
        const next = { ...current }
        delete next[favoriteId]
        return next
      })
    }
  }

  function handleShowMoreSources(messageId) {
    setMessages((current) =>
      current.map((message) => {
        if (message.id !== messageId) return message
        const totalSources = message.sources?.length || 0
        return {
          ...message,
          visibleSourceCount: Math.min((message.visibleSourceCount || 0) + SOURCE_PAGE_SIZE, totalSources),
        }
      }),
    )
  }

  return (
    <div className="space-y-4">
      <section className="shell-panel mesh-surface overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-moss/70">Q&A Workspace</p>
            <h2 className="mt-3 font-display text-4xl leading-tight text-ink sm:text-5xl">질문 하나로 실무 판단과 법적 근거를 함께 정리합니다.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
              공개 법률 데이터와 내부자료를 결합해 답변하고, 민원처리 힌트와 전산적용 메모는 별도 섹션으로 분리해서 보여줍니다.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:min-w-[320px]">
            <label className="flex items-center justify-between gap-4 rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel">
              <div>
                <div className="text-sm font-semibold text-ink">공개 데이터 포함</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">국가법령정보센터 검색을 함께 수행합니다.</div>
              </div>
              <button
                type="button"
                aria-pressed={includePublic}
                onClick={() => setIncludePublic((current) => !current)}
                className={`relative h-8 w-16 rounded-full transition ${includePublic ? 'bg-ink' : 'bg-slate-300'}`}
              >
                <span
                  className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow transition ${includePublic ? 'left-9' : 'left-1'}`}
                />
              </button>
            </label>
            <div className="rounded-[24px] border border-amber-200 bg-amber-50/80 px-5 py-4 shadow-panel">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/80">최근 기록 유지</div>
              <div className="mt-2 text-sm leading-6 text-slate-700">최근 질의응답 {recentAnswerCount}건을 저장해 두고, 다른 메뉴를 다녀와도 다시 보여줍니다.</div>
            </div>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          {starterPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => setDraft(prompt)}
              className="secondary-button rounded-full px-4 py-2"
            >
              {prompt}
            </button>
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="shell-panel flex min-h-[680px] flex-col p-4 sm:p-6">
          <div className="space-y-4 overflow-y-auto pr-1">
            {messages.map((message) => {
              const totalSources = message.sources?.length || 0
              const visibleSourceCount = message.visibleSourceCount || totalSources
              const visibleSources = totalSources ? message.sources.slice(0, visibleSourceCount) : []
              const remainingSources = Math.max(totalSources - visibleSourceCount, 0)

              return (
                <article key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-4xl rounded-[28px] px-5 py-4 shadow-panel ${message.role === 'user' ? 'bg-ink text-white' : 'border border-slate-200 bg-white/88 text-ink'}`}>
                    {message.role === 'user' ? (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-white/70">질문</p>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-7 sm:text-base">{message.question}</p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">답변</p>
                          <div className="mt-3">
                            <MessageSections answer={message.answer} />
                          </div>
                        </div>

                        {visibleSources.length ? (
                          <div>
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">참조 출처</p>
                              <p className="text-xs text-slate-500">총 {totalSources}건</p>
                            </div>
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              {visibleSources.map((source, index) => (
                                <SourceCard
                                  key={source.favorite_id || `${message.id}-${source.title}-${index}`}
                                  source={source}
                                  isFavorite={favoriteIdSet.has(source.favorite_id)}
                                  favoriteBusy={Boolean(favoritePendingIds[source.favorite_id])}
                                  onToggleFavorite={handleToggleFavorite}
                                />
                              ))}
                            </div>
                            {remainingSources ? (
                              <div className="mt-4 flex justify-center">
                                <button type="button" className="secondary-button px-5 py-3" onClick={() => handleShowMoreSources(message.id)}>
                                  더보기 ({remainingSources}건 남음)
                                </button>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>
                </article>
              )
            })}
          </div>

          {favoriteError ? <p className="mt-4 text-sm text-amber-700">즐겨찾기 처리 중 문제가 있었습니다: {favoriteError}</p> : null}

          <form onSubmit={handleSubmit} className="mt-6 rounded-[28px] border border-slate-200 bg-white/85 p-4 shadow-panel">
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">질문 입력</span>
              <textarea
                className="field-textarea mt-3 min-h-[140px]"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={'예: "부담부증여" 취득세 판례를 찾아서 요지를 정리해줘.'}
                required
              />
            </label>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-slate-500">답변은 제공된 자료만 기반으로 작성되며, 공개자료 포함 여부는 즉시 반영됩니다. 최근 3개 질의응답은 자동 저장되어 다른 메뉴를 다녀와도 유지됩니다.</p>
              <button type="submit" className="primary-button" disabled={submitting}>
                {submitting ? '검색 및 생성 중...' : '질문 보내기'}
              </button>
            </div>
            {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
          </form>
        </div>

        <aside className="space-y-4">
          <section className="shell-panel p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">답변 원칙</p>
            <h3 className="mt-2 text-2xl font-display text-ink">출처와 전산 메모를 분리해서 읽기</h3>
            <ul className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <li>공개자료는 판례번호·조문번호 중심으로, 비공개자료는 내부자료 뱃지로 구분합니다.</li>
              <li>🖥️ 전산 처리 방법 섹션은 초록색 박스로 강조되어 실무 메모를 빠르게 확인할 수 있습니다.</li>
              <li>참조 출처는 처음 몇 개만 보이고, 더보기 버튼으로 같은 질문의 추가 자료를 계속 확인할 수 있습니다.</li>
              <li>마음에 드는 판례나 심판례는 카드 오른쪽 위 별표를 눌러 즐겨찾기(참조 출처)로 바로 모을 수 있습니다.</li>
              <li>최근 질의응답 3건은 페이지 이동 뒤에도 유지되어 바로 이어서 확인할 수 있습니다.</li>
            </ul>
          </section>

          <section className="shell-panel p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/80">실무 팁</p>
            <div className="mt-3 rounded-[24px] border border-amber-200 bg-amber-50/85 p-5 text-sm leading-7 text-slate-700">
              사실관계가 복잡한 질문은 취득 경위, 과세대상, 날짜, 예외 주장 포인트를 함께 적어두면 더 정확한 검색 결과를 얻기 쉽습니다. 특정 문구가 꼭 들어가야 하면 "부담부증여"처럼 큰따옴표로 묶어 주세요.
            </div>
          </section>
        </aside>
      </section>
    </div>
  )
}



