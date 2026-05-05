export type AnalysisStatus =
  | 'idle'
  | 'extracting'
  | 'article'
  | 'diagram'
  | 'video'
  | 'complete'
  | 'error'

export interface ProgressEvent {
  type: 'progress' | 'complete' | 'error' | 'heartbeat'
  stage?: string
  message?: string
  progress?: number
  article?: string
  diagram_code?: string
  video_url?: string | null
  video_error?: string | null
  url_type?: string
  source_url?: string
  detail?: string
}

export interface AnalysisResult {
  article: string
  diagram_code: string
  video_url: string | null
  video_error: string | null
  url_type: string
  source_url: string
}

export interface QAChunk {
  chunk_index: number | string
  text: string
  source?: 'article' | 'content'
}

export interface QAResponse {
  answer: string
  references: QAChunk[]
  mode?: 'holistic' | 'retrieval'
}
