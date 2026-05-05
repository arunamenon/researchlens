import { useState, useCallback } from 'react'
import type { QAResponse } from '../types'

interface QAState {
  loading: boolean
  answer: string | null
  references: QAResponse['references']
  mode: QAResponse['mode']
  error: string | null
}

export function useQA(jobId: string | null) {
  const [state, setState] = useState<QAState>({
    loading: false,
    answer: null,
    references: [],
    mode: undefined,
    error: null,
  })

  const ask = useCallback(async (question: string) => {
    if (!jobId || !question.trim()) return

    setState({ loading: true, answer: null, references: [], mode: undefined, error: null })

    try {
      const res = await fetch(`/api/ask/${jobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data: QAResponse = await res.json()
      setState({ loading: false, answer: data.answer, references: data.references, mode: data.mode, error: null })
    } catch (e) {
      setState({ loading: false, answer: null, references: [], mode: undefined, error: String(e) })
    }
  }, [jobId])

  const clear = useCallback(() => {
    setState({ loading: false, answer: null, references: [], mode: undefined, error: null })
  }, [])

  return { ...state, ask, clear }
}
