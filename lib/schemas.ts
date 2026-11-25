import { z } from 'zod'
import { DEFAULT_LIMITS } from './config'

const requestId = z.string().nullish().transform((value) => value ?? '')
const generation = z.number().int().nonnegative()
const nullableString = z.string().nullish().transform((value) => value ?? null)

export const healthSchema = z.object({
  status: z.string(),
  timestamp: z.string(),
  request_id: requestId,
})

export const readySchema = z.object({
  status: z.enum(['ready', 'unready']),
  generation,
  document_count: z.number().int().nonnegative(),
  reason: nullableString,
  request_id: requestId,
})

const configFields = z.object({
  allowed_extensions: z.array(z.string()).default(DEFAULT_LIMITS.allowed_extensions),
  max_file_size: z.number().int().positive().default(DEFAULT_LIMITS.max_file_size),
  max_files: z.number().int().positive().default(DEFAULT_LIMITS.max_files),
  max_query_length: z.number().int().positive().default(DEFAULT_LIMITS.max_query_length),
  ranking_modes: z.array(z.string()).default(DEFAULT_LIMITS.ranking_modes),
  retrieval_modes: z.array(z.string()).default(DEFAULT_LIMITS.retrieval_modes),
  request_id: requestId,
})

export const configSchema = z.preprocess((value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value
  const raw = value as Record<string, unknown>
  return {
    ...raw,
    allowed_extensions: raw.allowed_extensions ?? raw.extensions ?? raw.allowed_extensions_list,
    max_file_size: raw.max_file_size ?? raw.max_file_size_bytes ?? raw.max_upload_bytes,
    max_files: raw.max_files ?? raw.max_file_count,
    max_query_length: raw.max_query_length ?? raw.max_query_chars,
    ranking_modes: raw.ranking_modes ?? raw.rankings,
    retrieval_modes: raw.retrieval_modes ?? raw.modes,
  }
}, configFields)

export const uploadSchema = z.object({
  upload_id: z.string().min(1),
  file_count: z.number().int().nonnegative(),
  rejected: z.array(z.string()).default([]),
  generation,
  request_id: requestId,
})

export const startIndexSchema = z.object({
  job_id: z.string().min(1),
  status: z.literal('queued'),
  generation,
  request_id: requestId,
})

export const indexStatusSchema = z.object({
  job_id: z.string(),
  kind: z.string(),
  status: z.string(),
  progress: z.number(),
  processed: z.number().int().nonnegative(),
  succeeded: z.number().int().nonnegative(),
  skipped: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative(),
  error: nullableString,
  generation,
  created_at: z.string(),
  updated_at: z.string(),
  finished_at: nullableString,
  request_id: requestId,
})

export const cancelSchema = z.object({
  job_id: z.string(),
  status: z.literal('cancelling'),
  request_id: requestId,
})

const facetCounts = z.record(z.string(), z.number())

export const searchResultSchema = z.object({
  doc_id: z.string(),
  filename: z.string(),
  source_type: z.string(),
  source_url: nullableString,
  score: z.number(),
  raw_score: z.number(),
  snippet: z.string(),
  word_count: z.number().int().nonnegative(),
  file_size_bytes: z.number().int().nonnegative(),
  indexed_at: z.string(),
  total_matches: z.number().int().nonnegative(),
  matched_positions: z.array(z.number().int().nonnegative()),
  explanation: z.record(z.string(), z.unknown()),
})

export const searchResponseSchema = z.object({
  query: z.string(),
  ranking: z.string(),
  mode: z.string(),
  generation,
  total_results: z.number().int().nonnegative(),
  results: z.array(searchResultSchema),
  correction: nullableString,
  facets: z.object({
    source_type: facetCounts,
    file_type: facetCounts,
  }).default({ source_type: {}, file_type: {} }),
  elapsed_ms: z.number(),
  request_id: requestId,
})

export const documentSchema = z.string()

export const errorResponseSchema = z.object({
  error: z.union([
    z.object({
      code: z.string().nullish().transform((value) => value ?? 'UNKNOWN'),
      message: z.string(),
    }),
    z.string(),
  ]),
  request_id: requestId,
})
