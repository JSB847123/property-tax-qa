import { categoryOptions, getCategoryMeta } from '../lib/categories'

export default function DocumentForm({
  form,
  onChange,
  onSubmit,
  submitLabel,
  submitting = false,
  secondaryAction = null,
}) {
  const categoryMeta = getCategoryMeta(form.category)

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="shell-panel mesh-surface p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">문서 기본 정보</p>
              <h3 className="mt-2 text-2xl font-display text-ink">분류와 메타데이터</h3>
            </div>
            <span className={`badge ${categoryMeta.tone}`}>{categoryMeta.label}</span>
          </div>

          <div className="mt-6 grid gap-5 md:grid-cols-2">
            <label className="space-y-2 md:col-span-2">
              <span className="text-sm font-semibold text-slate-700">분류</span>
              <select className="field-input" value={form.category} onChange={(event) => onChange('category', event.target.value)}>
                {categoryOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="text-sm leading-6 text-slate-500">{categoryMeta.description}</p>
            </label>

            <label className="space-y-2 md:col-span-2">
              <span className="text-sm font-semibold text-slate-700">제목</span>
              <input className="field-input" value={form.title} onChange={(event) => onChange('title', event.target.value)} placeholder="예: 사실상 취득의 판단 기준 정리" required />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-semibold text-slate-700">출처</span>
              <input className="field-input" value={form.source} onChange={(event) => onChange('source', event.target.value)} placeholder="예: 내부 검토 메모" required />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-semibold text-slate-700">날짜</span>
              <input type="date" className="field-input" value={form.date} onChange={(event) => onChange('date', event.target.value)} required />
            </label>

            <label className="space-y-2 md:col-span-2">
              <span className="text-sm font-semibold text-slate-700">태그</span>
              <input
                className="field-input"
                value={form.tagText}
                onChange={(event) => onChange('tagText', event.target.value)}
                placeholder="세미콜론 또는 쉼표로 구분하세요. 예: 취득세; 사실상취득; 경정"
              />
            </label>
          </div>
        </section>

        <section className="shell-panel p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700/80">전산 메모</p>
          <h3 className="mt-2 text-2xl font-display text-ink">실무 적용 포인트</h3>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            전산적용 입력란은 실제 화면 조작, 검증 포인트, 후속 결재 흐름처럼 실무자가 바로 따라 할 수 있는 순서 중심으로 남겨두면 좋습니다.
          </p>

          <div className="mt-5 rounded-[28px] border border-emerald-200 bg-emerald-50/80 p-5 shadow-inner">
            <label className="space-y-2">
              <span className="text-sm font-semibold text-emerald-900">🖥️ 전산적용</span>
              <textarea
                className="field-textarea border-emerald-200 bg-white/80 focus:border-emerald-500 focus:ring-emerald-100"
                value={form.practical}
                onChange={(event) => onChange('practical', event.target.value)}
                placeholder="예: 위택스 자료 조회 → 과세대장 확인 → 감면코드 검증 → 세액 재계산"
              />
            </label>
          </div>
        </section>
      </div>

      <section className="shell-panel p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">본문</p>
        <h3 className="mt-2 text-2xl font-display text-ink">내용 작성</h3>
        <div className="mt-5">
          <textarea
            className="field-textarea min-h-[260px]"
            value={form.content}
            onChange={(event) => onChange('content', event.target.value)}
            placeholder="쟁점, 사실관계, 판단 기준, 설명 논리, 유의사항을 정리하세요."
            required
          />
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? '저장 중...' : submitLabel}
          </button>
          {secondaryAction}
        </div>
      </section>
    </form>
  )
}
