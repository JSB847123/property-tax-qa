import { useDeferredValue, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

import SourceCard from '../components/SourceCard'
import { deleteFavorite } from '../lib/api'
import { categoryOptions, getCategoryMeta } from '../lib/categories'

export default function FavoritesPage() {
  const { favorites = [], refreshFavorites, favoritesLoading, favoritesError } = useOutletContext()
  const [pendingIds, setPendingIds] = useState({})
  const [actionError, setActionError] = useState('')
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)

  const publicCount = useMemo(() => favorites.filter((item) => !item.is_private).length, [favorites])
  const privateCount = favorites.length - publicCount

  const selectedCategoryDescription = useMemo(() => {
    if (!category) return '전체 즐겨찾기를 대상으로 제목, 출처, 요약, 참조번호를 함께 검색합니다.'
    return getCategoryMeta(category).description
  }, [category])

  const filteredFavorites = useMemo(() => {
    const normalizedQuery = deferredSearch.trim().toLowerCase()

    return favorites.filter((item) => {
      if (category && item.category !== category) {
        return false
      }

      if (!normalizedQuery) {
        return true
      }

      const haystack = [
        item.title,
        item.source,
        item.summary,
        item.reference,
        item.citation,
        item.date,
        getCategoryMeta(item.category).label,
        item.is_private ? '등록 자료' : '공개자료',
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

      return haystack.includes(normalizedQuery)
    })
  }, [favorites, category, deferredSearch])

  async function handleToggleFavorite(source) {
    const favoriteId = source.favorite_id
    if (!favoriteId) {
      return
    }

    setPendingIds((current) => ({ ...current, [favoriteId]: true }))
    setActionError('')

    try {
      await deleteFavorite(favoriteId)
      await refreshFavorites()
    } catch (requestError) {
      setActionError(requestError.message)
    } finally {
      setPendingIds((current) => {
        const next = { ...current }
        delete next[favoriteId]
        return next
      })
    }
  }

  return (
    <div className="space-y-4">
      <section className="shell-panel mesh-surface overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-amber-700/80">Bookmarks</p>
            <h2 className="mt-3 font-pretendard text-4xl font-bold leading-tight text-ink sm:text-5xl">즐겨찾기(참조 출처)</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
              질문 중에 별표한 판례, 심판례, 법령, 등록 자료를 한곳에서 다시 보고 원문이나 전체 내용을 바로 확인할 수 있습니다.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">전체</div>
              <div className="mt-3 text-3xl font-display text-ink">{favoritesLoading ? '...' : favorites.length}</div>
            </div>
            <div className="rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-700/80">공개자료</div>
              <div className="mt-3 text-3xl font-display text-ink">{favoritesLoading ? '...' : publicCount}</div>
            </div>
            <div className="rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700/80">등록 자료</div>
              <div className="mt-3 text-3xl font-display text-ink">{favoritesLoading ? '...' : privateCount}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="shell-panel p-6">
        <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
          <label className="space-y-2">
            <span className="text-sm font-semibold text-slate-700">즐겨찾기 검색</span>
            <input
              className="field-input"
              placeholder="제목, 출처, 요약, 참조번호 검색"
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

      <section className="shell-panel p-6 sm:p-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Saved Sources</p>
            <h3 className="mt-2 text-2xl font-display text-ink">별표한 참조 출처 목록</h3>
          </div>
          <div className="rounded-full bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700">
            {favoritesLoading ? '불러오는 중...' : `${filteredFavorites.length}건 표시 / 전체 ${favorites.length}건`}
          </div>
        </div>

        <div className="mt-4 rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel">
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">검색 범위 설명</div>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-600">{selectedCategoryDescription}</p>
        </div>

        {favoritesError ? <p className="mt-4 text-sm text-amber-700">즐겨찾기를 불러오지 못했습니다: {favoritesError}</p> : null}
        {actionError ? <p className="mt-4 text-sm text-rose-600">즐겨찾기 변경 중 문제가 있었습니다: {actionError}</p> : null}

        {favoritesLoading ? (
          <div className="mt-6 rounded-[24px] border border-dashed border-slate-300 bg-slate-50/80 px-6 py-10 text-center text-sm text-slate-500">
            즐겨찾기한 참조 출처를 불러오는 중입니다.
          </div>
        ) : !favorites.length ? (
          <div className="mt-6 rounded-[28px] border border-dashed border-amber-300 bg-amber-50/60 px-6 py-10 text-center">
            <h4 className="text-xl font-semibold text-ink">아직 저장된 즐겨찾기가 없습니다.</h4>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              질의응답 화면에서 참조 출처 카드 오른쪽 위 별표를 누르면 여기에서 바로 다시 볼 수 있습니다.
            </p>
          </div>
        ) : filteredFavorites.length ? (
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredFavorites.map((source) => (
              <SourceCard
                key={source.favorite_id}
                source={source}
                isFavorite
                favoriteBusy={Boolean(pendingIds[source.favorite_id])}
                onToggleFavorite={handleToggleFavorite}
              />
            ))}
          </div>
        ) : (
          <div className="mt-6 rounded-[28px] border border-dashed border-slate-300 bg-slate-50/80 px-6 py-10 text-center">
            <h4 className="text-xl font-semibold text-ink">검색 조건에 맞는 즐겨찾기가 없습니다.</h4>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              검색어를 줄이거나 카테고리를 전체로 바꾸면 저장된 참조 출처를 다시 확인할 수 있습니다.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}
