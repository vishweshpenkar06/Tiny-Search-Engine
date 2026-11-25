export const API_BASE = '/api'

export const DEFAULT_LIMITS = {
  allowed_extensions: ['txt', 'md', 'markdown', 'html', 'htm', 'csv'],
  max_file_size: 10 * 1024 * 1024,
  max_files: 100,
  max_query_length: 500,
  ranking_modes: ['tfidf', 'bm25', 'learned'],
  retrieval_modes: ['lexical', 'semantic', 'hybrid'],
}

export const config = {
  apiBase: API_BASE,
  appName: process.env.NEXT_PUBLIC_APP_NAME || 'Tiny Search Engine',
  isDev: process.env.NODE_ENV === 'development',
  requestTimeoutMs: 15000,
  cacheTtlMs: 60000,
  cacheMaxEntries: 50,
  pageSize: 10,
}
