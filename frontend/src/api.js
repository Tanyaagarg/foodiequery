/* --------------------------------------------------------------------------
   api.js
   Every call to the backend lives here, so no component has to know a URL.

   Requests go to /api/... and Vite forwards them to the FastAPI server on
   port 8000. That forwarding is set up in vite.config.js.
   -------------------------------------------------------------------------- */

const BASE = import.meta.env.VITE_API_URL ?? ''

/**
 * Reads the error message out of a failed response.
 * FastAPI puts a human-readable reason in a "detail" field, which is far more
 * useful to show than "Request failed with status 422".
 */
async function readError(response) {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail[0]?.msg ?? 'Invalid request.'
  } catch {
    // response had no JSON body, fall through to the generic messages
  }
  if (response.status === 429) return 'Too many questions at once. Wait a minute.'
  if (response.status >= 500) return 'The server had a problem. Try again shortly.'
  return `Something went wrong (${response.status}).`
}

/**
 * Sends a question and returns { sql, columns, rows, insight, ... }.
 *
 * `history` is the recent answered turns, oldest first, each { question, sql }.
 * The model has no memory of its own, so this is what lets a follow-up like
 * "same for Koramangala" mean anything.
 */
export async function askQuestion(question, history = []) {
  let response
  try {
    response = await fetch(`${BASE}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, history }),
    })
  } catch {
    // fetch only throws when the server cannot be reached at all.
    throw new Error(
      'Cannot reach the server. Is the backend running on port 8000?',
    )
  }

  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

/** Sample questions for the sidebar. Returns [] if the backend is down. */
export async function fetchExamples() {
  try {
    const response = await fetch(`${BASE}/api/examples`)
    if (!response.ok) return []
    const body = await response.json()
    return body.examples ?? []
  } catch {
    return []
  }
}

/** Used by the header dot to show whether the backend is alive. */
export async function fetchHealth() {
  try {
    const response = await fetch(`${BASE}/api/health`)
    if (!response.ok) return { status: 'down' }
    return response.json()
  } catch {
    return { status: 'down' }
  }
}
