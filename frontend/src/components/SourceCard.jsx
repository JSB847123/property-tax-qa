import { useState } from 'react'

import { fetchDocument } from '../lib/api'
import { getCategoryMeta } from '../lib/categories'

function StarIcon({ filled }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path
        d="M12 3.75l2.546 5.16 5.694.827-4.12 4.016.972 5.671L12 16.746l-5.092 2.678.972-5.671-4.12-4.016 5.694-.827L12 3.75z"
        fill={filled ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.7"
      />
    </svg>
  )
}

function RegisteredDocumentModal({ source, detail, loading, error, onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-ink/45 px-4 py-8" onClick={onClose}>
      <div
        className="mx-auto flex max-h-full max-w-4xl flex-col rounded-[28px] border border-white/60 bg-white/95 p-6 shadow-2xl backdrop-blur-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">등록 자료 상세</p>
            <h3 className="mt-2 text-2xl font-display text-ink">{detail?.title || source.title || '제목 정보 없음'}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">{detail?.source || source.source || '출처 정보 없음'}</p>
          </div>
          <button type="button" className="secondary-button px-4 py-2" onClick={onClose}>
            닫기
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="badge border-emerald-200 bg-emerald-50 text-emerald-700">등록 자료</span>
          <span className="badge border-slate-200 bg-slate-50 text-slate-600">{getCategoryMeta(detail?.category || source.category).shortLabel}</span>
          {(detail?.date || source.date) ? <span className="text-xs font-medium text-slate-500">{detail?.date || source.date}</span> : null}
        </div>

        {loading ? (
          <div className="mt-6 rounded-[24px] border border-slate-200 bg-slate-50/80 px-5 py-8 text-center text-sm text-slate-500">
            등록 자료 전체 내용을 불러오는 중입니다.
          </div>
        ) : error ? (
          <div className="mt-6 rounded-[24px] border border-rose-200 bg-rose-50/80 px-5 py-4 text-sm text-rose-700">
            등록 자료를 불러오지 못했습니다: {error}
          </div>
        ) : (
          <div className="mt-6 space-y-4 overflow-y-auto pr-1">
            <section className="rounded-[24px] border border-slate-200 bg-white/90 p-5">
              <h4 className="text-sm font-semibold uppercase tracking-[0.2em] text-moss/70">내용</h4>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-8 text-slate-700">
                {detail?.content || source.summary || '등록된 내용이 없습니다.'}
              </p>
            </section>

            {detail?.practical ? (
              <section className="rounded-[24px] border border-emerald-200 bg-emerald-50/85 p-5">
                <h4 className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-800">🖥️ 전산적용</h4>
                <p className="mt-4 whitespace-pre-wrap text-sm leading-8 text-slate-700">{detail.practical}</p>
              </section>
            ) : null}

            {detail?.tags?.length ? (
              <div className="flex flex-wrap gap-2">
                {detail.tags.map((tag) => (
                  <span key={tag} className="badge border-slate-200 bg-slate-50 text-slate-600">
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}

export default function SourceCard({ source, isFavorite = false, onToggleFavorite, favoriteBusy = false }) {
  const isPrivate = source.is_private
  const categoryMeta = getCategoryMeta(source.category)
  const referenceLabel = isPrivate ? '등록 자료' : source.reference || source.title || '공개자료'
  const canToggleFavorite = typeof onToggleFavorite === 'function' && source.favorite_id
  const canOpenRegisteredDocument = Boolean(isPrivate && source.id)
  const [detailOpen, setDetailOpen] = useState(false)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')

  async function handleOpenRegisteredDocument() {
    setDetailOpen(true)
    if (!source.id || detail || detailLoading) {
      return
    }

    setDetailLoading(true)
    setDetailError('')
    try {
      const response = await fetchDocument(source.id)
      setDetail(response)
    } catch (requestError) {
      setDetailError(requestError.message)
    } finally {
      setDetailLoading(false)
    }
  }

  const titleNode = canOpenRegisteredDocument ? (
    <button type="button" onClick={handleOpenRegisteredDocument} className="mt-4 text-left text-base font-semibold text-ink hover:text-moss">
      {source.title || '제목 정보 없음'}
    </button>
  ) : (
    <h4 className="mt-4 text-base font-semibold text-ink">{source.title || '제목 정보 없음'}</h4>
  )

  const summaryText = source.summary || (canOpenRegisteredDocument ? '등록된 자료의 전체 내용은 아래 버튼에서 바로 확인할 수 있습니다.' : '')

  return (
    <>
      <article className="relative rounded-[24px] border border-slate-200 bg-white/85 p-4 shadow-panel">
        {canToggleFavorite ? (
          <button
            type="button"
            aria-label={isFavorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}
            aria-pressed={isFavorite}
            disabled={favoriteBusy}
            onClick={() => onToggleFavorite(source)}
            className={`absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full border transition ${
              isFavorite
                ? 'border-amber-300 bg-amber-50 text-amber-500'
                : 'border-slate-200 bg-white text-slate-400 hover:border-amber-200 hover:text-amber-500'
            } ${favoriteBusy ? 'cursor-wait opacity-70' : ''}`}
          >
            <StarIcon filled={isFavorite} />
          </button>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 pr-14">
          <span className={`badge ${isPrivate ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : categoryMeta.tone}`}>
            {referenceLabel}
          </span>
          <span className="badge border-slate-200 bg-slate-50 text-slate-600">{categoryMeta.shortLabel}</span>
          {source.date ? <span className="text-xs font-medium text-slate-500">{source.date}</span> : null}
        </div>

        {titleNode}
        <p className="mt-2 text-sm leading-6 text-slate-600">{source.source || '출처 정보 없음'}</p>
        {summaryText ? <p className="mt-3 text-sm leading-6 text-slate-700">{summaryText}</p> : null}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {canOpenRegisteredDocument ? (
            <button type="button" className="secondary-button px-4 py-2" onClick={handleOpenRegisteredDocument}>
              등록 자료 보기
            </button>
          ) : null}
          {source.detail_link ? (
            <a
              href={source.detail_link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex text-sm font-semibold text-moss hover:text-tide"
            >
              원문 보기
            </a>
          ) : null}
        </div>
      </article>

      {detailOpen ? (
        <RegisteredDocumentModal
          source={source}
          detail={detail}
          loading={detailLoading}
          error={detailError}
          onClose={() => setDetailOpen(false)}
        />
      ) : null}
    </>
  )
}
