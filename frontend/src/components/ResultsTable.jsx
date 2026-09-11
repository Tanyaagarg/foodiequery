/* --------------------------------------------------------------------------
   ResultsTable.jsx
   The data table, with the toolbar a real product would put above it.

   The columns are not known ahead of time. Every question returns a different
   shape, so the table reads the column names out of the response and builds
   its own headers.

   Styling is deliberately conventional: a filled sticky header, hairline row
   dividers, right-aligned numbers, a hover state. People already know how to
   read a table that looks like this, and familiarity beats novelty for data.
   -------------------------------------------------------------------------- */

import { useState } from 'react'
import { Check, Copy, Download } from 'lucide-react'

function prettyHeader(name) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

/** Booleans arrive from MySQL as 1 and 0, but they are labels, not amounts. */
function isBooleanColumn(column) {
  return /^(online_order|book_table)$/i.test(column)
}

/** Only real quantities get right-aligned, so the digits stack in a column. */
function isNumericColumn(column, rows) {
  if (isBooleanColumn(column)) return false
  return rows.some((row) => typeof row[column] === 'number')
}

function formatCell(column, value) {
  if (value === null || value === undefined) {
    return <span className="text-slate-300">&mdash;</span>
  }

  // MySQL returns booleans as 1 and 0.
  if (isBooleanColumn(column)) {
    const yes = value === 1 || value === true
    return (
      <span
        className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${
          yes ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
        }`}
      >
        {yes ? 'Yes' : 'No'}
      </span>
    )
  }

  if (typeof value === 'number') {
    if (/cost|price|spend/i.test(column)) return `₹${value.toLocaleString('en-IN')}`
    if (/pct|percent/i.test(column)) return `${value}%`
    if (/rating|score/i.test(column)) return value.toFixed(Number.isInteger(value) ? 1 : 2)
    return value.toLocaleString('en-IN')
  }

  return String(value)
}

/** Builds a CSV string from the results, so the data can leave the app. */
function toCsv(columns, rows) {
  const escape = (value) => {
    if (value === null || value === undefined) return ''
    const text = String(value)
    // A value containing a comma, quote or newline has to be wrapped in quotes,
    // and any quote inside it doubled. This is the actual CSV rule, and
    // skipping it is why so many exports open broken in Excel.
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  const header = columns.map(escape).join(',')
  const body = rows.map((row) => columns.map((column) => escape(row[column])).join(','))
  return [header, ...body].join('\n')
}

export default function ResultsTable({ columns, rows, truncated }) {
  const [copied, setCopied] = useState(false)

  if (!rows?.length) {
    return (
      <div className="mt-4 rounded-lg border border-dashed border-slate-200 bg-slate-25 px-4 py-6 text-center">
        <p className="text-sm text-slate-500">No rows matched that question.</p>
        <p className="mt-1 text-[13px] text-slate-400">
          Try removing a filter, or widening the price or rating range.
        </p>
      </div>
    )
  }

  async function copyCsv() {
    await navigator.clipboard.writeText(toCsv(columns, rows))
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  function downloadCsv() {
    // A Blob is a file held in memory. We point a temporary link at it and
    // click it, which is the standard way to trigger a browser download
    // without a server involved.
    const blob = new Blob([toCsv(columns, rows)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'foodiequery-results.csv'
    link.click()
    URL.revokeObjectURL(url) // release the memory again
  }

  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-slate-200">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2">
        <span className="text-[12px] font-medium text-slate-500">
          {rows.length} {rows.length === 1 ? 'row' : 'rows'}
          {truncated && ' (first batch)'}
        </span>

        <div className="flex items-center gap-1">
          <button
            onClick={copyCsv}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] font-medium text-slate-600 transition-colors hover:bg-slate-200/70 hover:text-slate-900"
            title="Copy as CSV"
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            onClick={downloadCsv}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] font-medium text-slate-600 transition-colors hover:bg-slate-200/70 hover:text-slate-900"
            title="Download as CSV"
          >
            <Download size={13} />
            CSV
          </button>
        </div>
      </div>

      {/* max-h plus overflow makes the table its own scroll area, so a long
          result does not push the SQL panel off the bottom of the screen. */}
      <div className="max-h-[24rem] overflow-auto">
        <table className="min-w-full border-collapse text-[13px]">
          <thead className="sticky top-0 z-10 bg-white">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  className={`whitespace-nowrap border-b border-slate-200 px-3 py-2 font-medium text-slate-500 ${
                    isNumericColumn(column, rows) ? 'text-right' : 'text-left'
                  }`}
                >
                  {prettyHeader(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white">
            {rows.map((row, index) => (
              <tr key={index} className="transition-colors hover:bg-brand-50/40">
                {columns.map((column) => (
                  <td
                    key={column}
                    className={`tabular max-w-[22rem] truncate border-b border-slate-100 px-3 py-2 text-slate-700 ${
                      isNumericColumn(column, rows) ? 'text-right' : 'text-left'
                    } ${column === columns[0] ? 'font-medium text-slate-900' : ''}`}
                    title={String(row[column] ?? '')}
                  >
                    {formatCell(column, row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
