import { useState, useEffect, FormEvent } from 'react'
import { SlidersHorizontal, X, Save, Loader2, CheckCircle, AlertCircle, Server, Zap, Brain } from 'lucide-react'

interface ProviderConfig {
  provider: 'ollama' | 'openai' | 'anthropic'
  model: string
  api_key: string
  base_url: string
}

const PROVIDER_DEFAULTS: Record<string, Partial<ProviderConfig>> = {
  ollama: { model: 'llama3', base_url: 'http://localhost:11434/v1' },
  openai: { model: 'gpt-4o-mini', base_url: '' },
  anthropic: { model: 'claude-opus-4-7', base_url: '' },
}

const PROVIDERS: { id: 'ollama' | 'openai' | 'anthropic'; label: string; sub: string; icon: React.ElementType }[] = [
  { id: 'ollama', label: 'Ollama', sub: 'Local', icon: Server },
  { id: 'openai', label: 'OpenAI', sub: 'Cloud', icon: Zap },
  { id: 'anthropic', label: 'Anthropic', sub: 'Cloud', icon: Brain },
]

interface AdminPanelProps {
  onClose: () => void
}

export function AdminPanel({ onClose }: AdminPanelProps) {
  const [config, setConfig] = useState<ProviderConfig>({
    provider: 'ollama',
    model: 'llama3',
    api_key: '',
    base_url: 'http://localhost:11434/v1',
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(data => setConfig(prev => ({
        ...prev,
        provider: data.provider || 'ollama',
        model: data.model || 'llama3',
        base_url: data.base_url || 'http://localhost:11434/v1',
      })))
      .catch(() => {})
  }, [])

  const handleProviderChange = (provider: ProviderConfig['provider']) => {
    const defaults = PROVIDER_DEFAULTS[provider]
    setConfig(prev => ({
      ...prev,
      provider,
      model: defaults?.model ?? prev.model,
      base_url: defaults?.base_url ?? '',
      api_key: '',
    }))
  }

  const handleSave = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const resp = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      if (!resp.ok) {
        const data = await resp.json()
        throw new Error(data.detail || 'Failed to save settings')
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-navy-900 border border-white/10 rounded-2xl w-full max-w-md shadow-2xl animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/8">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-indigo-600/20 rounded-lg">
              <SlidersHorizontal size={16} className="text-indigo-400" />
            </div>
            <h2 className="text-white font-semibold text-sm">Model Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-500 hover:text-slate-300 hover:bg-white/8 rounded-lg transition-all"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSave} className="p-6 space-y-5">
          {/* Provider selector */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Provider</label>
            <div className="grid grid-cols-3 gap-2">
              {PROVIDERS.map(({ id, label, sub, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => handleProviderChange(id)}
                  className={`py-3 px-3 rounded-xl text-sm transition-all border flex flex-col items-center gap-1 ${
                    config.provider === id
                      ? 'bg-indigo-600/20 border-indigo-500/60 text-white'
                      : 'bg-navy-800 border-white/8 text-slate-400 hover:text-white hover:border-white/15'
                  }`}
                >
                  <Icon size={16} className={config.provider === id ? 'text-indigo-400' : ''} />
                  <span className="font-medium leading-none">{label}</span>
                  <span className={`text-[10px] leading-none ${config.provider === id ? 'text-indigo-400' : 'text-slate-600'}`}>{sub}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Model name */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Model</label>
            <input
              type="text"
              value={config.model}
              onChange={e => setConfig(prev => ({ ...prev, model: e.target.value }))}
              placeholder={PROVIDER_DEFAULTS[config.provider]?.model ?? 'model name'}
              className="w-full px-4 py-2.5 rounded-xl bg-navy-800 border border-white/8 text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/20 text-sm transition-all"
              required
            />
            <p className="text-xs text-slate-600">
              {config.provider === 'ollama' && 'e.g. llama3, mistral, codellama, phi3'}
              {config.provider === 'openai' && 'e.g. gpt-4o, gpt-4o-mini, gpt-4-turbo'}
              {config.provider === 'anthropic' && 'e.g. claude-opus-4-7, claude-sonnet-4-6'}
            </p>
          </div>

          {/* API Key */}
          {config.provider !== 'ollama' && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">API Key</label>
              <input
                type="password"
                value={config.api_key}
                onChange={e => setConfig(prev => ({ ...prev, api_key: e.target.value }))}
                placeholder="sk-..."
                className="w-full px-4 py-2.5 rounded-xl bg-navy-800 border border-white/8 text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/20 text-sm font-mono transition-all"
                required
              />
              <p className="text-xs text-slate-600">Stored in memory only — never written to disk.</p>
            </div>
          )}

          {/* Base URL for Ollama */}
          {config.provider === 'ollama' && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Base URL</label>
              <input
                type="text"
                value={config.base_url}
                onChange={e => setConfig(prev => ({ ...prev, base_url: e.target.value }))}
                placeholder="http://localhost:11434/v1"
                className="w-full px-4 py-2.5 rounded-xl bg-navy-800 border border-white/8 text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/20 text-sm font-mono transition-all"
              />
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex gap-2.5 p-3.5 bg-red-950/50 border border-red-800/50 rounded-xl text-sm">
              <AlertCircle size={15} className="text-red-400 shrink-0 mt-0.5" />
              <span className="text-red-300 text-sm">{error}</span>
            </div>
          )}

          {/* Save */}
          <button
            type="submit"
            disabled={saving}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl font-medium transition-all text-sm flex items-center justify-center gap-2"
          >
            {saving ? (
              <><Loader2 size={15} className="animate-spin" /> Saving...</>
            ) : saved ? (
              <><CheckCircle size={15} className="text-emerald-400" /> Saved</>
            ) : (
              <><Save size={15} /> Save Settings</>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
