/* --------------------------------------------------------------------------
   App.jsx
   The whole screen: sidebar, top bar, conversation and composer.

   State lives here and is handed down to the smaller components as props, so
   there is exactly one version of the truth about what is on screen.

   Conversations are kept in the browser's own storage. The app holds a list
   of them plus the id of the one being viewed, and writes the list back to
   storage whenever it changes.
   -------------------------------------------------------------------------- */

import { useEffect, useRef, useState } from 'react'
import { ArrowUp, ArrowUpRight, Menu, Search } from 'lucide-react'
import { askQuestion, fetchExamples, fetchHealth } from './api'
import ChatMessage from './components/ChatMessage'
import Sidebar from './components/Sidebar'
import {
  emptyConversation,
  loadConversations,
  saveConversations,
} from './storage'

// How many example questions to show on the empty state. Six fills the space
// without turning the first screen into a menu to read.
const EXAMPLES_SHOWN = 6

// How many earlier turns to send with each question, so the agent can resolve
// follow-ups like "same for Koramangala".
const HISTORY_TURNS = 4

export default function App() {
  // The lazy form of useState, a function rather than a value, runs only on
  // the first render. Without it, localStorage would be read on every redraw.
  const [conversations, setConversations] = useState(() => {
    const saved = loadConversations()
    return saved.length ? saved : [emptyConversation()]
  })
  const [activeId, setActiveId] = useState(() => null)

  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [examples, setExamples] = useState([])
  const [health, setHealth] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // useRef holds on to a DOM element so we can scroll it or focus it later.
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Pick the first conversation once, after the saved ones have been read.
  useEffect(() => {
    if (!activeId && conversations.length) setActiveId(conversations[0].id)
  }, [activeId, conversations])

  useEffect(() => {
    fetchExamples().then(setExamples)
    fetchHealth().then(setHealth)
  }, [])

  // Write to storage whenever the conversations change. Running it in an
  // effect rather than inside every handler means there is one save path, and
  // no way to update state and forget to persist it.
  useEffect(() => {
    saveConversations(conversations)
  }, [conversations])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversations, activeId, loading])

  const active =
    conversations.find((conversation) => conversation.id === activeId) ??
    conversations[0] ??
    emptyConversation()
  const messages = active.messages
  const empty = messages.length === 0

  /** Adds messages to the open conversation and stamps it as just used. */
  function appendToActive(...newMessages) {
    setConversations((previous) =>
      previous.map((conversation) =>
        conversation.id === active.id
          ? {
              ...conversation,
              messages: [...conversation.messages, ...newMessages],
              updatedAt: Date.now(),
            }
          : conversation,
      ),
    )
  }

  async function send(text) {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    appendToActive({ role: 'user', text: trimmed })
    setQuestion('')
    setLoading(true)

    try {
      // Only answered turns carry usable SQL, so failed ones are left out.
      const history = messages
        .filter((message) => message.role === 'answer')
        .slice(-HISTORY_TURNS)
        .map((message) => ({ question: message.question, sql: message.sql }))

      const answer = await askQuestion(trimmed, history)
      appendToActive({ role: 'answer', ...answer })
    } catch (error) {
      appendToActive({ role: 'error', text: error.message })
    } finally {
      // finally runs whether the call succeeded or failed, so the loading
      // indicator can never get stuck on screen.
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function startNewConversation() {
    const fresh = emptyConversation()
    setConversations((previous) => [fresh, ...previous])
    setActiveId(fresh.id)
  }

  function deleteConversation(id) {
    setConversations((previous) => {
      const remaining = previous.filter((conversation) => conversation.id !== id)
      // Never leave the app with nothing open.
      const next = remaining.length ? remaining : [emptyConversation()]
      if (id === activeId) setActiveId(next[0].id)
      return next
    })
  }

  const backendUp = health?.status === 'ok'

  // Only offer a new conversation when the open one has been used. Otherwise
  // the button just makes empty conversations.
  const canStartNew = !empty

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={conversations.filter(
          (conversation) => conversation.messages.length > 0,
        )}
        activeId={active.id}
        onSelect={setActiveId}
        onDelete={deleteConversation}
        onNewChat={startNewConversation}
        canStartNew={canStartNew}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* ---------------------------------------------------------------- */}
        {/* Top bar                                                           */}
        {/* ---------------------------------------------------------------- */}
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="-ml-1 rounded-md p-1.5 text-slate-500 transition-colors hover:bg-slate-100 md:hidden"
            aria-label="Open menu"
          >
            <Menu size={18} />
          </button>

          <h1 className="flex-1 text-[14px] font-semibold text-slate-900">
            Ask the data
          </h1>

          {/* Connection status. A dead backend should be visible before you
              type a question and wait for it to fail. */}
          <div
            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11.5px] font-medium ${
              health === null
                ? 'border-slate-200 bg-slate-50 text-slate-400'
                : backendUp
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-red-200 bg-red-50 text-red-700'
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                health === null
                  ? 'bg-slate-300'
                  : backendUp
                    ? 'bg-emerald-500'
                    : 'bg-red-500'
              }`}
            />
            {health === null ? 'Connecting' : backendUp ? 'Connected' : 'Offline'}
          </div>
        </header>

        {/* ---------------------------------------------------------------- */}
        {/* Conversation                                                      */}
        {/* ---------------------------------------------------------------- */}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6">
            {empty ? (
              <div className="pt-[7vh]">
                <div className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                  <Search size={20} />
                </div>

                <h2 className="text-[22px] font-semibold tracking-tight text-slate-900">
                  Ask a question about Bangalore restaurants
                </h2>
                <p className="mt-1.5 max-w-lg text-[14px] leading-relaxed text-slate-500">
                  Type it in plain English. An agent writes the SQL, runs it
                  against a MySQL database of 12,464 restaurants, and explains
                  the result.
                </p>

                {/* The examples come from the backend, so the list lives in
                    one place and the UI never drifts out of step with it. */}
                <div className="mt-7">
                  <p className="mb-2 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
                    Try asking
                  </p>

                  <div className="grid gap-2 sm:grid-cols-2">
                    {examples.slice(0, EXAMPLES_SHOWN).map((example) => (
                      <button
                        key={example}
                        onClick={() => send(example)}
                        disabled={loading}
                        className="group flex items-start gap-2 rounded-lg border border-slate-200 bg-white
                                   px-3 py-2.5 text-left text-[13px] leading-snug text-slate-600
                                   transition-colors hover:border-brand-200 hover:bg-brand-50/40 hover:text-slate-900
                                   disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <ArrowUpRight
                          size={14}
                          className="mt-px shrink-0 text-slate-300 transition-colors group-hover:text-brand-500"
                        />
                        {example}
                      </button>
                    ))}
                  </div>
                </div>

                {!backendUp && health !== null && (
                  <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-3">
                    <p className="text-[13px] font-semibold text-amber-900">
                      Backend not running
                    </p>
                    <p className="mt-1 text-[13px] leading-relaxed text-amber-800">
                      Start it from the backend folder with{' '}
                      <code className="rounded bg-amber-100 px-1 py-0.5 font-mono text-[12px]">
                        uvicorn app.main:app --reload
                      </code>
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-5">
                {messages.map((message, index) => (
                  <ChatMessage key={index} message={message} />
                ))}

                {loading && (
                  <div className="flex items-center gap-3 pl-10">
                    <span className="flex gap-1">
                      <span className="dot h-1.5 w-1.5 rounded-full bg-brand-500" />
                      <span className="dot h-1.5 w-1.5 rounded-full bg-brand-500" />
                      <span className="dot h-1.5 w-1.5 rounded-full bg-brand-500" />
                    </span>
                    <span className="text-[12.5px] text-slate-400">
                      Writing and running the query
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* An empty marker at the end, used as the scroll target. */}
            <div ref={bottomRef} />
          </div>
        </main>

        {/* ---------------------------------------------------------------- */}
        {/* Composer                                                          */}
        {/* ---------------------------------------------------------------- */}
        <div className="shrink-0 border-t border-slate-200 bg-white px-4 py-3">
          <div className="mx-auto max-w-3xl">
            <form
              onSubmit={(event) => {
                event.preventDefault() // stop the browser reloading the page
                send(question)
              }}
              className="flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-1.5
                         transition-colors focus-within:border-brand-300 focus-within:ring-2 focus-within:ring-brand-100"
            >
              <textarea
                ref={inputRef}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  // Enter sends. Shift and Enter together make a new line.
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    send(question)
                  }
                }}
                rows={1}
                placeholder="Ask about ratings, prices, cuisines or neighbourhoods…"
                disabled={loading}
                className="max-h-32 min-h-[34px] flex-1 resize-none bg-transparent px-2 py-1.5
                           text-[14px] text-slate-800 placeholder:text-slate-400
                           focus:outline-none disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white
                           transition-colors hover:bg-brand-700
                           disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
                aria-label="Send question"
              >
                <ArrowUp size={16} />
              </button>
            </form>

            <p className="mt-2 text-center text-[11.5px] text-slate-400">
              Read-only access. The agent can run SELECT statements and nothing else.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
