import { NavLink } from 'react-router-dom'

import { categoryOptions } from '../lib/categories'

const navigation = [
  { to: '/chat', label: '질의응답', caption: '공개·비공개 자료를 합쳐 바로 답변' },
  { to: '/favorites', label: '즐겨찾기', caption: '별표한 참조 출처를 한곳에 모아 보기' },
  { to: '/settings', label: '연동설정', caption: 'API 키를 임시 또는 영구 저장으로 적용' },
  { to: '/documents', label: '자료관리', caption: '등록 자료 검색, 수정, 삭제' },
  { to: '/documents/new', label: '자료등록', caption: '새 실무자료 빠르게 입력' },
  { to: '/documents/bulk', label: '대량등록', caption: 'CSV 미리보기 후 일괄 반영' },
]

function StatLine({ label, value, tone }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/70 bg-white/70 px-4 py-3">
      <span className={`badge ${tone}`}>{label}</span>
      <span className="text-sm font-semibold text-ink">{value}</span>
    </div>
  )
}

export default function Sidebar({ stats, loading, favoritesCount = 0, favoritesLoading = false }) {
  return (
    <aside className="shell-panel mesh-surface relative overflow-hidden px-5 py-6 sm:px-6 lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)]">
      <div className="absolute inset-x-0 top-0 h-36 bg-gradient-to-br from-emerald-200/60 via-transparent to-amber-200/60" />
      <div className="relative flex h-full flex-col gap-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-moss/70">Tax RAG Console</p>
          <h1 className="mt-3 font-pretendard text-3xl font-bold leading-tight text-ink">취득세·재산세 업무 도우미</h1>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            취득세·재산세 질의, 내부 실무자료, 공개 법률 데이터를 한 화면에서 정리하는 업무용 인터페이스입니다.
          </p>
        </div>

        <nav className="space-y-2">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded-[24px] border px-4 py-4 transition ${
                  isActive
                    ? 'border-moss bg-ink text-white shadow-float'
                    : 'border-white/70 bg-white/70 text-ink hover:border-moss/40 hover:bg-white'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold tracking-[0.16em] uppercase">{item.label}</div>
                    {item.to === '/favorites' ? (
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${isActive ? 'bg-white/15 text-white' : 'bg-amber-50 text-amber-700'}`}>
                        {favoritesLoading ? '...' : `${favoritesCount}건`}
                      </span>
                    ) : null}
                  </div>
                  <div className={`mt-2 text-sm leading-6 ${isActive ? 'text-white/80' : 'text-slate-600'}`}>{item.caption}</div>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto rounded-[24px] border border-white/70 bg-white/80 p-4 shadow-panel">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">등록 통계</p>
              <h2 className="mt-2 text-lg font-semibold text-ink">자료 현황</h2>
            </div>
            <div className="rounded-2xl bg-emerald-100 px-3 py-2 text-sm font-semibold text-moss">
              {loading ? '불러오는 중' : `${stats?.total_count ?? 0}건`}
            </div>
          </div>

          <div className="mt-4 space-y-3">
            <StatLine label="전체" value={loading ? '...' : stats?.total_count ?? 0} tone="border-slate-200 bg-slate-50 text-slate-700" />
            <StatLine
              label="전산적용 포함"
              value={loading ? '...' : stats?.with_practical_count ?? 0}
              tone="border-emerald-200 bg-emerald-50 text-emerald-700"
            />
            <StatLine
              label="즐겨찾기(참조 출처)"
              value={favoritesLoading ? '...' : favoritesCount}
              tone="border-amber-200 bg-amber-50 text-amber-700"
            />
            {categoryOptions.map((item) => (
              <StatLine
                key={item.value}
                label={item.shortLabel}
                value={loading ? '...' : stats?.category_counts?.[item.value] ?? 0}
                tone={item.tone}
              />
            ))}
          </div>
        </div>
      </div>
    </aside>
  )
}
