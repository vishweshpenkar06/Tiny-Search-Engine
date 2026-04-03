export interface SearchResult {
  doc_id: string
  filename: string
  path: string
  score: number
  snippet: string
  matched_positions: number[]
  word_count?: number
  file_size?: string
  indexed_at?: string
}

export interface SearchResponse {
  query: string
  results_count: number
  search_time_ms: number
  results: SearchResult[]
}

export interface IndexStatus {
  status: 'idle' | 'indexing' | 'complete' | 'error'
  progress: number
  files_indexed: number
  total_files: number
  elapsed_time: string
  estimated_remaining: string
  current_file?: string
  error_message?: string
}

export interface IndexRequest {
  folder_path?: string
  files?: File[]
}

export interface IndexResponse {
  status: string
  files_count: number
  estimated_time: string
}
