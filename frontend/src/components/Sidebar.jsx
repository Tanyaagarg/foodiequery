/* --------------------------------------------------------------------------
   Sidebar.jsx
   App navigation: the brand block, saved conversations, and what the data
   actually contains.

   The saved list is read from the browser's own storage, so it comes back
   after a refresh or a reboot. It never leaves this device.
   -------------------------------------------------------------------------- */

import { Database, MessageSquarePlus, Trash2, Utensils, X } from 'lucide-react'
import { relativeTime, titleFor } from '../storage'

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onDelete,
  onNewChat,
  canStartNew,
  open,
  onClose,
}) {
  return (
    <>
      {/* On a phone the sidebar slides over the chat, so a dimmed backdrop sits
          behind it and closes it when tapped. */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-slate-900/30 md:hidden"
          onClick={onClose}
        />
      )}

      {/* max-md: applies only BELOW the medium breakpoint. Sliding the panel
          off screen is phone behaviour. On a wide screen there must be no
          transform at all, or it fights with md:static and the sidebar ends
          up shifted off the left edge. */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[16.5rem] shrink-0 flex-col border-r
                    border-slate-200 bg-white transition-transform duration-200
                    md:static md:z-auto
                    ${open ? 'translate-x-0' : 'max-md:-translate-x-full'}`}
      >
        {/* --- brand block --- */}
        <div className="flex h-14 items-center gap-2.5 border-b border-slate-200 px-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-500 text-white">
            <Utensils size={15} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[14px] leading-tight font-semibold text-slate-900">
              FoodieQuery
            </p>
            <p className="text-[11px] leading-tight text-slate-400">
              Bangalore restaurants
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 md:hidden"
            aria-label="Close menu"
          >
            <X size={16} />
          </button>
        </div>

        {/* --- new conversation --- */}
        <div className="px-3 pt-3">
          <button
            onClick={() => {
              onNewChat()
              onClose()
            }}
            disabled={!canStartNew}
            className="inline-flex w-full items-center gap-2 rounded-md border border-slate-200 px-2.5 py-2
                       text-[13px] font-medium text-slate-700 transition-colors
                       hover:border-slate-300 hover:bg-slate-50
                       disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-transparent"
          >
            <MessageSquarePlus size={14} />
            New conversation
          </button>
        </div>

        {/* --- saved conversations --- */}
        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
          <p className="px-1 pb-2 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
            Saved
          </p>

          {conversations.length === 0 ? (
            <p className="px-1 text-[12.5px] leading-relaxed text-slate-400">
              Your conversations are saved here automatically, on this device.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {conversations.map((conversation) => {
                const active = conversation.id === activeId
                return (
                  <li key={conversation.id} className="group relative">
                    <button
                      onClick={() => {
                        onSelect(conversation.id)
                        onClose()
                      }}
                      className={`w-full rounded-md py-2 pr-8 pl-2.5 text-left transition-colors ${
                        active
                          ? 'bg-brand-50 text-slate-900'
                          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                      }`}
                    >
                      {/* truncate needs a width to work against, which the
                          block display and the padding above provide. */}
                      <span className="block truncate text-[13px] leading-snug">
                        {titleFor(conversation.messages)}
                      </span>
                      <span className="mt-0.5 block text-[11px] text-slate-400">
                        {relativeTime(conversation.updatedAt)}
                      </span>
                    </button>

                    {/* Hidden until hover, so the list stays calm. It is still
                        reachable by keyboard because focus-visible shows it. */}
                    <button
                      onClick={() => onDelete(conversation.id)}
                      className="absolute top-1/2 right-1 -translate-y-1/2 rounded p-1.5 text-slate-400
                                 opacity-0 transition-opacity group-hover:opacity-100
                                 hover:bg-slate-200 hover:text-red-600 focus-visible:opacity-100"
                      aria-label="Delete this conversation"
                      title="Delete"
                    >
                      <Trash2 size={13} />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* --- what is in the database --- */}
        <div className="border-t border-slate-200 px-4 py-3">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
            <Database size={12} />
            Dataset
          </p>
          <dl className="mt-2 space-y-1 text-[12.5px]">
            {[
              ['Restaurants', '12,464'],
              ['Neighbourhoods', '93'],
              ['Cuisines', '107'],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between">
                <dt className="text-slate-500">{label}</dt>
                <dd className="tabular font-medium text-slate-700">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </aside>
    </>
  )
}
