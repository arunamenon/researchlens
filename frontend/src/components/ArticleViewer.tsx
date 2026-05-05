import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ArticleViewerProps {
  markdown: string
}

function cleanArticle(markdown: string): string {
  return markdown.replace(/```mermaid[\s\S]*?```/gi, '').trim()
}

export function ArticleViewer({ markdown }: ArticleViewerProps) {
  const clean = cleanArticle(markdown)
  return (
    <div className="prose prose-invert max-w-none animate-fade-in">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        children={clean}
        components={{
          h1: ({ children }) => (
            <h1 className="text-2xl font-bold text-white mt-8 mb-4 leading-tight">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-xl font-semibold text-slate-100 mt-8 mb-3 pb-2.5 border-b border-white/8">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-base font-semibold text-slate-200 mt-5 mb-2">{children}</h3>
          ),
          p: ({ children }) => (
            <p className="text-slate-300 leading-7 mb-4 text-[0.9375rem]">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="space-y-1.5 mb-4 ml-4 text-slate-300">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside text-slate-300 space-y-1.5 mb-4 ml-4">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="text-slate-300 leading-relaxed flex gap-2 items-start">
              <span className="text-indigo-400 mt-1.5 shrink-0">·</span>
              <span>{children}</span>
            </li>
          ),
          code: ({ children, className }) => {
            const isBlock = className?.includes('language-')
            return isBlock ? (
              <code className="block bg-navy-950/80 border border-white/6 rounded-xl p-4 text-sm text-indigo-200 overflow-x-auto my-4 font-mono leading-relaxed">{children}</code>
            ) : (
              <code className="bg-navy-700 text-indigo-300 px-1.5 py-0.5 rounded-md text-[0.8125rem] font-mono">{children}</code>
            )
          },
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-indigo-500/60 pl-5 py-1 italic text-slate-400 my-5 bg-navy-700/30 rounded-r-lg">{children}</blockquote>
          ),
          strong: ({ children }) => (
            <strong className="text-white font-semibold">{children}</strong>
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300 underline decoration-indigo-600 underline-offset-2 transition-colors">{children}</a>
          ),
          hr: () => (
            <hr className="border-white/8 my-8" />
          ),
        }}
      />
    </div>
  )
}
