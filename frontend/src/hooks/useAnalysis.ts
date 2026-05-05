import { useState, useRef, useCallback } from 'react'
import type { AnalysisStatus, AnalysisResult, ProgressEvent } from '../types'

interface AnalysisState {
  status: AnalysisStatus
  progress: number
  message: string
  result: AnalysisResult | null
  jobId: string | null
  error: string | null
}

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({
    status: 'idle',
    progress: 0,
    message: '',
    result: null,
    jobId: null,
    error: null,
  })
  const eventSourceRef = useRef<EventSource | null>(null)

  const analyze = useCallback(async (url: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setState({ status: 'extracting', progress: 0, message: 'Starting analysis...', result: null, jobId: null, error: null })

    let jobId: string
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      jobId = data.job_id
    } catch (e) {
      setState(prev => ({ ...prev, status: 'error', error: String(e) }))
      return
    }

    setState(prev => ({ ...prev, jobId }))

    const es = new EventSource(`/api/stream/${jobId}`)
    eventSourceRef.current = es

    es.onmessage = (event) => {
      try {
        const payload: ProgressEvent = JSON.parse(event.data)
        if (payload.type === 'heartbeat') return

        if (payload.type === 'progress') {
          setState(prev => ({
            ...prev,
            status: (payload.stage as AnalysisStatus) || prev.status,
            progress: payload.progress ?? prev.progress,
            message: payload.message ?? prev.message,
          }))
        }

        if (payload.type === 'complete') {
          es.close()
          setState({
            status: 'complete',
            progress: 100,
            message: 'Analysis complete!',
            jobId,
            result: {
              article: payload.article ?? '',
              diagram_code: payload.diagram_code ?? '',
              video_url: payload.video_url ?? null,
              video_error: payload.video_error ?? null,
              url_type: payload.url_type ?? 'general',
              source_url: payload.source_url ?? '',
            },
            error: null,
          })
        }

        if (payload.type === 'error') {
          es.close()
          setState(prev => ({
            ...prev,
            status: 'error',
            error: payload.message ?? 'An unknown error occurred.',
          }))
        }
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      es.close()
      setState(prev => {
        if (prev.status !== 'complete') {
          return { ...prev, status: 'error', error: 'Connection to server lost.' }
        }
        return prev
      })
    }
  }, [])

  const reset = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    setState({ status: 'idle', progress: 0, message: '', result: null, jobId: null, error: null })
  }, [])

  return { ...state, analyze, reset }
}
