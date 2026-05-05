import { useState, FormEvent } from 'react'
import { Send, Loader2, FileText, AlertCircle, X, MessageSquare, BookOpen, Search } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { QAChunk } from '../types'

interface QAPanelProps {
  jobId: string | null
  urlType: string
  sourceUrl: string
  onAsk: (question: string) => void
  loading: boolean
  answer: string | null
  references: QAChunk[]
  mode?: 'holistic' | 'retrieval'
  error: string | null
  onClear: () => void
}

const SUGGESTED = [
  'What is the main contribution of this work?',
  'How does this approach differ from previous methods?',
  'What are the key limitations or challenges mentioned?',
  'What are the practical applications?',
]

export function QAPanel({
  jobId,
  onAsk,
  loading,
  answer,
  references,
  mode,
  error,
  onClear,
}: QAPanelProps) {
  const [question, setQuestion] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const q = question.trim()
    if (q && !loading) onAsk(q)
  }

  const handleSuggestion = (q: string) => {
    setQuestion(q)
    if (!loading) onAsk(q)
  }

  return (
    <div className="space-y-6">
      {/* Question input */}
      <form onSubmit={handleSubmit} className="relative group">
        <div className={`relative flex items-center rounded-xl transition-all duration-200 bg-navy-700/80 border ${
          loading || !jobId ? 'border-white/5 opacity-60' : 'border-white/10 group-focus-within:border-indigo-500/50 group-focus-within:shadow-[0_0_0_3px_rgba(99,102,241,0.1)]'
        }`}>
          <div className="pl-4 text-slate-500">
            <MessageSquare size={16} />
          </div>
          <input
            type="text"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="Ask anything about the content..."
            disabled={loading || !jobId}
            className="flex-1 px-4 py-3.5 bg-transparent text-white placeholder-slate-500 focus:outline-none text-sm"
          />
          <div className="pr-2">
            <button
              type="submit"
              disabled={loading || !question.trim() || !jobId}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-all text-sm"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              Ask
            </button>
          </div>
        </div>
      </form>

      {/* Suggested questions */}
      {!answer && !loading && (
        <div className="animate-fade-in">
          <p className="text-xs text-slate-500 mb-3 font-medium uppercase tracking-wide">Try asking</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED.map(q => (
              <button
                key={q}
                onClick={() => handleSuggestion(q)}
                disabled={loading}
                className="px-3.5 py-2 text-xs bg-navy-700/60 border border-white/8 text-slate-300 hover:text-white hover:border-indigo-500/50 hover:bg-navy-700 rounded-lg transition-all"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 text-indigo-300 text-sm animate-fade-in">
          <Loader2 size={16} className="animate-spin" />
          <span>Searching content and generating answer...</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex gap-3 p-4 bg-red-950/50 border border-red-800/50 rounded-xl text-sm animate-fade-in">
          <AlertCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-red-300 font-medium">Error</p>
            <p className="text-red-400 text-xs mt-1">{error}</p>
          </div>
          <button onClick={onClear} className="text-red-600 hover:text-red-400 transition-colors">
            <X size={15} />
          </button>
        </div>
      )}

      {/* Answer */}
      {answer && !loading && (
        <div className="space-y-5 animate-slide-up">
          {/* Mode badge + clear */}
          <div className="flex items-center justify-between">
            {mode === 'holistic' ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-violet-500/15 text-violet-300 border border-violet-500/25">
                <BookOpen size={11} />
                Full article
              </span>
            ) : mode === 'retrieval' ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                <Search size={11} />
                Focused search
              </span>
            ) : <span />}
            <button
              onClick={onClear}
              className="text-slate-600 hover:text-slate-400 transition-colors"
              title="Clear answer"
            >
              <X size={15} />
            </button>
          </div>

          <div className="prose prose-invert prose-sm max-w-none prose-p:text-slate-300 prose-headings:text-white prose-strong:text-white prose-a:text-indigo-400 prose-code:text-indigo-300 prose-code:bg-navy-700 prose-code:px-1 prose-code:rounded">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
          </div>

          {/* References — only shown in retrieval mode */}
          {mode !== 'holistic' && references.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">
                {references.length} source passage{references.length > 1 ? 's' : ''}
              </p>
              <div className="space-y-2">
                {references.map((ref, i) => {
                  const isArticle = ref.source === 'article'
                  return (
                    <div key={i} className="p-4 bg-navy-700/50 border border-white/6 rounded-xl">
                      <div className="flex items-center gap-2 mb-2">
                        <FileText size={12} className={isArticle ? 'text-violet-400' : 'text-indigo-400'} />
                        <span className="text-slate-400 text-xs font-medium">
                          {isArticle ? 'Article section' : `Passage ${Number(ref.chunk_index) + 1}`}
                        </span>
                      </div>
                      <p className="text-slate-300 text-xs leading-relaxed line-clamp-5">{ref.text}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
