import { useEffect, useMemo, useState } from 'react'

import { clearSessionSettings, fetchSettingsStatus, saveCredentials } from '../lib/api'

const sourceLabels = {
  memory: '이번 실행',
  file: '저장된 설정',
  env: '.env 파일',
  missing: '미설정',
}

const providerOptions = [
  {
    value: 'anthropic',
    label: 'Anthropic Claude',
    description: '현재 기본 구현과 가장 자연스럽게 연결되는 제공자입니다.',
  },
  {
    value: 'openai',
    label: 'OpenAI',
    description: 'OpenAI API Key를 저장하고 최종 답변 생성에 사용할 수 있습니다.',
  },
  {
    value: 'gemini',
    label: 'Google Gemini',
    description: 'Gemini API Key를 저장하고 최종 답변 생성에 사용할 수 있습니다.',
  },
  {
    value: 'glm',
    label: 'Zhipu GLM',
    description: 'GLM API Key를 저장하고 최종 답변 생성에 사용할 수 있습니다.',
  },
]

const modeCards = [
  {
    value: 'session',
    label: '이번 실행만 적용',
    description: '서버를 다시 켜면 다시 입력해야 합니다. 테스트용으로 가볍게 쓰기 좋습니다.',
  },
  {
    value: 'saved',
    label: '계속 저장',
    description: '로컬 파일에 저장해 다음 실행에도 유지합니다. 같은 PC에서 반복 사용하기 좋습니다.',
  },
]

const credentialFields = [
  {
    key: 'anthropicApiKey',
    payloadKey: 'anthropic_api_key',
    label: 'Anthropic API Key',
    placeholder: 'sk-ant-...',
    helper: 'Claude를 최종 답변 생성 모델로 쓸 때 사용합니다.',
  },
  {
    key: 'openaiApiKey',
    payloadKey: 'openai_api_key',
    label: 'OpenAI API Key',
    placeholder: 'sk-...',
    helper: 'OpenAI를 최종 답변 생성 모델로 쓸 때 사용합니다.',
  },
  {
    key: 'geminiApiKey',
    payloadKey: 'gemini_api_key',
    label: 'Gemini API Key',
    placeholder: 'AIza...',
    helper: 'Google Gemini를 최종 답변 생성 모델로 쓸 때 사용합니다.',
  },
  {
    key: 'glmApiKey',
    payloadKey: 'glm_api_key',
    label: 'GLM API Key',
    placeholder: 'Zhipu GLM API Key',
    helper: 'Zhipu GLM을 최종 답변 생성 모델로 쓸 때 사용합니다.',
  },
]

function StatusBadge({ configured, source, saved }) {
  const tone = configured ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'
  return (
    <div className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold tracking-[0.16em] uppercase ${tone}`}>
      {configured ? `${sourceLabels[source] || source}${saved ? ' · 저장됨' : ''}` : '미설정'}
    </div>
  )
}

function SettingStatusCard({ title, helper, status }) {
  return (
    <article className="rounded-[24px] border border-slate-200 bg-white/85 p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold text-ink">{title}</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{helper}</p>
        </div>
        <StatusBadge configured={status?.configured} source={status?.source} saved={status?.saved} />
      </div>
    </article>
  )
}

function ProviderCard({ option, active, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(option.value)}
      className={`rounded-[24px] border px-5 py-5 text-left transition ${
        active ? 'border-moss bg-ink text-white shadow-float' : 'border-slate-200 bg-white/90 text-ink hover:border-moss/40'
      }`}
    >
      <div className="text-sm font-semibold tracking-[0.16em] uppercase">{option.label}</div>
      <p className={`mt-3 text-sm leading-6 ${active ? 'text-white/80' : 'text-slate-600'}`}>{option.description}</p>
    </button>
  )
}

export default function SettingsPage() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [mode, setMode] = useState('session')
  const [provider, setProvider] = useState('anthropic')
  const [anthropicApiKey, setAnthropicApiKey] = useState('')
  const [openaiApiKey, setOpenaiApiKey] = useState('')
  const [geminiApiKey, setGeminiApiKey] = useState('')
  const [glmApiKey, setGlmApiKey] = useState('')
  const [lawOc, setLawOc] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadStatus() {
    setLoading(true)
    try {
      const next = await fetchSettingsStatus()
      setStatus(next)
      setProvider(next?.llm_provider?.active || 'anthropic')
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const modeDescription = useMemo(() => modeCards.find((item) => item.value === mode)?.description || '', [mode])
  const activeProviderLabel = useMemo(() => providerOptions.find((item) => item.value === provider)?.label || provider, [provider])

  async function handleSubmit(event) {
    event.preventDefault()

    const payload = {
      anthropic_api_key: anthropicApiKey || undefined,
      openai_api_key: openaiApiKey || undefined,
      gemini_api_key: geminiApiKey || undefined,
      glm_api_key: glmApiKey || undefined,
      law_oc: lawOc || undefined,
      llm_provider: provider,
      mode,
    }

    setSaving(true)
    try {
      const response = await saveCredentials(payload)
      setStatus(response.settings)
      setProvider(response.settings?.llm_provider?.active || provider)
      setMessage(response.message)
      setError('')
      setAnthropicApiKey('')
      setOpenaiApiKey('')
      setGeminiApiKey('')
      setGlmApiKey('')
      setLawOc('')
    } catch (requestError) {
      setError(requestError.message)
      setMessage('')
    } finally {
      setSaving(false)
    }
  }

  async function handleClearSession() {
    setClearing(true)
    try {
      const response = await clearSessionSettings()
      setStatus(response.settings)
      setProvider(response.settings?.llm_provider?.active || 'anthropic')
      setMessage(response.message)
      setError('')
    } catch (requestError) {
      setError(requestError.message)
      setMessage('')
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="space-y-4">
      <section className="shell-panel mesh-surface overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-moss/70">Connection Settings</p>
            <h2 className="mt-3 font-pretendard text-4xl font-bold leading-tight text-ink sm:text-5xl">답변 제공자와 외부검색 키를 화면에서 선택하고 바로 적용할 수 있습니다.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
              Anthropic, OpenAI, Gemini, GLM 키를 저장하고 어떤 제공자로 최종 답변을 생성할지 선택할 수 있습니다. LAW_OC는 판례, 심판례, 법령 외부검색에 계속 사용됩니다.
            </p>
          </div>

          <div className="rounded-[24px] border border-white/70 bg-white/80 px-5 py-4 shadow-panel sm:min-w-[320px]">
            <div className="text-sm font-semibold text-ink">현재 활성 제공자</div>
            <div className="mt-2 text-lg font-semibold text-moss">{status?.llm_provider?.active ? providerOptions.find((item) => item.value === status.llm_provider.active)?.label || status.llm_provider.active : activeProviderLabel}</div>
            <div className="mt-2 text-xs leading-6 text-slate-500">
              이번 실행만 적용: 서버 재시작 전까지만 유지됩니다.
              <br />
              계속 저장: 로컬 파일에 저장되어 다음 실행에도 유지됩니다.
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="space-y-4">
          <section className="shell-panel p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">입력</p>
                <h3 className="mt-2 text-2xl font-display text-ink">연동 키와 답변 제공자 적용</h3>
              </div>
              <button type="button" className="secondary-button px-4 py-3" onClick={handleClearSession} disabled={clearing}>
                {clearing ? '초기화 중...' : '임시 설정 초기화'}
              </button>
            </div>

            <form onSubmit={handleSubmit} className="mt-6 space-y-6">
              <div>
                <div className="text-sm font-semibold text-slate-700">답변 제공자 선택</div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {providerOptions.map((option) => (
                    <ProviderCard key={option.value} option={option} active={provider === option.value} onSelect={setProvider} />
                  ))}
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                {modeCards.map((item) => {
                  const active = mode === item.value
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

              <div className="grid gap-5 md:grid-cols-2">
                <label className="block">
                  <span className="text-sm font-semibold text-slate-700">Anthropic API Key</span>
                  <input
                    className="field-input mt-3"
                    type="password"
                    value={anthropicApiKey}
                    onChange={(event) => setAnthropicApiKey(event.target.value)}
                    placeholder="sk-ant-..."
                    autoComplete="off"
                  />
                  <p className="mt-3 text-xs leading-6 text-slate-500">Claude를 최종 답변 생성 모델로 쓸 때 사용합니다.</p>
                </label>

                <label className="block">
                  <span className="text-sm font-semibold text-slate-700">OpenAI API Key</span>
                  <input
                    className="field-input mt-3"
                    type="password"
                    value={openaiApiKey}
                    onChange={(event) => setOpenaiApiKey(event.target.value)}
                    placeholder="sk-..."
                    autoComplete="off"
                  />
                  <p className="mt-3 text-xs leading-6 text-slate-500">OpenAI를 최종 답변 생성 모델로 쓸 때 사용합니다.</p>
                </label>

                <label className="block">
                  <span className="text-sm font-semibold text-slate-700">Gemini API Key</span>
                  <input
                    className="field-input mt-3"
                    type="password"
                    value={geminiApiKey}
                    onChange={(event) => setGeminiApiKey(event.target.value)}
                    placeholder="AIza..."
                    autoComplete="off"
                  />
                  <p className="mt-3 text-xs leading-6 text-slate-500">Google Gemini를 최종 답변 생성 모델로 쓸 때 사용합니다.</p>
                </label>

                <label className="block">
                  <span className="text-sm font-semibold text-slate-700">GLM API Key</span>
                  <input
                    className="field-input mt-3"
                    type="password"
                    value={glmApiKey}
                    onChange={(event) => setGlmApiKey(event.target.value)}
                    placeholder="Zhipu GLM API Key"
                    autoComplete="off"
                  />
                  <p className="mt-3 text-xs leading-6 text-slate-500">Zhipu GLM을 최종 답변 생성 모델로 쓸 때 사용합니다.</p>
                </label>
              </div>

              <label className="block">
                <span className="text-sm font-semibold text-slate-700">LAW_OC</span>
                <input
                  className="field-input mt-3"
                  type="password"
                  value={lawOc}
                  onChange={(event) => setLawOc(event.target.value)}
                  placeholder="국가법령정보 OC 값을 입력하세요"
                  autoComplete="off"
                />
                <p className="mt-3 text-xs leading-6 text-slate-500">
                  LAW_OC는 국가법령정보 공동활용 OPEN API에서 발급받아 사용합니다. 아래 안내 카드의 공식 링크에서 회원가입과 활용신청 순서를 확인할 수 있습니다.
                </p>
              </label>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs leading-6 text-slate-500">
                  보안을 위해 입력한 값은 다시 화면에 표시하지 않습니다. 키를 새로 입력하지 않아도 제공자 선택만 바꿔서 적용할 수 있습니다.
                </p>
                <button type="submit" className="primary-button" disabled={saving}>
                  {saving ? '적용 중...' : mode === 'saved' ? '저장하고 적용' : '이번 실행에만 적용'}
                </button>
              </div>
            </form>
          </section>

          {message ? <div className="shell-panel border border-emerald-200 bg-emerald-50/85 px-5 py-4 text-sm text-emerald-700">{message}</div> : null}
          {error ? <div className="shell-panel border border-rose-200 bg-rose-50/85 px-5 py-4 text-sm text-rose-700">{error}</div> : null}
        </div>

        <aside className="space-y-4">
          <section className="shell-panel p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss/70">현재 상태</p>
            <div className="mt-4 rounded-[24px] border border-moss/20 bg-moss/5 p-5">
              <div className="text-sm font-semibold text-slate-500">현재 활성 답변 제공자</div>
              <div className="mt-2 text-xl font-semibold text-ink">{providerOptions.find((item) => item.value === status?.llm_provider?.active)?.label || 'Anthropic Claude'}</div>
              <div className="mt-2 text-xs leading-6 text-slate-500">
                {status?.llm_provider?.selected ? '사용자가 직접 선택한 제공자가 적용 중입니다.' : '명시적으로 선택하지 않으면 저장된 키를 기준으로 자동 선택됩니다.'}
              </div>
            </div>
            <div className="mt-4 space-y-3">
              <SettingStatusCard title="Anthropic 키" helper="Claude 답변 생성에 사용합니다." status={status?.anthropic} />
              <SettingStatusCard title="OpenAI 키" helper="OpenAI 답변 생성에 사용합니다." status={status?.openai} />
              <SettingStatusCard title="Gemini 키" helper="Gemini 답변 생성에 사용합니다." status={status?.gemini} />
              <SettingStatusCard title="GLM 키" helper="GLM 답변 생성에 사용합니다." status={status?.glm} />
              <SettingStatusCard title="국가법령정보 외부검색" helper="판례, 심판례, 법령을 외부에서 조회할 때 사용합니다." status={status?.law_oc} />
            </div>
            <button type="button" className="secondary-button mt-4 w-full" onClick={loadStatus} disabled={loading}>
              {loading ? '새로고침 중...' : '상태 새로고침'}
            </button>
          </section>

          <section className="shell-panel p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-700/80">LAW_OC 받는 방법</p>
            <div className="mt-3 rounded-[24px] border border-sky-200 bg-sky-50/85 p-5 text-sm leading-7 text-slate-700">
              <ol className="list-decimal space-y-2 pl-5">
                <li>국가법령정보 공동활용 사이트에서 회원가입을 합니다.</li>
                <li>원하는 OPEN API에 대해 공동활용 신청을 진행합니다.</li>
                <li>승인 후 OC 값을 입력합니다. 공식 안내 기준으로 OPEN API 이용 시 OC는 로그인 이메일의 아이디 부분을 사용합니다.</li>
              </ol>
              <p className="mt-4 text-xs leading-6 text-slate-500">
                예: <span className="font-mono">taxteam@example.com</span> 으로 가입했다면 OC는 <span className="font-mono">taxteam</span> 형태입니다.
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <a href="https://open.law.go.kr/LSO/information/guide.do" target="_blank" rel="noreferrer" className="secondary-button px-4 py-2">
                  공동활용 이용안내 열기
                </a>
                <a href="https://open.law.go.kr/LSO/openApi/guideResult.do" target="_blank" rel="noreferrer" className="secondary-button px-4 py-2">
                  OPEN API 가이드 열기
                </a>
              </div>
            </div>
          </section>

          <section className="shell-panel p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/80">저장 안내</p>
            <div className="mt-3 rounded-[24px] border border-amber-200 bg-amber-50/85 p-5 text-sm leading-7 text-slate-700">
              계속 저장을 선택하면 값은 로컬 PC의 설정 파일에 저장됩니다.
              {status?.settings_path ? (
                <>
                  <br />
                  <span className="font-mono text-xs text-slate-500">{status.settings_path}</span>
                </>
              ) : null}
            </div>
          </section>
        </aside>
      </section>
    </div>
  )
}
