import { useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

import { uploadBulkCsv } from '../lib/api'
import { buildBulkPreview } from '../lib/bulkImport'
import { categoryOptions, getCategoryMeta } from '../lib/categories'

const markdownExample = `# 사실상 취득의 판단 기준 정리
- 분류: 이론
- 출처: 내부 검토 메모
- 날짜: 2026-04-03
- 태그: 취득세;사실상취득
## 내용
사실상 취득은 대금 지급과 사용수익의 이전 등 실질을 기준으로 판단한다.
## 전산적용
잔금일과 점유 이전일을 함께 확인한다.

---
# 증여취득 신고 누락 민원
- 분류: 민원처리
- 출처: 민원처리 내부기록
- 날짜: 2026-04-03
- 태그: 취득세;증여;민원
## 내용
신고 누락 민원 처리 기록
## 전산적용
위택스 보완 입력`

export default function BulkUploadPage() {
  const { refreshStats } = useOutletContext()
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const totalRows = preview?.rows?.length || 0
  const successfulPreviewCount = totalRows - (preview?.errors?.length || 0)

  const categorySummaries = useMemo(() => {
    if (!preview?.categoryStats) return []
    return categoryOptions
      .map((option) => ({ ...option, count: preview.categoryStats[option.value] || 0 }))
      .filter((item) => item.count > 0)
  }, [preview])

  async function handleFileChange(event) {
    const nextFile = event.target.files?.[0] || null
    setFile(nextFile)
    setResult(null)
    setError('')

    if (!nextFile) {
      setPreview(null)
      return
    }

    try {
      const text = await nextFile.text()
      setPreview(buildBulkPreview({ text, fileName: nextFile.name }))
    } catch (parseError) {
      setPreview(null)
      setError(parseError.message)
    }
  }

  async function handleUpload() {
    if (!file || uploading) {
      return
    }

    setUploading(true)
    setError('')
    try {
      const response = await uploadBulkCsv(file)
      setResult(response)
      await refreshStats()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-4">
      <section className="shell-panel mesh-surface p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-moss/70">Bulk Import</p>
        <h2 className="mt-3 font-pretendard text-4xl font-bold text-ink">CSV와 Markdown을 미리 검토한 뒤 안전하게 일괄 등록합니다.</h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
          업로드 전에 카테고리 매핑과 건수 분포를 먼저 확인하고, 이상이 없을 때만 서버에 반영하는 흐름입니다. Markdown은 문서 사이를 <code>---</code> 한 줄로 구분하면 여러 건을 한 번에 넣을 수 있습니다.
        </p>
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
        <div className="space-y-4">
          <section className="shell-panel p-6">
            <label className="block rounded-[24px] border border-dashed border-moss/30 bg-emerald-50/55 p-6 text-center">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">CSV / Markdown 업로드</span>
              <div className="mt-3 text-2xl font-display text-ink">파일을 선택해 미리보기 생성</div>
              <p className="mt-2 text-sm leading-7 text-slate-600">
                CSV 헤더: 분류, 제목, 출처, 내용, 전산적용, 날짜, 태그
                <br />
                Markdown: <code># 제목</code>, <code>- 분류:</code>, <code>## 내용</code>, <code>## 전산적용</code>, 문서 구분선 <code>---</code>
              </p>
              <input type="file" accept=".csv,text/csv,.md,.markdown,text/markdown" className="mt-5 block w-full text-sm text-slate-600" onChange={handleFileChange} />
              {file ? <p className="mt-4 text-sm font-semibold text-moss">선택 파일: {file.name}</p> : null}
            </label>
          </section>

          <section className="shell-panel p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">미리보기 요약</p>
                <h3 className="mt-2 text-2xl font-display text-ink">건수와 분포</h3>
              </div>
              <button type="button" className="primary-button" onClick={handleUpload} disabled={!file || !preview || uploading || totalRows === 0}>
                {uploading ? '등록 중...' : '확인 후 일괄 등록'}
              </button>
            </div>

            <div className="mt-4 flex items-center gap-3">
              {preview ? <span className="badge border-moss/20 bg-emerald-50 text-moss">{preview.formatLabel} 파일</span> : null}
              {result?.file_type ? <span className="badge border-slate-200 bg-slate-50 text-slate-600">최근 등록: {result.file_type}</span> : null}
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-[24px] border border-slate-200 bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.24em] text-slate-500">전체 항목</div>
                <div className="mt-2 text-3xl font-display text-ink">{totalRows}</div>
              </div>
              <div className="rounded-[24px] border border-emerald-200 bg-emerald-50/80 p-4">
                <div className="text-xs uppercase tracking-[0.24em] text-emerald-700">유효 항목</div>
                <div className="mt-2 text-3xl font-display text-ink">{successfulPreviewCount}</div>
              </div>
              <div className="rounded-[24px] border border-rose-200 bg-rose-50/80 p-4">
                <div className="text-xs uppercase tracking-[0.24em] text-rose-700">검토 필요</div>
                <div className="mt-2 text-3xl font-display text-ink">{preview?.errors?.length || 0}</div>
              </div>
            </div>

            <div className="mt-5 space-y-3">
              {categorySummaries.length ? (
                categorySummaries.map((item) => (
                  <div key={item.value} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white/75 px-4 py-3">
                    <span className={`badge ${item.tone}`}>{item.shortLabel}</span>
                    <span className="text-sm font-semibold text-ink">{item.count}건</span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">미리보기 생성 후 카테고리별 건수가 표시됩니다.</p>
              )}
            </div>
          </section>

          <section className="shell-panel p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/80">Markdown 예시</p>
            <h3 className="mt-2 text-2xl font-display text-ink">문서를 여러 건으로 나눠서 작성하기</h3>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              각 문서는 제목과 메타데이터를 적고, 문서와 문서 사이는 <code>---</code> 한 줄로 구분하세요. <code>## 내용</code> 섹션이 없으면 본문 전체를 내용으로 간주합니다.
            </p>
            <pre className="mt-4 overflow-x-auto rounded-[24px] border border-slate-200 bg-slate-950 px-4 py-4 text-xs leading-6 text-slate-100">{markdownExample}</pre>
          </section>

          {error ? <div className="shell-panel border border-rose-200 bg-rose-50/80 px-5 py-4 text-sm text-rose-700">{error}</div> : null}
          {result ? (
            <div className="shell-panel border border-emerald-200 bg-emerald-50/80 px-5 py-4 text-sm text-emerald-700">
              등록 완료: 총 {result.total_rows}건 중 {result.created_count}건 생성, {result.failed_count}건 실패
            </div>
          ) : null}
        </div>

        <section className="shell-panel p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">파싱 결과 미리보기</p>
              <h3 className="mt-2 text-2xl font-display text-ink">업로드 전 샘플 확인</h3>
            </div>
            {preview?.errors?.length ? (
              <span className="badge border-rose-200 bg-rose-50 text-rose-700">검토 필요 {preview.errors.length}건</span>
            ) : null}
          </div>

          {preview ? (
            <div className="mt-5 space-y-5">
              {preview.errors.length ? (
                <div className="rounded-[24px] border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-700">
                  {preview.errors.map((issue) => (
                    <p key={`${issue.line}-${issue.message}`}>{issue.line}번 항목: {issue.message}</p>
                  ))}
                </div>
              ) : null}

              <div className="overflow-x-auto rounded-[24px] border border-slate-200">
                <table className="min-w-full bg-white/80 text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
                    <tr>
                      <th className="px-4 py-3">번호</th>
                      <th className="px-4 py-3">분류</th>
                      <th className="px-4 py-3">제목</th>
                      <th className="px-4 py-3">출처</th>
                      <th className="px-4 py-3">날짜</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.slice(0, 8).map((row) => {
                      const categoryMeta = row.category ? getCategoryMeta(row.category) : null
                      return (
                        <tr key={`${preview.kind}-${row.line}`} className="border-t border-slate-200 align-top">
                          <td className="px-4 py-4 text-slate-500">{row.line}</td>
                          <td className="px-4 py-4">
                            {categoryMeta ? <span className={`badge ${categoryMeta.tone}`}>{categoryMeta.shortLabel}</span> : <span className="text-rose-600">분류 오류</span>}
                          </td>
                          <td className="px-4 py-4 text-ink">{row['제목'] || '-'}</td>
                          <td className="px-4 py-4 text-slate-600">{row['출처'] || '-'}</td>
                          <td className="px-4 py-4 text-slate-500">{row['날짜'] || '-'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="mt-5 rounded-[24px] border border-slate-200 bg-white/75 px-5 py-8 text-center text-sm text-slate-500">
              CSV 또는 Markdown 파일을 선택하면 파싱 결과와 카테고리별 통계가 여기에 표시됩니다.
            </div>
          )}
        </section>
      </section>
    </div>
  )
}
