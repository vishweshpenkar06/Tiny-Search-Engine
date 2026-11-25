import { z } from 'zod'
import { config, DEFAULT_LIMITS } from './config'
import * as schemas from './schemas'
import type {
  CancelResponse,
  HealthResponse,
  IndexStatus,
  PublicConfig,
  ReadyResponse,
  RequestOptions,
  SearchRequest,
  SearchResponse,
  StartIndexResponse,
  UploadResponse,
} from './types'

export class ApiError extends Error {
  readonly code: string
  readonly status?: number
  readonly requestId?: string

  constructor(message: string, code = 'UNKNOWN', status?: number, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.requestId = requestId
  }
}

interface CacheEntry {
  data: unknown
  expires: number
}

const responseCache = new Map<string, CacheEntry>()
const pendingRequests = new Map<string, Promise<unknown>>()
let observedGeneration = 0

function recordGeneration(value: number): void {
  if (Number.isFinite(value) && value > observedGeneration) {
    observedGeneration = value
    responseCache.clear()
  }
}

function getCached<T>(key: string): T | undefined {
  const entry = responseCache.get(key)
  if (!entry) return undefined
  if (entry.expires <= Date.now()) {
    responseCache.delete(key)
    return undefined
  }
  return entry.data as T
}

function setCached(key: string, data: unknown): void {
  if (responseCache.size >= config.cacheMaxEntries) {
    const oldest = responseCache.keys().next().value
    if (oldest !== undefined) responseCache.delete(oldest)
  }
  responseCache.set(key, { data, expires: Date.now() + config.cacheTtlMs })
}

function createSignal(external?: AbortSignal, timeoutMs = config.requestTimeoutMs) {
  const controller = new AbortController()
  let timedOut = false
  const onAbort = () => controller.abort()

  if (external) {
    if (external.aborted) controller.abort()
    else external.addEventListener('abort', onAbort, { once: true })
  }
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    cleanup: () => {
      clearTimeout(timer)
      external?.removeEventListener('abort', onAbort)
    },
  }
}

function parseMaybeJson(text: string): unknown {
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function extractError(status: number, payload: unknown, raw: string): ApiError {
  const parsed = schemas.errorResponseSchema.safeParse(payload)
  if (parsed.success) {
    const error = parsed.data.error
    if (typeof error === 'string') {
      return new ApiError(error, 'HTTP_ERROR', status, parsed.data.request_id)
    }
    return new ApiError(error.message, error.code, status, parsed.data.request_id)
  }
  const message = raw.trim().slice(0, 200)
  return new ApiError(message || `Request failed with status ${status}`, 'HTTP_ERROR', status)
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  validator: z.ZodTypeAny,
  options?: RequestOptions,
): Promise<T> {
  const { signal, timedOut, cleanup } = createSignal(options?.signal, options?.timeoutMs)
  try {
    const response = await fetch(`${config.apiBase}${path}`, { ...init, signal })
    const text = await response.text()
    const payload = parseMaybeJson(text)

    if (!response.ok) throw extractError(response.status, payload, text)

    const parsed = validator.safeParse(payload)
    if (!parsed.success) {
      throw new ApiError('The server returned an unexpected response format.', 'SCHEMA_MISMATCH', response.status)
    }

    const data = parsed.data as T
    const withGeneration = data as unknown as { generation?: unknown }
    if (typeof withGeneration?.generation === 'number') recordGeneration(withGeneration.generation)
    return data
  } catch (error) {
    if (timedOut()) throw new ApiError('The request timed out. Please try again.', 'TIMEOUT')
    throw error
  } finally {
    cleanup()
  }
}

async function requestText(path: string, options?: RequestOptions): Promise<string> {
  const { signal, timedOut, cleanup } = createSignal(options?.signal, options?.timeoutMs)
  try {
    const response = await fetch(`${config.apiBase}${path}`, { method: 'GET', signal })
    const text = await response.text()
    if (!response.ok) throw extractError(response.status, parseMaybeJson(text), text)
    const parsed = schemas.documentSchema.safeParse(text)
    if (!parsed.success) {
      throw new ApiError('The document response could not be read.', 'SCHEMA_MISMATCH', response.status)
    }
    return parsed.data
  } catch (error) {
    if (timedOut()) throw new ApiError('The request timed out. Please try again.', 'TIMEOUT')
    throw error
  } finally {
    cleanup()
  }
}

export function getHealth(options?: RequestOptions): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health', { method: 'GET' }, schemas.healthSchema, options)
}

export function getReady(options?: RequestOptions): Promise<ReadyResponse> {
  return requestJson<ReadyResponse>('/readyz', { method: 'GET' }, schemas.readySchema, options)
}

export function getConfig(options?: RequestOptions): Promise<PublicConfig> {
  const key = `config:${observedGeneration}`
  const cached = getCached<PublicConfig>(key)
  if (cached) return Promise.resolve(cached)

  const existing = pendingRequests.get(key)
  if (existing) return existing as Promise<PublicConfig>

  const request = requestJson<PublicConfig>('/config', { method: 'GET' }, schemas.configSchema, options)
    .then((data) => {
      setCached(`config:${observedGeneration}`, data)
      return data
    })
    .finally(() => {
      pendingRequests.delete(key)
    })

  pendingRequests.set(key, request)
  return request
}

export function uploadFiles(files: File[], options?: RequestOptions): Promise<UploadResponse> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))

  return requestJson<UploadResponse>(
    '/upload',
    { method: 'POST', body: formData },
    schemas.uploadSchema,
    options,
  ).then((data) => {
    recordGeneration(data.generation)
    responseCache.clear()
    return data
  })
}

export function startIndexing(
  uploadId: string,
  ranking: 'tfidf' | 'bm25' = 'bm25',
  options?: RequestOptions,
): Promise<StartIndexResponse> {
  return requestJson<StartIndexResponse>(
    '/index',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: uploadId, ranking }),
    },
    schemas.startIndexSchema,
    options,
  ).then((data) => {
    recordGeneration(data.generation)
    responseCache.clear()
    return data
  })
}

export function getIndexStatus(jobId: string, options?: RequestOptions): Promise<IndexStatus> {
  return requestJson<IndexStatus>(
    `/index/status?job_id=${encodeURIComponent(jobId)}`,
    { method: 'GET' },
    schemas.indexStatusSchema,
    options,
  )
}

export function cancelIndexing(jobId: string, options?: RequestOptions): Promise<CancelResponse> {
  return requestJson<CancelResponse>(
    `/index/jobs/${encodeURIComponent(jobId)}/cancel`,
    { method: 'POST' },
    schemas.cancelSchema,
    options,
  ).then((data) => {
    responseCache.clear()
    return data
  })
}

function clampInteger(value: number | undefined, min: number, max: number, fallback: number): number {
  if (value === undefined || !Number.isFinite(value)) return fallback
  return Math.min(max, Math.max(min, Math.floor(value)))
}

function normalizeSearchBody(params: SearchRequest): Record<string, unknown> {
  const query = (params.query ?? '').trim().slice(0, DEFAULT_LIMITS.max_query_length)
  const ranking = params.ranking === 'tfidf' ? 'tfidf' : 'bm25'
  const mode = params.mode === 'semantic' || params.mode === 'hybrid' ? params.mode : 'lexical'
  const sort = params.sort === 'filename' || params.sort === 'size' ? params.sort : 'relevance'
  const threshold = typeof params.threshold === 'number' && Number.isFinite(params.threshold)
    ? Math.min(1, Math.max(0, params.threshold))
    : 0
  const limit = clampInteger(params.limit, 1, 100, 10)
  const offset = clampInteger(params.offset, 0, 1000000, 0)
  const sourceType = params.filters?.source_type?.trim() ?? ''
  const fileType = params.filters?.file_type?.trim() ?? ''
  const filters = sourceType || fileType
    ? { ...(sourceType ? { source_type: sourceType } : {}), ...(fileType ? { file_type: fileType } : {}) }
    : undefined

  return {
    query,
    ranking,
    mode,
    fuzzy: Boolean(params.fuzzy),
    threshold,
    limit,
    offset,
    sort,
    ...(filters ? { filters } : {}),
  }
}

function emptySearchResponse(body: Record<string, unknown>): SearchResponse {
  return {
    query: String(body.query ?? ''),
    ranking: String(body.ranking ?? 'bm25'),
    mode: String(body.mode ?? 'lexical'),
    generation: observedGeneration,
    total_results: 0,
    results: [],
    correction: null,
    facets: { source_type: {}, file_type: {} },
    elapsed_ms: 0,
    request_id: '',
  }
}

function asRequestOptions(value: number | RequestOptions | undefined): RequestOptions | undefined {
  return typeof value === 'object' && value !== null ? value : undefined
}

export function search(query: string, topK?: number, threshold?: number, options?: RequestOptions): Promise<SearchResponse>
export function search(params: SearchRequest, options?: RequestOptions): Promise<SearchResponse>
export function search(
  queryOrParams: string | SearchRequest,
  topKOrOptions?: number | RequestOptions,
  thresholdArg?: number,
  optionsArg?: RequestOptions,
): Promise<SearchResponse> {
  const options = typeof queryOrParams === 'string' ? optionsArg : asRequestOptions(topKOrOptions)
  const params: SearchRequest = typeof queryOrParams === 'string'
    ? {
        query: queryOrParams,
        limit: typeof topKOrOptions === 'number' ? topKOrOptions : undefined,
        threshold: thresholdArg,
      }
    : queryOrParams
  const body = normalizeSearchBody(params)

  if (!body.query) return Promise.resolve(emptySearchResponse(body))

  const key = `search:${observedGeneration}:${JSON.stringify(body)}`
  const cached = getCached<SearchResponse>(key)
  if (cached) return Promise.resolve(cached)

  const existing = pendingRequests.get(key)
  if (existing) return existing as Promise<SearchResponse>

  const request = requestJson<SearchResponse>(
    '/search',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    schemas.searchResponseSchema,
    options,
  )
    .then((data) => {
      setCached(key, data)
      return data
    })
    .finally(() => {
      pendingRequests.delete(key)
    })

  pendingRequests.set(key, request)
  return request
}

export function getDocumentUrl(docId: string): string {
  return `${config.apiBase}/documents/${encodeURIComponent(docId)}`
}

export function getDocument(docId: string, options?: RequestOptions): Promise<string> {
  return requestText(`/documents/${encodeURIComponent(docId)}`, options)
}
