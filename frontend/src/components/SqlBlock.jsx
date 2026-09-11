/* --------------------------------------------------------------------------
   SqlBlock.jsx
   The generated SQL, collapsed by default.

   Hidden because most people do not want to read it. One click away because
   it is the receipt: it proves the numbers came from the database and were
   not invented. Any serious data tool shows its working.
   -------------------------------------------------------------------------- */

import { useState } from 'react'
import { Check, ChevronRight, Copy, Wrench } from 'lucide-react'

export default function SqlBlock({ sql, repaired }) {
  // useState gives the component its own memory. A plain variable would reset
  // every time React redraws this component.
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="mt-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[12px] font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
          aria-expanded={open}
        >
          <ChevronRight
            size={13}
            className={`transition-transform duration-150 ${open ? 'rotate-90' : ''}`}
          />
          {open ? 'Hide SQL' : 'Show SQL'}
        </button>

        {repaired && (
          <span
            className="inline-flex items-center gap-1 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700"
            title="The first query failed. The agent read the database error and corrected itself."
          >
            <Wrench size={11} />
            Self-corrected
          </span>
        )}
      </div>

      {open && (
        <div className="enter relative mt-2 overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
          <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
            <span className="font-mono text-[11px] tracking-wide text-slate-400">
              generated query
            </span>
            <button
              onClick={copy}
              className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre className="overflow-x-auto px-3 py-3 font-mono text-[12.5px] leading-[1.65] text-slate-200">
            <code>{sql}</code>
          </pre>
        </div>
      )}
    </div>
  )
}
