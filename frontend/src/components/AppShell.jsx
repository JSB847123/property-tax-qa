import { useCallback, useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'

import { fetchDocumentStats, fetchFavorites } from '../lib/api'
import Sidebar from './Sidebar'

export default function AppShell() {
  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState('')
  const [favorites, setFavorites] = useState([])
  const [favoritesLoading, setFavoritesLoading] = useState(true)
  const [favoritesError, setFavoritesError] = useState('')

  const refreshStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const next = await fetchDocumentStats()
      setStats(next)
      setStatsError('')
    } catch (error) {
      setStatsError(error.message)
    } finally {
      setStatsLoading(false)
    }
  }, [])

  const refreshFavorites = useCallback(async () => {
    setFavoritesLoading(true)
    try {
      const next = await fetchFavorites()
      setFavorites(next)
      setFavoritesError('')
    } catch (error) {
      setFavoritesError(error.message)
    } finally {
      setFavoritesLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshStats()
    refreshFavorites()
  }, [refreshStats, refreshFavorites])

  return (
    <div className="relative min-h-screen overflow-hidden px-4 py-4 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-0 opacity-60">
        <div className="soft-grid absolute inset-0" />
      </div>

      <div className="relative mx-auto grid max-w-[1700px] gap-4 lg:grid-cols-[320px_minmax(0,1fr)] lg:gap-6">
        <Sidebar stats={stats} loading={statsLoading} favoritesCount={favorites.length} favoritesLoading={favoritesLoading} />

        <main className="space-y-4">
          {statsError ? (
            <div className="shell-panel border border-rose-200 bg-rose-50/80 px-5 py-4 text-sm text-rose-700">
              통계를 불러오지 못했습니다: {statsError}
            </div>
          ) : null}
          {favoritesError ? (
            <div className="shell-panel border border-amber-200 bg-amber-50/80 px-5 py-4 text-sm text-amber-700">
              즐겨찾기를 불러오지 못했습니다: {favoritesError}
            </div>
          ) : null}
          <Outlet context={{ stats, refreshStats, favorites, refreshFavorites, favoritesLoading, favoritesError }} />
        </main>
      </div>
    </div>
  )
}
