import { SearchResult } from './types'

export function exportAsJSON(results: SearchResult[]) {
  const json = JSON.stringify(results, null, 2)
  downloadFile(json, 'search_results.json', 'application/json')
}

export function exportAsCSV(results: SearchResult[]) {
  const headers = ['Filename', 'Path', 'Score', 'Snippet']
  
  const csvRows = results.map(r => {
    // Escape quotes and wrap in quotes for CSV
    const snippet = r.snippet.replace(/"/g, '""')
    const filename = r.filename.replace(/"/g, '""')
    const path = r.path.replace(/"/g, '""')
    
    return `"${filename}","${path}","${r.score}","${snippet}"`
  })
  
  const csv = [headers.join(','), ...csvRows].join('\n')
  downloadFile(csv, 'search_results.csv', 'text/csv')
}

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
