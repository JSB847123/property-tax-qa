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

export const publicCategoryOptions = [
  {
    value: 'admin_rule',
    label: '행정규칙',
    shortLabel: '행정규칙',
    description: '고시, 훈령, 예규 등 행정규칙 공개자료입니다.',
    tone: 'border-teal-200 bg-teal-50 text-teal-700',
  },
  {
    value: 'ordinance',
    label: '자치법규',
    shortLabel: '자치법규',
    description: '지방자치단체 조례와 규칙 공개자료입니다.',
    tone: 'border-cyan-200 bg-cyan-50 text-cyan-700',
  },
  {
    value: 'treaty',
    label: '조약',
    shortLabel: '조약',
    description: '국가 간 조약과 협정 공개자료입니다.',
    tone: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  },
  {
    value: 'interpretation',
    label: '해석례',
    shortLabel: '해석례',
    description: '법령해석, 질의회신, 유권해석 공개자료입니다.',
    tone: 'border-lime-200 bg-lime-50 text-lime-800',
  },
  {
    value: 'tax_tribunal',
    label: '조세심판례',
    shortLabel: '조세심판례',
    description: '조세심판원 결정 공개자료입니다.',
    tone: 'border-purple-200 bg-purple-50 text-purple-700',
  },
  {
    value: 'customs',
    label: '관세해석',
    shortLabel: '관세해석',
    description: '관세 관련 결정과 해석 공개자료입니다.',
    tone: 'border-blue-200 bg-blue-50 text-blue-700',
  },
  {
    value: 'nts',
    label: '국세청해석',
    shortLabel: '국세청해석',
    description: '국세청 해석과 질의회신 공개자료입니다.',
    tone: 'border-orange-200 bg-orange-50 text-orange-700',
  },
  {
    value: 'constitutional',
    label: '헌재결정',
    shortLabel: '헌재결정',
    description: '헌법재판소 결정 공개자료입니다.',
    tone: 'border-pink-200 bg-pink-50 text-pink-700',
  },
  {
    value: 'admin_appeal',
    label: '행정심판례',
    shortLabel: '행정심판례',
    description: '행정심판 재결 공개자료입니다.',
    tone: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700',
  },
]

export const categoryMap = Object.fromEntries([...categoryOptions, ...publicCategoryOptions].map((item) => [item.value, item]))
export const koreanCategoryMap = {
  판례: 'precedent',
  심판례: 'tribunal',
  사례: 'case',
  민원처리: 'civil',
  이론: 'theory',
  법령: 'statute',
  행정규칙: 'admin_rule',
  자치법규: 'ordinance',
  조약: 'treaty',
  해석례: 'interpretation',
  조세심판례: 'tax_tribunal',
  관세해석: 'customs',
  국세청해석: 'nts',
  헌재결정: 'constitutional',
  행정심판례: 'admin_appeal',
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
