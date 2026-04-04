import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

import DocumentForm from '../components/DocumentForm'
import { deleteDocument, fetchDocuments, updateDocument } from '../lib/api'
import { categoryOptions, getCategoryMeta } from '../lib/categories'
import { documentToForm, formToPayload, summarizeText } from '../lib/documents'

function Pagination({ page, totalPages, onChange }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[24px] border border-slate-200 bg-white/80 px-4 py-3">
      <p className="text-sm text-slate-500">
        페이지 <span className="font-semibold text-ink">{page}</span> / {Math.max(totalPages, 1)}
      </p>
      <div className="flex gap-2">
        <button type="button" className="secondary-button px-4 py-2" onClick={() => onChange(page - 1)} disabled={page <= 1}>
          이전
        </button>
        <button type="button" className="secondary-button px-4 py-2" onClick={() => onChange(page + 1)} disabled={page >= totalPages}>
          다음
        </button>
      </div>
    </div>
  )
}

export default function DocumentsPage() {
  const { refreshStats } = useOutletContext()
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [page, setPage] = useState(1)
  const [data, setData] = useState({ items: [], total: 0, total_pages: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedId, setExpandedId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editingForm, setEditingForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  useEffect(() => {
    setPage(1)
  }, [category, deferredSearch])

  useEffect(() => {
    let active = true

    async function loadDocuments() {
      setLoading(true)
      try {
        const next = await fetchDocuments({
          category: category || undefined,
          search: deferredSearch || undefined,
          page,
          pageSize: 8,
        })
        if (active) {
          setData(next)
          setError('')
        }
      } catch (requestError) {
        if (active) {
          setError(requestError.message)
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    loadDocuments()
    return () => {
      active = false
    }
  }, [category, deferredSearch, page])

  const documents = data.items || []
  const totalPages = data.total_pages || 0

  const selectedCategoryDescription = useMemo(() => {
    if (!category) return '전체 자료를 대상으로 제목, 출처, 내용, 전산적용 메모를 함께 검색합니다.'
    return getCategoryMeta(category).description
  }, [category])

  function startEdit(document) {
    setEditingId(document.id)
    setEditingForm(documentToForm(document))
    setExpandedId(document.id)
  }

  function cancelEdit() {
    setEditingId(null)
    setEditingForm(null)
  }

  async function handleSave(event) {
    event.preventDefault()
    if (!editingId || !editingForm) {
      return
    }

    setSaving(true)
    try {
      await updateDocument(editingId, formToPayload(editingForm))
      const next = await fetchDocuments({
        category: category || undefined,
        search: deferredSearch || undefined,
        page,
        pageSize: 8,
      })
      setData(next)
      await refreshStats()
      cancelEdit()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(document) {
    if (!window.confirm(`'${document.title}' 문서를 삭제할까요?`)) {
      return
    }

    setDeletingId(document.id)
    try {
      await deleteDocument(document.id)
      const nextPage = documents.length === 1 && page > 1 ? page - 1 : page
      const next = await fetchDocuments({
        category: category || undefined,
        search: deferredSearch || undefined,
        page: nextPage,
        pageSize: 8,
      })
      setPage(nextPage)
      setData(next)
      await refreshStats()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <section className="shell-panel mesh-surface p-6 sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-moss/70">Document Library</p>
            <h2 className="mt-3 font-pretendard text-4xl font-bold text-ink">등록 자료를 한 눈에 보고 바로 수정합니다.</h2>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
              검색어, 카테고리, 전산적용 여부를 기준으로 실무자료를 골라보고, 카드 확장 후 즉시 내용을 수정하거나 삭제할 수 있습니다.
            </p>
          </div>
          <div className="rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel">
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">검색 범위 설명</div>
            <p className="mt-2 max-w-sm text-sm leading-7 text-slate-600">{selectedCategoryDescription}</p>
          </div>
        </div>
      </section>

      <section className="shell-panel p-6">
        <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
          <label className="space-y-2">
            <span className="text-sm font-semibold text-slate-700">자료 검색</span>
            <input
              className="field-input"
              placeholder="제목, 출처, 내용, 전산적용, 태그 검색"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-semibold text-slate-700">카테고리 필터</span>
            <select className="field-input" value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">전체</option>
              {categoryOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {error ? <div className="shell-panel border border-rose-200 bg-rose-50/80 px-5 py-4 text-sm text-rose-700">{error}</div> : null}

      <section className="space-y-4">
        {loading ? (
          <div className="shell-panel px-6 py-10 text-center text-sm text-slate-500">문서 목록을 불러오는 중입니다.</div>
        ) : documents.length === 0 ? (
          <div className="shell-panel px-6 py-10 text-center text-sm text-slate-500">조건에 맞는 문서가 없습니다.</div>
        ) : (
          documents.map((document) => {
            const categoryMeta = getCategoryMeta(document.category)
            const expanded = expandedId === document.id
            const editing = editingId === document.id && editingForm

            return (
              <article key={document.id} className="shell-panel overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedId(expanded ? null : document.id)}
                  className="flex w-full flex-col gap-4 p-6 text-left transition hover:bg-white/40"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`badge ${categoryMeta.tone}`}>{categoryMeta.shortLabel}</span>
                        {document.practical ? <span className="badge border-emerald-200 bg-emerald-50 text-emerald-700">전산적용</span> : null}
                        <span className="text-xs font-medium text-slate-500">{document.date}</span>
                      </div>
                      <div>
                        <h3 className="text-2xl font-semibold text-ink">{document.title}</h3>
                        <p className="mt-2 text-sm text-slate-500">{document.source}</p>
                      </div>
                    </div>
                    <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {expanded ? '닫기' : '상세 보기'}
                    </div>
                  </div>
                  <p className="max-w-5xl text-sm leading-7 text-slate-600">{summarizeText(document.content)}</p>
                </button>

                {expanded ? (
                  <div className="border-t border-slate-200 px-6 pb-6 pt-5">
                    {editing ? (
                      <DocumentForm
                        form={editingForm}
                        onChange={(field, value) => setEditingForm((current) => ({ ...current, [field]: value }))}
                        onSubmit={handleSave}
                        submitLabel="변경사항 저장"
                        submitting={saving}
                        secondaryAction={
                          <button type="button" className="secondary-button" onClick={cancelEdit}>
                            편집 취소
                          </button>
                        }
                      />
                    ) : (
                      <div className="space-y-5">
                        <section className="rounded-[24px] border border-slate-200 bg-white/80 p-5">
                          <h4 className="text-sm font-semibold uppercase tracking-[0.2em] text-moss/70">내용</h4>
                          <p className="mt-4 whitespace-pre-wrap text-sm leading-8 text-slate-700">{document.content}</p>
                        </section>

                        {document.practical ? (
                          <section className="rounded-[24px] border border-emerald-200 bg-emerald-50/85 p-5">
                            <h4 className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-800">🖥️ 전산적용</h4>
                            <p className="mt-4 whitespace-pre-wrap text-sm leading-8 text-slate-700">{document.practical}</p>
                          </section>
                        ) : null}

                        {document.tags?.length ? (
                          <div className="flex flex-wrap gap-2">
                            {document.tags.map((tag) => (
                              <span key={tag} className="badge border-slate-200 bg-slate-50 text-slate-600">
                                {tag}
                              </span>
                            ))}
                          </div>
                        ) : null}

                        <div className="flex flex-wrap gap-3">
                          <button type="button" className="primary-button" onClick={() => startEdit(document)}>
                            수정
                          </button>
                          <button type="button" className="danger-button" onClick={() => handleDelete(document)} disabled={deletingId === document.id}>
                            {deletingId === document.id ? '삭제 중...' : '삭제'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}
              </article>
            )
          })
        )}
      </section>

      <Pagination page={page} totalPages={Math.max(totalPages, 1)} onChange={setPage} />
    </div>
  )
}
