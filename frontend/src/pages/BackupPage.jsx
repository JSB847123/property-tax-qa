import { useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

import { downloadBackupFile, restoreBackupFile } from '../lib/api'

const restoreModes = [
  {
    value: 'merge',
    label: '합쳐서 복원',
    description: '현재 자료는 유지하고, 백업 파일 안의 등록 자료·즐겨찾기·설정을 추가하거나 덮어씁니다.',
  },
  {
    value: 'replace',
    label: '현재 내용 교체',
    description: '현재 PC의 등록 자료·즐겨찾기·저장 설정을 지우고, 백업 파일 기준으로 완전히 바꿉니다.',
  },
]

function triggerDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

export default function BackupPage() {
  const { stats, favorites = [], refreshStats, refreshFavorites } = useOutletContext()
  const [mode, setMode] = useState('merge')
  const [selectedFile, setSelectedFile] = useState(null)
  const [downloading, setDownloading] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const modeDescription = useMemo(
    () => restoreModes.find((item) => item.value === mode)?.description || '',
    [mode],
  )

  async function handleDownload() {
    setDownloading(true)
    setError('')
    setMessage('')

    try {
      const { blob, filename } = await downloadBackupFile()
      triggerDownload(blob, filename)
      setMessage('등록 자료, 즐겨찾기, 설정을 백업 파일로 내려받았습니다. API 키가 포함될 수 있으니 안전한 위치에 보관해 주세요.')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setDownloading(false)
    }
  }

  async function handleRestore(event) {
    event.preventDefault()
    if (!selectedFile || restoring) {
      return
    }

    setRestoring(true)
    setError('')
    setMessage('')

    try {
      const response = await restoreBackupFile(selectedFile, mode)
      await refreshStats()
      await refreshFavorites()
      setMessage(
        `${response.message} 등록 자료 ${response.documents_imported}건, 즐겨찾기 ${response.favorites_imported}건, 설정 ${response.settings_imported}건을 반영했습니다.`,
      )
      setSelectedFile(null)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setRestoring(false)
    }
  }

  return (
    <div className="space-y-4">
      <section className="shell-panel mesh-surface overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-moss/70">Backup & Restore</p>
            <h2 className="mt-3 font-pretendard text-4xl font-bold leading-tight text-ink sm:text-5xl">등록 자료와 즐겨찾기, 설정을 파일로 옮겨서 다른 PC에서도 이어서 사용하세요</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
              항상 켜진 PC나 클라우드가 없어도, 백업 파일 하나로 등록 자료·즐겨찾기·저장 설정을 옮길 수 있습니다. 복원 방식은 합치기와 현재 내용 교체 중에서 선택할 수 있습니다.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">등록 자료</div>
              <div className="mt-3 text-3xl font-display text-ink">{stats?.total_count ?? 0}</div>
            </div>
            <div className="rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/80">즐겨찾기</div>
              <div className="mt-3 text-3xl font-display text-ink">{favorites.length}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)]">
        <section className="shell-panel p-6 sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">내보내기</p>
          <h3 className="mt-2 text-2xl font-display text-ink">현재 PC의 자료를 백업 파일로 저장</h3>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            현재 등록 자료, 즐겨찾기, 저장된 설정을 하나의 JSON 백업 파일로 내려받습니다. 다른 자리 PC에서는 이 파일 하나만 있으면 복원할 수 있습니다.
          </p>
          <div className="mt-5 rounded-[24px] border border-amber-200 bg-amber-50/85 p-5 text-sm leading-7 text-slate-700">
            백업 파일에는 API Key와 LAW_OC 같은 민감한 설정이 포함될 수 있습니다. 메신저, 이메일, 공유폴더로 옮길 때는 권한과 보관 위치를 꼭 확인해 주세요.
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs leading-6 text-slate-500">다운로드 후에는 파일명을 바꾸지 않아도 복원할 수 있습니다.</p>
            <button type="button" className="primary-button" onClick={handleDownload} disabled={downloading}>
              {downloading ? '백업 생성 중...' : '전체 백업 내보내기'}
            </button>
          </div>
        </section>

        <section className="shell-panel p-6 sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-700/80">불러오기</p>
          <h3 className="mt-2 text-2xl font-display text-ink">다른 PC의 백업 파일 복원</h3>
          <form onSubmit={handleRestore} className="mt-6 space-y-6">
            <div className="grid gap-3">
              {restoreModes.map((item) => {
                const active = item.value === mode
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setMode(item.value)}
                    className={`rounded-[24px] border px-5 py-5 text-left transition ${
                      active ? 'border-moss bg-ink text-white shadow-float' : 'border-slate-200 bg-white/90 text-ink hover:border-moss/40'
                    }`}
                  >
                    <div className="text-sm font-semibold tracking-[0.16em] uppercase">{item.label}</div>
                    <p className={`mt-3 text-sm leading-6 ${active ? 'text-white/80' : 'text-slate-600'}`}>{item.description}</p>
                  </button>
                )
              })}
            </div>

            <div className="rounded-[24px] border border-slate-200 bg-slate-50/70 px-4 py-4 text-sm leading-6 text-slate-600">
              {modeDescription}
            </div>

            <label className="block rounded-[24px] border border-dashed border-moss/30 bg-emerald-50/55 p-6 text-center">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">백업 파일 선택</span>
              <div className="mt-3 text-2xl font-display text-ink">JSON 백업 파일 업로드</div>
              <p className="mt-2 text-sm leading-7 text-slate-600">복원 시 등록 자료, 즐겨찾기, 저장된 설정이 함께 반영됩니다.</p>
              <input
                type="file"
                accept=".json,application/json"
                className="mt-5 block w-full text-sm text-slate-600"
                onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
              />
              {selectedFile ? <p className="mt-4 text-sm font-semibold text-moss">선택 파일: {selectedFile.name}</p> : null}
            </label>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs leading-6 text-slate-500">복원 후에는 현재 화면의 자료 통계와 즐겨찾기 목록도 자동으로 새로고침됩니다.</p>
              <button type="submit" className="primary-button" disabled={!selectedFile || restoring}>
                {restoring ? '복원 중...' : mode === 'replace' ? '현재 내용 교체' : '백업 파일 복원'}
              </button>
            </div>
          </form>
        </section>
      </section>

      {message ? <div className="shell-panel border border-emerald-200 bg-emerald-50/85 px-5 py-4 text-sm text-emerald-700">{message}</div> : null}
      {error ? <div className="shell-panel border border-rose-200 bg-rose-50/85 px-5 py-4 text-sm text-rose-700">{error}</div> : null}
    </div>
  )
}
