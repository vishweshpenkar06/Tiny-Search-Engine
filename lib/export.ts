import type { SearchResult } from './types'

function safeCell(value: string | number): string {
  let text = String(value)
  if (/^\s*[=+@\-]/.test(text)) text = `'${text}`
  return `"${text.replace(/"/g, '""')}"`
}

function downloadFile(content: string, filename: string, type: string): void {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

function exportable(result: SearchResult) {
  return {
    doc_id: result.doc_id,
    filename: result.filename,
    source_type: result.source_type,
    source_url: result.source_url,
    score: result.score,
    raw_score: result.raw_score,
    snippet: result.snippet,
    word_count: result.word_count,
    file_size_bytes: result.file_size_bytes,
    indexed_at: result.indexed_at,
    total_matches: result.total_matches,
    matched_positions: result.matched_positions,
    explanation: result.explanation,
  }
}

export function exportAsJSON(results: SearchResult[]): void {
  const json = JSON.stringify(results.map(exportable), null, 2)
  downloadFile(json, 'search_results.json', 'application/json')
}

export function exportAsCSV(results: SearchResult[]): void {
  const headers = [
    'doc_id',
    'filename',
    'source_type',
    'source_url',
    'score',
    'raw_score',
    'total_matches',
    'word_count',
    'file_size_bytes',
    'indexed_at',
    'snippet',
  ]
  const rows = results.map((result) => [
    safeCell(result.doc_id),
    safeCell(result.filename),
    safeCell(result.source_type),
    safeCell(result.source_url ?? ''),
    safeCell(result.score),
    safeCell(result.raw_score),
    safeCell(result.total_matches),
    safeCell(result.word_count),
    safeCell(result.file_size_bytes),
    safeCell(result.indexed_at),
    safeCell(result.snippet),
  ].join(','))
  const csv = [headers.join(','), ...rows].join('\r\n')
  downloadFile(csv, 'search_results.csv', 'text/csv;charset=utf-8')
}
