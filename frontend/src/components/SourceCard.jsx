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

export default function SourceCard({ source, isFavorite = false, onToggleFavorite, favoriteBusy = false }) {
  const isPrivate = source.is_private
  const categoryMeta = getCategoryMeta(source.category)
  const referenceLabel = isPrivate ? '내부자료' : source.reference || source.title || '공개자료'
  const canToggleFavorite = typeof onToggleFavorite === 'function' && source.favorite_id

  return (
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

      <h4 className="mt-4 text-base font-semibold text-ink">{source.title || '제목 정보 없음'}</h4>
      <p className="mt-2 text-sm leading-6 text-slate-600">{source.source || '출처 정보 없음'}</p>
      {source.summary ? <p className="mt-3 text-sm leading-6 text-slate-700">{source.summary}</p> : null}
      {source.detail_link ? (
        <a
          href={source.detail_link}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex text-sm font-semibold text-moss hover:text-tide"
        >
          원문 보기
        </a>
      ) : null}
    </article>
  )
}
