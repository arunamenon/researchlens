import { Check, Loader2 } from 'lucide-react'
import type { AnalysisStatus } from '../types'

interface ProgressTrackerProps {
  status: AnalysisStatus
  progress: number
  message: string
}

const STAGES: { key: AnalysisStatus; label: string; sublabel: string }[] = [
  { key: 'extracting', label: 'Extracting', sublabel: 'Fetching content' },
  { key: 'article',    label: 'Writing',    sublabel: 'Generating article' },
  { key: 'diagram',    label: 'Diagram',    sublabel: 'Building flowchart' },
  { key: 'video',      label: 'Video',      sublabel: 'Rendering slides' },
  { key: 'complete',   label: 'Done',       sublabel: 'Analysis complete' },
]

const ORDER: AnalysisStatus[] = ['extracting', 'article', 'diagram', 'video', 'complete']

function stageIndex(status: AnalysisStatus): number {
  return ORDER.indexOf(status)
}

export function ProgressTracker({ status, progress, message }: ProgressTrackerProps) {
  const currentIdx = stageIndex(status)

  return (
    <div className="w-full max-w-xl mx-auto space-y-8">
      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <p className="text-sm text-slate-300 font-medium truncate max-w-xs">{message}</p>
          <span className="text-xs text-slate-500 font-mono tabular-nums">{progress}%</span>
        </div>
        <div className="w-full bg-navy-700 rounded-full h-1.5 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-violet-500 transition-all duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Stage steps */}
      <div className="flex items-center gap-0">
        {STAGES.map((stage, idx) => {
          const done = idx < currentIdx || status === 'complete'
          const active = idx === currentIdx && status !== 'complete'
          const upcoming = idx > currentIdx && status !== 'complete'
          const isLast = idx === STAGES.length - 1

          return (
            <div key={stage.key} className="flex items-center flex-1">
              <div className="flex flex-col items-center gap-1.5">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 ${
                  done
                    ? 'bg-indigo-600 border-2 border-indigo-500'
                    : active
                    ? 'bg-navy-800 border-2 border-indigo-500 shadow-[0_0_12px_rgba(99,102,241,0.4)]'
                    : 'bg-navy-800 border-2 border-white/10'
                }`}>
                  {done ? (
                    <Check size={14} className="text-white" />
                  ) : active ? (
                    <Loader2 size={14} className="text-indigo-400 animate-spin" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-slate-600" />
                  )}
                </div>
                <div className="text-center">
                  <p className={`text-xs font-medium leading-none ${
                    done ? 'text-indigo-300' : active ? 'text-white' : upcoming ? 'text-slate-600' : 'text-slate-400'
                  }`}>{stage.label}</p>
                </div>
              </div>
              {!isLast && (
                <div className={`flex-1 h-px mx-2 mb-5 transition-all duration-500 ${
                  done ? 'bg-indigo-600' : 'bg-white/8'
                }`} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
