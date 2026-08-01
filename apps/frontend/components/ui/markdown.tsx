import "katex/dist/katex.min.css"

import ReactMarkdown from "react-markdown"
import rehypeKatex from "rehype-katex"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"

function normalizeMath(content: string): string {
  return content
    .replace(/\\\[([\s\S]*?)\\\]/g, (_m, inner) => `$$\n${inner.trim()}\n$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_m, inner) => `$${inner.trim()}$`)
    .replace(
      /^\s*\[[ \t]*([^\n]+?)[ \t]*\]\s*$/gm,
      (match, inner) => {
        if (!/[\\^_={}]/.test(inner)) {
          return match
        }
        return `$$\n${inner}\n$$`
      },
    )
}

const Markdown = ({ content }: { content: string }) => {
  return (
    <div className="text-xs/relaxed [&_*]:break-words">
      <ReactMarkdown
        remarkPlugins={[[remarkMath, { singleDollarTextMath: true }], remarkGfm]}
        rehypePlugins={[[rehypeKatex, { strict: false, throwOnError: false }]]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-2 mt-3 text-base font-medium first:mt-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-3 text-sm font-medium first:mt-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-3 text-xs font-semibold first:mt-0">{children}</h3>
          ),
          p: ({ children }) => (
            <p className="my-1.5 first:mt-0 last:mb-0">{children}</p>
          ),
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          del: ({ children }) => <del className="line-through">{children}</del>,
          ul: ({ children }) => (
            <ul className="my-1.5 flex list-disc flex-col gap-0.5 ps-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-1.5 flex list-decimal flex-col gap-0.5 ps-5">{children}</ol>
          ),
          li: ({ children }) => <li className="ps-1">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-border ps-3 text-muted-foreground">
              {children}
            </blockquote>
          ),
          code: ({ className, children }) => {
            const isBlock = /language-/.test(className ?? "")
            if (isBlock) {
              return (
                <code className="block overflow-x-auto bg-muted px-2.5 py-2 text-xs">
                  {children}
                </code>
              )
            }
            return (
              <code className="rounded-none border border-border bg-muted px-1 py-0.5 text-[11px]">
                {children}
              </code>
            )
          },
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-none border border-border bg-muted p-0 text-xs">
              {children}
            </pre>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-primary underline underline-offset-4 hover:text-primary/80"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto rounded-none border border-border">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-border bg-muted px-2 py-1 text-start font-medium">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-border/50 px-2 py-1">{children}</td>
          ),
        }}
      >
        {normalizeMath(content)}
      </ReactMarkdown>
    </div>
  )
}

export { Markdown }
