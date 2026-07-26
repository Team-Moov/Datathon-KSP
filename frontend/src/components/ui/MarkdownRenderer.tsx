/**
 * MarkdownRenderer — custom zero-dependency markdown parser.
 *
 * Supports: headers (h1-h6), bold, italic, bold+italic, inline code, code blocks,
 * ordered and unordered lists, nested lists, blockquotes, tables, horizontal rules,
 * and paragraph text. All rendering is pure React — no dangerouslySetInnerHTML.
 *
 * Architecture: The parser works in two passes:
 *   1. Block-level: splits the document into sections (headers, lists, code blocks, tables…)
 *   2. Inline-level: within each text line, renders bold/italic/code spans.
 */
import * as React from "react"
import { cn } from "@/lib/utils"

interface MarkdownRendererProps {
  content: string
  className?: string
}

// ── Inline parser ─────────────────────────────────────────────────────────────

/** Recursively parse inline markdown: ***bold+italic***, **bold**, *italic*, `code` */
function parseInline(text: string, key?: string | number): React.ReactNode {
  if (!text) return null

  // Pattern order matters: more specific patterns must come first.
  const INLINE_RE =
    /(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[([^\]]+)\]\(([^)]+)\))/gs

  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  INLINE_RE.lastIndex = 0
  while ((match = INLINE_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }

    if (match[2]) {
      // ***bold+italic***
      parts.push(
        <strong key={match.index} className="font-bold italic">
          {match[2]}
        </strong>,
      )
    } else if (match[3]) {
      // **bold**
      parts.push(
        <strong key={match.index} className="font-semibold text-zinc-900 dark:text-zinc-55">
          {match[3]}
        </strong>,
      )
    } else if (match[4]) {
      // *italic*
      parts.push(
        <em key={match.index} className="italic text-zinc-700 dark:text-zinc-300">
          {match[4]}
        </em>,
      )
    } else if (match[5]) {
      // `inline code`
      parts.push(
        <code
          key={match.index}
          className="rounded bg-zinc-150 px-1 py-0.5 font-mono text-[0.8em] text-accent-700 dark:bg-zinc-800 dark:text-accent-300"
        >
          {match[5]}
        </code>,
      )
    } else if (match[6] && match[7]) {
      // [link text](url)
      parts.push(
        <a
          key={match.index}
          href={match[7]}
          target="_blank"
          rel="noreferrer"
          className="text-accent-600 hover:underline dark:text-accent-400"
        >
          {match[6]}
        </a>,
      )
    }

    lastIndex = INLINE_RE.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }

  return parts.length === 1 ? parts[0] : <React.Fragment key={key}>{parts}</React.Fragment>
}

// ── Block parser ──────────────────────────────────────────────────────────────

/** Strip Windows/Mac carriage returns so splits work consistently. */
function normalise(content: string): string {
  return content.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
}

interface Block {
  type:
    | "heading"
    | "hr"
    | "codeblock"
    | "blockquote"
    | "ul"
    | "ol"
    | "table"
    | "paragraph"
  raw: string
  level?: number        // heading level 1-6
  lang?: string         // fenced code language
  items?: string[]      // list items (already stripped of bullet/number)
  rows?: string[][]     // table rows
  headerRow?: string[]  // table header
}

function tokenize(lines: string[]): Block[] {
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    // ── Skip blank lines
    if (!trimmed) { i++; continue }

    // ── Fenced code block ```lang
    if (trimmed.startsWith("```") || trimmed.startsWith("~~~")) {
      const fence = trimmed[0].repeat(3)
      const lang = trimmed.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith(fence)) {
        codeLines.push(lines[i])
        i++
      }
      i++ // consume closing fence
      blocks.push({ type: "codeblock", raw: codeLines.join("\n"), lang })
      continue
    }

    // ── Horizontal rule
    if (/^[-*_]{3,}$/.test(trimmed)) {
      blocks.push({ type: "hr", raw: trimmed })
      i++
      continue
    }

    // ── ATX Heading  # … ######
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      blocks.push({ type: "heading", level: headingMatch[1].length, raw: headingMatch[2] })
      i++
      continue
    }

    // ── Blockquote
    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = []
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""))
        i++
      }
      blocks.push({ type: "blockquote", raw: quoteLines.join("\n") })
      continue
    }

    // ── Unordered list (* - •)
    if (/^[\*\-•]\s/.test(trimmed)) {
      const items: string[] = []
      while (i < lines.length) {
        const t = lines[i].trim()
        if (/^[\*\-•]\s/.test(t)) {
          items.push(t.replace(/^[\*\-•]\s+/, ""))
          i++
        } else if (t === "") {
          // Allow a single blank line inside list, but stop at two
          i++
          if (i < lines.length && /^[\*\-•]\s/.test(lines[i].trim())) continue
          break
        } else {
          break
        }
      }
      blocks.push({ type: "ul", raw: items.join("\n"), items })
      continue
    }

    // ── Ordered list (1. 2.)
    if (/^\d+\.\s/.test(trimmed)) {
      const items: string[] = []
      while (i < lines.length) {
        const t = lines[i].trim()
        if (/^\d+\.\s/.test(t)) {
          items.push(t.replace(/^\d+\.\s+/, ""))
          i++
        } else if (t === "") {
          i++
          if (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) continue
          break
        } else {
          break
        }
      }
      blocks.push({ type: "ol", raw: items.join("\n"), items })
      continue
    }

    // ── Table (has | in it and at least 2 rows)
    if (trimmed.includes("|")) {
      const tableLines: string[] = []
      while (i < lines.length && lines[i].trim().includes("|")) {
        tableLines.push(lines[i].trim())
        i++
      }
      if (tableLines.length >= 2) {
        const parseRow = (row: string) =>
          row
            .split("|")
            .map((c) => c.trim())
            .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
        const headerRow = parseRow(tableLines[0])
        const isDivider = tableLines[1].replace(/[| :\-]/g, "").length === 0
        const bodyRows = tableLines.slice(isDivider ? 2 : 1).map(parseRow)
        blocks.push({ type: "table", raw: tableLines.join("\n"), headerRow, rows: bodyRows })
        continue
      }
      // Not a table — fall through to paragraph
    }

    // ── Paragraph — collect until blank line or block-level element
    const paraLines: string[] = []
    while (i < lines.length) {
      const t = lines[i].trim()
      if (
        !t ||
        t.startsWith("```") ||
        t.startsWith("~~~") ||
        /^#{1,6}\s/.test(t) ||
        t.startsWith(">") ||
        /^[\*\-•]\s/.test(t) ||
        /^\d+\.\s/.test(t) ||
        /^[-*_]{3,}$/.test(t)
      ) break
      paraLines.push(lines[i])
      i++
    }
    if (paraLines.length > 0) {
      blocks.push({ type: "paragraph", raw: paraLines.join("\n") })
    }
  }

  return blocks
}

// ── Render functions for each block type ──────────────────────────────────────

function renderBlock(block: Block, index: number): React.ReactNode {
  switch (block.type) {
    case "heading": {
      const content = parseInline(block.raw, index)
      const cls = "font-bold text-zinc-900 dark:text-zinc-50 leading-tight"
      if (block.level === 1) return <h1 key={index} className={cn(cls, "text-xl pt-2 pb-1")}>{content}</h1>
      if (block.level === 2) return <h2 key={index} className={cn(cls, "text-lg pt-2 pb-0.5")}>{content}</h2>
      if (block.level === 3) return <h3 key={index} className={cn(cls, "text-base pt-1.5")}>{content}</h3>
      if (block.level === 4) return <h4 key={index} className={cn(cls, "text-sm")}>{content}</h4>
      return <h5 key={index} className={cn(cls, "text-sm font-semibold")}>{content}</h5>
    }

    case "hr":
      return <hr key={index} className="my-3 border-zinc-200 dark:border-zinc-800" />

    case "codeblock":
      return (
        <div key={index} className="my-2.5 overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-950">
          {block.lang && (
            <div className="px-3 py-1.5 text-[9px] font-mono text-zinc-500 border-b border-zinc-800 uppercase tracking-widest">
              {block.lang}
            </div>
          )}
          <pre className="px-4 py-3 text-xs text-zinc-100 font-mono leading-relaxed whitespace-pre-wrap break-words">
            {block.raw}
          </pre>
        </div>
      )

    case "blockquote":
      return (
        <blockquote
          key={index}
          className="border-l-2 border-accent-400 pl-3 py-0.5 my-2 text-zinc-600 dark:text-zinc-400 italic"
        >
          <MarkdownRenderer content={block.raw} className="space-y-1" />
        </blockquote>
      )

    case "ul":
      return (
        <ul key={index} className="list-disc pl-5 space-y-1 my-1.5">
          {(block.items ?? []).map((item, idx) => (
            <li key={idx} className="text-zinc-700 dark:text-zinc-300 leading-relaxed">
              {parseInline(item, idx)}
            </li>
          ))}
        </ul>
      )

    case "ol":
      return (
        <ol key={index} className="list-decimal pl-5 space-y-1 my-1.5">
          {(block.items ?? []).map((item, idx) => (
            <li key={idx} className="text-zinc-700 dark:text-zinc-300 leading-relaxed">
              {parseInline(item, idx)}
            </li>
          ))}
        </ol>
      )

    case "table":
      return (
        <div key={index} className="my-3 overflow-x-auto rounded-md border border-zinc-200 dark:border-zinc-800">
          <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800 text-xs">
            <thead className="bg-zinc-50 dark:bg-zinc-900/60">
              <tr>
                {(block.headerRow ?? []).map((cell, idx) => (
                  <th
                    key={idx}
                    className="px-3 py-2 text-left font-semibold text-zinc-700 dark:text-zinc-200 uppercase tracking-wider"
                  >
                    {parseInline(cell, idx)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {(block.rows ?? []).map((row, rowIdx) => (
                <tr key={rowIdx} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-900/20 transition-colors">
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx} className="px-3 py-2 text-zinc-600 dark:text-zinc-300">
                      {parseInline(cell, cellIdx)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )

    case "paragraph":
    default: {
      const paraLines = block.raw.split("\n")
      return (
        <p key={index} className="leading-relaxed text-zinc-700 dark:text-zinc-300">
          {paraLines.map((line, lineIdx) => (
            <React.Fragment key={lineIdx}>
              {lineIdx > 0 && <br />}
              {parseInline(line, lineIdx)}
            </React.Fragment>
          ))}
        </p>
      )
    }
  }
}

// ── Public component ──────────────────────────────────────────────────────────

function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  if (!content) return null
  const lines = normalise(content).split("\n")
  const blocks = tokenize(lines)
  return (
    <div className={cn("space-y-2 text-sm leading-relaxed", className)}>
      {blocks.map((block, i) => renderBlock(block, i))}
    </div>
  )
}

export { MarkdownRenderer }
