import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'
import { AlertTriangle, Code2 } from 'lucide-react'

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#1e1b4b',
    primaryTextColor: '#e2e8f0',
    primaryBorderColor: '#6366f1',
    lineColor: '#6366f1',
    secondaryColor: '#0f172a',
    tertiaryColor: '#0d1225',
    background: '#0d1225',
    mainBkg: '#1a1a3e',
    nodeBorder: '#6366f1',
    clusterBkg: '#111827',
    titleColor: '#a5b4fc',
    edgeLabelBackground: '#111827',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  flowchart: { htmlLabels: true, curve: 'basis', padding: 20 },
})

let renderCounter = 0

interface DiagramViewerProps {
  code: string
}

export function DiagramViewer({ code }: DiagramViewerProps) {
  const [error, setError] = useState<string | null>(null)
  const [svg, setSvg] = useState<string>('')
  const [showRaw, setShowRaw] = useState(false)
  const lastRenderedCode = useRef<string>('')

  // On mount, remove any mermaid error elements left over from a previous render
  useEffect(() => {
    document.querySelectorAll('[id^="mermaid-"]').forEach(el => {
      if (el.parentElement === document.body) el.remove()
    })
  }, [])

  useEffect(() => {
    const trimmed = code.trim()
    if (!trimmed || trimmed === lastRenderedCode.current) return

    const id = `mermaid-${++renderCounter}`
    let active = true

    // Remove any orphaned mermaid error elements Mermaid v11 injects into <body>
    const purgeMermaidBodyElements = () => {
      document.querySelectorAll('[id^="mermaid-"]').forEach(el => {
        if (el.parentElement === document.body) el.remove()
      })
    }
    purgeMermaidBodyElements()

    mermaid
      .render(id, trimmed)
      .then(({ svg: rendered }) => {
        // Mermaid may leave the container in the body even on success
        document.getElementById(id)?.remove()
        purgeMermaidBodyElements()
        if (active) {
          lastRenderedCode.current = trimmed
          setSvg(rendered)
          setError(null)
        }
      })
      .catch(err => {
        // Clean up the error SVG Mermaid injected into the body
        document.getElementById(id)?.remove()
        purgeMermaidBodyElements()
        if (active) {
          lastRenderedCode.current = trimmed
          setError(String(err))
          setSvg('')
        }
      })

    return () => { active = false }
  }, [code])

  if (error) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="flex items-start gap-3 p-4 bg-amber-950/40 border border-amber-700/40 rounded-xl">
          <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-amber-300 text-sm font-medium">Diagram render error</p>
            <p className="text-amber-500/80 text-xs mt-1 font-mono break-all">{error}</p>
          </div>
        </div>
        <div className="bg-navy-700/50 border border-white/6 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/6">
            <div className="flex items-center gap-2 text-slate-400 text-xs">
              <Code2 size={13} />
              Raw Mermaid code
            </div>
          </div>
          <pre className="text-xs text-slate-300 overflow-x-auto font-mono whitespace-pre-wrap p-4 leading-relaxed">{code}</pre>
        </div>
      </div>
    )
  }

  if (!svg) {
    return (
      <div className="flex items-center justify-center h-72">
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <div className="w-8 h-8 border-2 border-indigo-600/40 border-t-indigo-500 rounded-full animate-spin" />
          <span className="text-sm">Rendering diagram...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3 animate-fade-in">
      <div className="flex items-center justify-end">
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-500 hover:text-slate-300 border border-white/8 hover:border-white/15 rounded-lg transition-all"
        >
          <Code2 size={12} />
          {showRaw ? 'Hide code' : 'View code'}
        </button>
      </div>

      {showRaw && (
        <div className="bg-navy-700/50 border border-white/6 rounded-xl overflow-hidden animate-fade-in">
          <pre className="text-xs text-slate-300 overflow-x-auto font-mono whitespace-pre-wrap p-4 leading-relaxed">{code}</pre>
        </div>
      )}

      <div
        className="w-full overflow-x-auto flex justify-center p-4 rounded-xl bg-navy-700/20"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  )
}
