export const categoryOptions = [
  {
    value: 'precedent',
    label: '판례',
    shortLabel: '판례',
    description: '법원 판결과 판시 논리를 정리하는 자료입니다.',
    tone: 'border-sky-200 bg-sky-50 text-sky-700',
  },
  {
    value: 'tribunal',
    label: '심판례',
    shortLabel: '심판례',
    description: '조세심판원 또는 특별행정심판 재결 논리를 정리하는 자료입니다.',
    tone: 'border-violet-200 bg-violet-50 text-violet-700',
  },
  {
    value: 'case',
    label: '사례',
    shortLabel: '사례',
    description: '질의회신, 참고사례, 내부 검토 사례를 축적하는 공간입니다.',
    tone: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  {
    value: 'civil',
    label: '민원처리',
    shortLabel: '민원처리',
    description: '실제 민원 응대 과정과 해결 경로, 설명 포인트를 기록합니다.',
    tone: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  {
    value: 'theory',
    label: '이론',
    shortLabel: '이론',
    description: '쟁점별 해석론, 판단 기준, 내부 정리 메모를 축적합니다.',
    tone: 'border-rose-200 bg-rose-50 text-rose-700',
  },
  {
    value: 'statute',
    label: '법령',
    shortLabel: '법령',
    description: '조문, 시행령, 시행규칙과 실무상 핵심 문구를 기록합니다.',
    tone: 'border-stone-200 bg-stone-50 text-stone-700',
  },
  {
    value: 'other',
    label: '기타',
    shortLabel: '기타',
    description: '기존 분류에 딱 맞지 않는 참고자료, 메모, 보조 문서를 임시 또는 일반 분류로 저장합니다.',
    tone: 'border-slate-300 bg-slate-100 text-slate-700',
  },
]

export const categoryMap = Object.fromEntries(categoryOptions.map((item) => [item.value, item]))
export const koreanCategoryMap = {
  판례: 'precedent',
  심판례: 'tribunal',
  사례: 'case',
  민원처리: 'civil',
  이론: 'theory',
  법령: 'statute',
  기타: 'other',
}

export function getCategoryMeta(category) {
  return categoryMap[category] ?? {
    value: category,
    label: category || '미분류',
    shortLabel: category || '미분류',
    description: '분류 설명이 아직 등록되지 않았습니다.',
    tone: 'border-slate-200 bg-slate-50 text-slate-700',
  }
}
