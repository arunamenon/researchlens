import { useState } from 'react'
import { Microscope, RotateCcw, AlertCircle, SlidersHorizontal, FileText, GitBranch, Play, MessageSquare } from 'lucide-react'
import { URLInput } from './components/URLInput'
import { ProgressTracker } from './components/ProgressTracker'
import { ArticleViewer } from './components/ArticleViewer'
import { DiagramViewer } from './components/DiagramViewer'
import { VideoPlayer } from './components/VideoPlayer'
import { QAPanel } from './components/QAPanel'
import { AdminPanel } from './components/AdminPanel'
import { useAnalysis } from './hooks/useAnalysis'
import { useQA } from './hooks/useQA'

type Tab = 'article' | 'diagram' | 'video' | 'qa'

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'article',  label: 'Article',   icon: FileText },
  { id: 'diagram',  label: 'Diagram',   icon: GitBranch },
  { id: 'video',    label: 'Video',     icon: Play },
  { id: 'qa',       label: 'Q&A',       icon: MessageSquare },
]

export default function App() {
  const { status, progress, message, result, jobId, error, analyze, reset } = useAnalysis()
  const { loading: qaLoading, answer, references, mode: qaMode, error: qaError, ask, clear } = useQA(jobId)
  const [activeTab, setActiveTab] = useState<Tab>('article')
  const [showAdmin, setShowAdmin] = useState(false)

  const isAnalyzing = status !== 'idle' && status !== 'complete' && status !== 'error'

  return (
    <div className="min-h-screen bg-navy-950 text-white antialiased">
      {/* Ambient background glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-64 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-indigo-950/40 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative z-10 border-b border-white/6 bg-navy-950/80 backdrop-blur-md sticky top-0">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-indigo-600/20 rounded-lg border border-indigo-500/20">
              <Microscope size={16} className="text-indigo-400" />
            </div>
            <span className="font-semibold text-sm text-white tracking-tight">ResearchLens</span>
          </div>
          <div className="flex items-center gap-1">
            {status !== 'idle' && (
              <button
                onClick={reset}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 hover:text-white hover:bg-white/6 rounded-lg transition-all"
              >
                <RotateCcw size={13} />
                New
              </button>
            )}
            <button
              onClick={() => setShowAdmin(true)}
              title="Model settings"
              className="p-2 text-slate-500 hover:text-slate-300 hover:bg-white/6 rounded-lg transition-all"
            >
              <SlidersHorizontal size={16} />
            </button>
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-5xl mx-auto px-6 py-12 space-y-10">

        {/* ── Idle / Hero ── */}
        {status === 'idle' && (
          <div className="flex flex-col items-center text-center space-y-10 pt-8 animate-fade-in">
            <div className="space-y-4 max-w-xl">
              <h1 className="text-5xl font-bold tracking-tight">
                <span className="bg-gradient-to-br from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                  Deep-dive any
                </span>
                <br />
                <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-indigo-300 bg-clip-text text-transparent">
                  research paper
                </span>
              </h1>
              <p className="text-slate-400 text-base leading-relaxed">
                Paste an arXiv link or any web article. Get a full summary article,
                concept diagram, narrated video, and an AI chatbot — all from local or cloud AI.
              </p>
            </div>
            <URLInput onSubmit={analyze} disabled={false} />

            {/* Feature pills */}
            <div className="flex flex-wrap gap-3 justify-center text-xs text-slate-500">
              {['📄 Deep-dive article', '🔀 Concept diagram', '🎬 Explainer video', '💬 Q&A chatbot'].map(f => (
                <span key={f} className="px-3 py-1.5 bg-white/4 border border-white/8 rounded-full">{f}</span>
              ))}
            </div>
          </div>
        )}

        {/* ── Analyzing ── */}
        {isAnalyzing && (
          <div className="space-y-8 animate-fade-in">
            <URLInput onSubmit={analyze} disabled={true} />
            <div className="bg-navy-900/60 border border-white/8 rounded-2xl p-10">
              <ProgressTracker status={status} progress={progress} message={message} />
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {status === 'error' && (
          <div className="space-y-6 animate-fade-in">
            <URLInput onSubmit={analyze} disabled={false} />
            <div className="flex gap-4 p-5 bg-red-950/40 border border-red-800/50 rounded-2xl">
              <AlertCircle className="text-red-400 shrink-0 mt-0.5" size={18} />
              <div>
                <p className="font-medium text-red-300 text-sm">Analysis failed</p>
                <p className="text-red-400/80 text-xs mt-1 leading-relaxed">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {status === 'complete' && result && (
          <div className="space-y-5 animate-slide-up">
            {/* Tab bar */}
            <div className="flex gap-1 bg-navy-900/60 border border-white/8 rounded-2xl p-1.5 w-fit">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                    activeTab === id
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/50'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon size={14} />
                  {label}
                </button>
              ))}
            </div>

            {/* Tab panel */}
            <div className="bg-navy-900/60 border border-white/8 rounded-2xl p-8 min-h-[400px]">
              {activeTab === 'article' && <ArticleViewer markdown={result.article} />}
              {activeTab === 'diagram' && <DiagramViewer code={result.diagram_code} />}
              {activeTab === 'video' && (
                result.video_url
                  ? <VideoPlayer videoUrl={result.video_url} />
                  : (
                    <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
                      <div className="p-4 bg-amber-950/40 border border-amber-700/30 rounded-2xl">
                        <Play size={24} className="text-amber-500" />
                      </div>
                      <div className="space-y-1.5">
                        <p className="text-slate-300 text-sm font-medium">Video generation failed</p>
                        {result.video_error ? (
                          <p className="text-slate-500 text-xs font-mono bg-navy-800 px-3 py-2 rounded-lg max-w-sm">{result.video_error}</p>
                        ) : (
                          <p className="text-slate-500 text-xs">
                            Requires <code className="text-indigo-300 bg-navy-800 px-1.5 py-0.5 rounded font-mono">ffmpeg</code>
                            {' — '}run <code className="text-indigo-300 bg-navy-800 px-1.5 py-0.5 rounded font-mono">brew install ffmpeg</code>
                          </p>
                        )}
                      </div>
                      <p className="text-slate-600 text-xs">Re-analyze after fixing the issue.</p>
                    </div>
                  )
              )}
              {activeTab === 'qa' && (
                <QAPanel
                  jobId={jobId}
                  urlType={result.url_type}
                  sourceUrl={result.source_url}
                  onAsk={ask}
                  loading={qaLoading}
                  answer={answer}
                  references={references}
                  mode={qaMode}
                  error={qaError}
                  onClear={clear}
                />
              )}
            </div>
          </div>
        )}
      </main>

      {showAdmin && <AdminPanel onClose={() => setShowAdmin(false)} />}
    </div>
  )
}
