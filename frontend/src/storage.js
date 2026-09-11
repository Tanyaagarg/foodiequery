/* --------------------------------------------------------------------------
   storage.js
   Saves conversations in the browser so they survive a refresh.

   localStorage is a small key-value store the browser keeps per website. It
   holds strings only, so everything is converted to JSON on the way in and
   parsed on the way out. It lives on this device in this browser: it does not
   follow you to your phone, and clearing site data wipes it.

   Every read and write is wrapped in try/catch. localStorage can throw for
   reasons that have nothing to do with your code, such as private browsing
   modes or a full quota, and none of those should take the whole app down.
   -------------------------------------------------------------------------- */

// The v1 on the end is deliberate. If the saved shape ever changes, bumping
// this to v2 makes old data invisible instead of crashing the new code.
const STORAGE_KEY = 'foodiequery.conversations.v1'

// Caps, because localStorage is roughly 5 MB per site and a single answer can
// carry 200 rows. Without these, a few long sessions would fill it and every
// later save would silently fail.
const MAX_CONVERSATIONS = 25
const MAX_ROWS_STORED = 50

/** Builds a short title from the first thing the person asked. */
export function titleFor(messages) {
  const firstQuestion = messages.find((message) => message.role === 'user')
  if (!firstQuestion) return 'New conversation'
  const text = firstQuestion.text.trim()
  return text.length > 48 ? `${text.slice(0, 48).trimEnd()}…` : text
}

/** A unique id, used to tell conversations apart in the list. */
export function newId() {
  return `c_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export function emptyConversation() {
  return { id: newId(), messages: [], updatedAt: Date.now() }
}

/**
 * Shrinks one conversation before it is written.
 *
 * The full result set is worth keeping on screen but not worth keeping on
 * disk forever, so only the first rows of each answer are stored. The saved
 * copy notes that it was trimmed, so the table can say so when reloaded.
 */
function trimForStorage(conversation) {
  return {
    ...conversation,
    messages: conversation.messages.map((message) => {
      if (message.role !== 'answer' || !message.rows) return message
      if (message.rows.length <= MAX_ROWS_STORED) return message
      return {
        ...message,
        rows: message.rows.slice(0, MAX_ROWS_STORED),
        truncated: true,
      }
    }),
  }
}

/** Reads every saved conversation. Returns [] if there is nothing usable. */
export function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []

    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    // Never trust what comes back. The data could have been written by an
    // older version of this app, or edited by hand in devtools.
    return parsed
      .filter(
        (conversation) =>
          conversation &&
          typeof conversation.id === 'string' &&
          Array.isArray(conversation.messages),
      )
      .slice(0, MAX_CONVERSATIONS)
  } catch {
    // Corrupt JSON, or storage blocked entirely. Start clean rather than crash.
    return []
  }
}

/**
 * Writes the conversations, newest first, dropping the oldest if the browser
 * runs out of room.
 */
export function saveConversations(conversations) {
  // Only conversations with something in them are worth keeping.
  const worthSaving = conversations
    .filter((conversation) => conversation.messages.length > 0)
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, MAX_CONVERSATIONS)
    .map(trimForStorage)

  // If the quota is hit, drop the oldest conversation and try again. A few
  // attempts is enough: each one removes the largest easy win.
  let candidates = worthSaving
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(candidates))
      return true
    } catch {
      if (candidates.length <= 1) break
      candidates = candidates.slice(0, Math.ceil(candidates.length / 2))
    }
  }
  return false
}

/** Forgets everything. Used by the "Clear all" button. */
export function clearConversations() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Nothing useful to do if even removing fails.
  }
}

/** Turns a timestamp into "just now", "5m ago", "3d ago". */
export function relativeTime(timestamp) {
  const seconds = Math.round((Date.now() - timestamp) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(timestamp).toLocaleDateString()
}
