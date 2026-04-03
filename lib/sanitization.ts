/**
 * Input sanitization utilities — strips dangerous characters from user input
 * before passing to the search engine or displaying in the UI.
 */

// Characters that could be used in injection or XSS attempts
const DANGEROUS_PATTERN = /[<>&"'`\\]/g

// Max lengths per field
const MAX_QUERY_LENGTH = 500
const MAX_FILENAME_LENGTH = 255

/**
 * Sanitize a search query string.
 * - Trims whitespace
 * - Removes dangerous chars
 * - Enforces max length
 */
export function sanitizeQuery(input: string): string {
  if (!input || typeof input !== 'string') return ''
  return input
    .trim()
    .replace(DANGEROUS_PATTERN, '')
    .slice(0, MAX_QUERY_LENGTH)
}

/**
 * Sanitize a filename for safe display.
 */
export function sanitizeFilename(input: string): string {
  if (!input || typeof input !== 'string') return ''
  return input
    .trim()
    .replace(DANGEROUS_PATTERN, '')
    .slice(0, MAX_FILENAME_LENGTH)
}

/**
 * Escape HTML entities in a string before inserting into the DOM.
 * Use this when you must render user content as text but cannot use
 * React's built-in escaping (e.g., dangerouslySetInnerHTML).
 */
export function escapeHtml(input: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }
  return input.replace(/[&<>"']/g, (char) => map[char] ?? char)
}

/**
 * Validate that a string is a safe relative path (no traversal).
 */
export function isSafePath(path: string): boolean {
  if (!path || typeof path !== 'string') return false
  // Block path traversal attempts
  if (path.includes('..') || path.includes('//') || path.startsWith('/')) return false
  return true
}
