import { useState, FormEvent } from 'react'
import { ArrowRight, BookOpen, Globe, Sparkles } from 'lucide-react'

interface URLInputProps {
  onSubmit: (url: string) => void
  disabled: boolean
}

export function URLInput({ onSubmit, disabled }: URLInputProps) {
  const [url, setUrl] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = url.trim()
    if (trimmed) onSubmit(trimmed)
  }

  return (
    <div className="w-full max-w-2xl mx-auto animate-slide-up">
      <form onSubmit={handleSubmit} className="relative group">
        <div className={`relative flex items-center rounded-2xl transition-all duration-200 ${
          disabled ? 'opacity-60' : ''
        } bg-navy-800 border ${
          disabled ? 'border-white/5' : 'border-white/10 group-focus-within:border-indigo-500/60 group-focus-within:shadow-[0_0_0_3px_rgba(99,102,241,0.12)]'
        }`}>
          <div className="pl-5 pr-1 text-slate-500">
            <Sparkles size={17} className={disabled ? '' : 'group-focus-within:text-indigo-400 transition-colors'} />
          </div>
          <input
            type="url"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="Paste an arXiv paper or website URL..."
            disabled={disabled}
            className="flex-1 px-4 py-4 bg-transparent text-white placeholder-slate-500 focus:outline-none text-sm"
            autoComplete="off"
          />
          <div className="pr-2">
            <button
              type="submit"
              disabled={disabled || !url.trim()}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-all duration-150 text-sm"
            >
              Analyze
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </form>

      <div className="flex gap-5 mt-4 justify-center text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <BookOpen size={13} className="text-emerald-500" /> arXiv papers
        </span>
        <span className="flex items-center gap-1.5 text-slate-600">·</span>
        <span className="flex items-center gap-1.5">
          <Globe size={13} className="text-sky-400" /> Web articles &amp; blogs
        </span>
      </div>
    </div>
  )
}
