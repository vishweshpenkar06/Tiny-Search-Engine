export type RankingMode = 'tfidf' | 'bm25'
export type RetrievalMode = 'lexical' | 'semantic' | 'hybrid'
export type SortMode = 'relevance' | 'filename' | 'size'

export interface RequestOptions {
  signal?: AbortSignal
  timeoutMs?: number
}

export interface ApiErrorBody {
  code: string
  message: string
}

export interface HealthResponse {
  status: string
  timestamp: string
  request_id: string
}

export interface ReadyResponse {
  status: 'ready' | 'unready'
  generation: number
  document_count: number
  reason: string | null
  request_id: string
}

export interface PublicConfig {
  allowed_extensions: string[]
  max_file_size: number
  max_files: number
  max_query_length: number
  ranking_modes: string[]
  retrieval_modes: string[]
  request_id: string
}

export interface UploadResponse {
  upload_id: string
  file_count: number
  rejected: string[]
  generation: number
  request_id: string
}

export interface StartIndexResponse {
  job_id: string
  status: 'queued'
  generation: number
  request_id: string
}

export interface IndexStatus {
  job_id: string
  kind: string
  status: string
  progress: number
  processed: number
  succeeded: number
  skipped: number
  failed: number
  error: string | null
  generation: number
  created_at: string
  updated_at: string
  finished_at: string | null
  request_id: string
}

export interface CancelResponse {
  job_id: string
  status: 'cancelling'
  request_id: string
}

export interface SearchFilters {
  source_type?: string
  file_type?: string
}

export interface SearchRequest {
  query: string
  ranking?: RankingMode
  mode?: RetrievalMode
  fuzzy?: boolean
  threshold?: number
  limit?: number
  offset?: number
  sort?: SortMode
  filters?: SearchFilters
}

export interface SearchResult {
  doc_id: string
  filename: string
  source_type: string
  source_url: string | null
  score: number
  raw_score: number
  snippet: string
  word_count: number
  file_size_bytes: number
  indexed_at: string
  total_matches: number
  matched_positions: number[]
  explanation: Record<string, unknown>
}

export interface SearchResponse {
  query: string
  ranking: string
  mode: string
  generation: number
  total_results: number
  results: SearchResult[]
  correction: string | null
  facets: {
    source_type: Record<string, number>
    file_type: Record<string, number>
  }
  elapsed_ms: number
  request_id: string
}
