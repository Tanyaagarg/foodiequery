/* --------------------------------------------------------------------------
   ChatMessage.jsx
   One turn in the conversation.

   Three kinds:
     user      the question that was typed, as a bubble on the right
     answer    an avatar, the written summary, the results, the SQL
     error     the same shape, but stating what went wrong

   Answers use the avatar-plus-content layout that chat products settled on,
   because it makes it obvious at a glance who said what, and it keeps the
   table and the SQL panel aligned to the same left edge.
   -------------------------------------------------------------------------- */

import { AlertCircle, Clock, Database, Sparkles } from 'lucide-react'
import ResultsTable from './ResultsTable'
import SqlBlock from './SqlBlock'

/** The small round badge next to every AI turn. */
function AgentAvatar({ tone = 'brand' }) {
  const styles =
    tone === 'error'
      ? 'bg-red-50 text-red-600 ring-red-100'
      : 'bg-brand-50 text-brand-600 ring-brand-100'

  return (
    <div
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-1 ${styles}`}
    >
      {tone === 'error' ? <AlertCircle size={15} /> : <Sparkles size={15} />}
    </div>
  )
}

export default function ChatMessage({ message }) {
  // --- the question the person typed ---------------------------------------
  if (message.role === 'user') {
    return (
      <div className="enter flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-slate-900 px-3.5 py-2 text-[14px] leading-snug text-white">
          {message.text}
        </div>
      </div>
    )
  }

  // --- something went wrong ------------------------------------------------
  if (message.role === 'error') {
    return (
      <div className="enter flex gap-3">
        <AgentAvatar tone="error" />
        <div className="min-w-0 flex-1 rounded-lg border border-red-100 bg-red-50/60 px-3.5 py-3">
          <p className="text-[13px] font-semibold text-red-800">
            Could not answer that
          </p>
          <p className="mt-1 text-[13.5px] leading-relaxed text-red-700/90">
            {message.text}
          </p>
        </div>
      </div>
    )
  }

  // --- a real answer -------------------------------------------------------
  return (
    <div className="enter flex gap-3">
      <AgentAvatar />

      <div className="min-w-0 flex-1">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(27,25,23,0.04)]">
          <p className="text-[14.5px] leading-relaxed text-slate-800">
            {message.insight}
          </p>

          <ResultsTable
            columns={message.columns}
            rows={message.rows}
            truncated={message.truncated}
          />

          <SqlBlock sql={message.sql} repaired={message.repaired} />
        </div>

        {/* Metadata sits outside the card, the way timestamps usually do. */}
        <div className="mt-1.5 flex items-center gap-3 px-1 text-[11.5px] text-slate-400">
          <span className="inline-flex items-center gap-1">
            <Database size={11} />
            MySQL
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock size={11} />
            {(message.elapsed_ms / 1000).toFixed(2)}s
          </span>
        </div>
      </div>
    </div>
  )
}
