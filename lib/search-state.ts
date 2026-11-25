import { DEFAULT_LIMITS } from './config'
import type { RankingMode, RetrievalMode, SortMode } from './types'

export const PAGE_SIZE = 10
export const RECENT_SEARCHES_KEY = 'recentSearches'

export interface SearchState {
  q: string
  ranking: RankingMode
  mode: RetrievalMode
  fuzzy: boolean
  threshold: number
  sort: SortMode
  offset: number
  source_type: string
  file_type: string
}

export const DEFAULT_SEARCH_STATE: SearchState = {
  q: '',
  ranking: 'bm25',
  mode: 'lexical',
  fuzzy: false,
  threshold: 0,
  sort: 'relevance',
  offset: 0,
  source_type: '',
  file_type: '',
}

function oneOf<T extends string>(value: string | null, allowed: readonly string[], fallback: T): T {
  return value !== null && allowed.includes(value) ? (value as T) : fallback
}

function boundedNumber(value: string | null, fallback: number, min: number, max: number): number {
  if (value === null) return fallback
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(max, Math.max(min, parsed))
}

export function parseSearchState(input: URLSearchParams | string | null): SearchState {
  const params = typeof input === 'string' || input === null
    ? new URLSearchParams(input ?? '')
    : input

  const rawThreshold = params.get('threshold')
  const rawOffset = params.get('offset')

  return {
    q: (params.get('q') ?? '').slice(0, DEFAULT_LIMITS.max_query_length),
    ranking: oneOf<RankingMode>(params.get('ranking'), DEFAULT_LIMITS.ranking_modes, DEFAULT_SEARCH_STATE.ranking),
    mode: oneOf<RetrievalMode>(params.get('mode'), DEFAULT_LIMITS.retrieval_modes, DEFAULT_SEARCH_STATE.mode),
    fuzzy: params.get('fuzzy') === '1' || params.get('fuzzy') === 'true',
    threshold: rawThreshold === null ? 0 : boundedNumber(rawThreshold, 0, 0, 1),
    sort: oneOf<SortMode>(params.get('sort'), ['relevance', 'filename', 'size'], DEFAULT_SEARCH_STATE.sort),
    offset: rawOffset === null ? 0 : Math.floor(boundedNumber(rawOffset, 0, 0, 1000000)),
    source_type: params.get('source_type') ?? '',
    file_type: params.get('file_type') ?? '',
  }
}

export function serializeSearchState(state: SearchState): URLSearchParams {
  const params = new URLSearchParams()
  const q = state.q.trim()

  if (q) params.set('q', q)
  if (state.ranking !== DEFAULT_SEARCH_STATE.ranking) params.set('ranking', state.ranking)
  if (state.mode !== DEFAULT_SEARCH_STATE.mode) params.set('mode', state.mode)
  if (state.fuzzy) params.set('fuzzy', '1')
  if (state.threshold > 0) params.set('threshold', String(Math.round(state.threshold * 100) / 100))
  if (state.sort !== DEFAULT_SEARCH_STATE.sort) params.set('sort', state.sort)
  if (state.offset > 0) params.set('offset', String(state.offset))
  if (state.source_type) params.set('source_type', state.source_type)
  if (state.file_type) params.set('file_type', state.file_type)

  return params
}

export function buildSearchHref(state: SearchState): string {
  const query = serializeSearchState(state).toString()
  return query ? `/search?${query}` : '/search'
}

export function withSearchState(state: SearchState, patch: Partial<SearchState>): SearchState {
  return parseSearchState(serializeSearchState({ ...state, ...patch }))
}

export function readRecentSearches(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const stored = window.localStorage.getItem(RECENT_SEARCHES_KEY)
    if (!stored) return []
    const parsed: unknown = JSON.parse(stored)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is string => typeof item === 'string').slice(0, 5)
  } catch {
    return []
  }
}

export function saveRecentSearch(query: string): string[] {
  const value = query.trim()
  if (typeof window === 'undefined') return value ? [value] : []
  if (!value) return readRecentSearches()
  const next = [value, ...readRecentSearches().filter((item) => item !== value)].slice(0, 5)
  try {
    window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(next))
  } catch {
    return next
  }
  return next
}
