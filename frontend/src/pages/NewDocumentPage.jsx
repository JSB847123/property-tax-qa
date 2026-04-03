import { useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'

import DocumentForm from '../components/DocumentForm'
import { createDocument } from '../lib/api'
import { createEmptyDocumentForm, formToPayload } from '../lib/documents'

export default function NewDocumentPage() {
  const navigate = useNavigate()
  const { refreshStats } = useOutletContext()
  const [form, setForm] = useState(createEmptyDocumentForm())
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccessMessage('')

    try {
      await createDocument(formToPayload(form))
      await refreshStats()
      setSuccessMessage('자료가 저장되었습니다. 자료관리 화면으로 이동합니다.')
      setTimeout(() => {
        navigate('/documents')
      }, 700)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <section className="shell-panel mesh-surface p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-moss/70">Document Intake</p>
        <h2 className="mt-3 font-display text-4xl text-ink">새 실무자료를 체계적으로 등록합니다.</h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
          판단 기준, 민원 설명 논리, 전산 단계까지 한 번에 정리해 두면 이후 채팅 답변과 내부 검색 품질이 함께 좋아집니다.
        </p>
      </section>

      {error ? <div className="shell-panel border border-rose-200 bg-rose-50/80 px-5 py-4 text-sm text-rose-700">{error}</div> : null}
      {successMessage ? <div className="shell-panel border border-emerald-200 bg-emerald-50/80 px-5 py-4 text-sm text-emerald-700">{successMessage}</div> : null}

      <DocumentForm
        form={form}
        onChange={(field, value) => setForm((current) => ({ ...current, [field]: value }))}
        onSubmit={handleSubmit}
        submitLabel="자료 등록"
        submitting={submitting}
      />
    </div>
  )
}
