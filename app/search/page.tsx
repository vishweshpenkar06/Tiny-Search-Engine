'use client'

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Header } from '@/components/header'
import { SearchBar } from '@/components/search-bar'
import { ResultCard } from '@/components/result-card'
import { ResultModal } from '@/components/result-modal'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { search } from '@/lib/api'
import type { SearchResponse, SearchResult } from '@/lib/types'
import {
  buildSearchHref,
  PAGE_SIZE,
  parseSearchState,
  readRecentSearches,
  saveRecentSearch,
  withSearchState,
  type SearchState,
} from '@/lib/search-state'
import { Search, SlidersHorizontal, FileSearch, AlertCircle } from 'lucide-react'
import { useDebounce } from '@/hooks/use-debounce'
import { ResultSkeleton } from '@/components/result-skeleton'
import { ErrorBoundary } from '@/components/error-boundary'

const RANKING_OPTIONS: Array<{ value: SearchState['ranking']; label: string }> = [
  { value: 'bm25', label: 'BM25' },
  { value: 'tfidf', label: 'TF-IDF' },
]

const MODE_OPTIONS: Array<{ value: SearchState['mode']; label: string }> = [
  { value: 'lexical', label: 'Lexical' },
  { value: 'semantic', label: 'Semantic' },
  { value: 'hybrid', label: 'Hybrid' },
]

const SORT_OPTIONS: Array<{ value: SearchState['sort']; label: string }> = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'filename', label: 'Filename' },
  { value: 'size', label: 'Size' },
]

function SearchContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const urlState = useMemo(() => parseSearchState(searchParams.toString()), [searchParams])

  const [query, setQuery] = useState(urlState.q)
  const [storedResults, setStoredResults] = useState<SearchResponse | null>(null)
  const [storedLoading, setStoredLoading] = useState(false)
  const [storedError, setStoredError] = useState<string | null>(null)
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [recentSearches, setRecentSearches] = useState<string[]>(() => readRecentSearches())
  const [retryToken, setRetryToken] = useState(0)

  const debouncedQuery = useDebounce(query, 350)
  const hasQuery = debouncedQuery.trim().length > 0
  const results = hasQuery ? storedResults : null
  const isLoading = hasQuery && storedLoading
  const error = hasQuery ? storedError : null
  const visibleSelectedResult = hasQuery ? selectedResult : null
  const abortRef = useRef<AbortController | null>(null)
  const sequenceRef = useRef(0)
  const pushedQueryRef = useRef(urlState.q)

  useEffect(() => {
    if (urlState.q !== pushedQueryRef.current) {
      pushedQueryRef.current = urlState.q
      setQuery(urlState.q)
    }
  }, [urlState.q])

  useEffect(() => {
    const current = parseSearchState(searchParams.toString())
    if (current.q !== debouncedQuery.trim()) {
      const next = withSearchState(current, { q: debouncedQuery.trim() })
      pushedQueryRef.current = next.q
      router.replace(buildSearchHref(next), { scroll: false })
    }
  }, [debouncedQuery, router, searchParams])

  const updateState = useCallback((patch: Partial<SearchState>) => {
    const base = parseSearchState(searchParams.toString())
    const next = withSearchState(base, patch)
    if (Object.keys(patch).some((key) => key !== 'offset')) next.offset = 0
    pushedQueryRef.current = next.q
    router.replace(buildSearchHref(next), { scroll: false })
  }, [router, searchParams])

  useEffect(() => {
    const trimmed = debouncedQuery.trim()
    if (!trimmed) {
      sequenceRef.current += 1
      abortRef.current?.abort()
      return
    }

    const sequence = ++sequenceRef.current
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setStoredLoading(true)
    setStoredError(null)
    setSelectedResult(null)

    search({
      query: trimmed,
      ranking: urlState.ranking,
      mode: urlState.mode,
      fuzzy: urlState.fuzzy,
      threshold: urlState.threshold,
      limit: PAGE_SIZE,
      offset: urlState.offset,
      sort: urlState.sort,
      filters: {
        source_type: urlState.source_type,
        file_type: urlState.file_type,
      },
    }, { signal: controller.signal })
      .then((data) => {
        if (sequence !== sequenceRef.current || controller.signal.aborted) return
        setStoredResults(data)
        setSelectedResult(null)
        setRecentSearches(saveRecentSearch(trimmed))
      })
      .catch((err: unknown) => {
        if (sequence !== sequenceRef.current || controller.signal.aborted) return
        setStoredError(err instanceof Error ? err.message : 'Search failed')
        setStoredResults(null)
        setSelectedResult(null)
      })
      .finally(() => {
        if (sequence === sequenceRef.current) setStoredLoading(false)
      })

    return () => controller.abort()
  }, [
    debouncedQuery,
    urlState.ranking,
    urlState.mode,
    urlState.fuzzy,
    urlState.threshold,
    urlState.offset,
    urlState.sort,
    urlState.source_type,
    urlState.file_type,
    retryToken,
  ])

  const total = results?.total_results ?? 0
  const resultCount = results?.results.length ?? 0
  const firstResult = total > 0 ? urlState.offset + 1 : 0
  const lastResult = urlState.offset + resultCount
  const canGoPrevious = urlState.offset > 0
  const canGoNext = results !== null && lastResult < total

  const sourceValues = Array.from(new Set([
    ...Object.keys(results?.facets?.source_type ?? {}),
    urlState.source_type,
  ].filter(Boolean)))
  const fileValues = Array.from(new Set([
    ...Object.keys(results?.facets?.file_type ?? {}),
    urlState.file_type,
  ].filter(Boolean)))

  const handleSubmit = (value: string) => {
    setQuery(value)
    updateState({ q: value })
  }

  return (
    <div className="min-h-screen bg-background">
      <Header showBackButton />

      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto max-w-[1200px] px-4 py-4 md:px-6 lg:px-12">
          <div className="flex items-center gap-4">
            <SearchBar
              value={query}
              onChange={setQuery}
              onSubmit={handleSubmit}
              placeholder="Search indexed documents..."
              isLoading={isLoading}
              maxLength={500}
              autoFocus
              className="min-w-0 flex-1"
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label={showFilters ? 'Hide search filters' : 'Show search filters'}
              aria-expanded={showFilters}
              className={cnFilterButton(showFilters)}
              onClick={() => setShowFilters((visible) => !visible)}
            >
              <SlidersHorizontal className="h-4 w-4" />
            </Button>
          </div>

          {showFilters && (
            <div className="mt-4 rounded-lg border border-border bg-card p-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="min-w-0">
                  <label htmlFor="ranking-filter" className="mb-1 block text-sm font-medium text-foreground">
                    Ranking
                  </label>
                  <select
                    id="ranking-filter"
                    className="h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
                    value={urlState.ranking}
                    onChange={(event) => updateState({ ranking: event.target.value as SearchState['ranking'] })}
                  >
                    {RANKING_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>

                <div className="min-w-0">
                  <label htmlFor="mode-filter" className="mb-1 block text-sm font-medium text-foreground">
                    Retrieval mode
                  </label>
                  <select
                    id="mode-filter"
                    className="h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
                    value={urlState.mode}
                    onChange={(event) => updateState({ mode: event.target.value as SearchState['mode'] })}
                  >
                    {MODE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>

                <div className="min-w-0">
                  <label htmlFor="sort-filter" className="mb-1 block text-sm font-medium text-foreground">
                    Sort by
                  </label>
                  <select
                    id="sort-filter"
                    className="h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
                    value={urlState.sort}
                    onChange={(event) => updateState({ sort: event.target.value as SearchState['sort'] })}
                  >
                    {SORT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>

                <div className="min-w-0">
                  <span className="mb-1 block text-sm font-medium text-foreground">Minimum relevance</span>
                  <div className="flex items-center gap-3">
                    <Slider
                      aria-label="Minimum relevance"
                      value={[Math.round(urlState.threshold * 100)]}
                      onValueChange={(value) => updateState({ threshold: value[0] / 100 })}
                      max={100}
                      step={5}
                      className="min-w-0 flex-1"
                    />
                    <span className="w-12 shrink-0 text-sm text-muted-foreground">
                      {(urlState.threshold * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <div className="flex items-end gap-2">
                  <input
                    id="fuzzy-filter"
                    type="checkbox"
                    className="h-4 w-4 rounded border-input focus-visible:ring-2 focus-visible:ring-ring"
                    checked={urlState.fuzzy}
                    onChange={(event) => updateState({ fuzzy: event.target.checked })}
                  />
                  <label htmlFor="fuzzy-filter" className="text-sm font-medium text-foreground">
                    Fuzzy matching
                  </label>
                </div>

                <div className="min-w-0">
                  <label htmlFor="source-filter" className="mb-1 block text-sm font-medium text-foreground">
                    Source type
                  </label>
                  <select
                    id="source-filter"
                    className="h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
                    value={urlState.source_type}
                    onChange={(event) => updateState({ source_type: event.target.value })}
                  >
                    <option value="">All sources</option>
                    {sourceValues.map((value) => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                </div>

                <div className="min-w-0">
                  <label htmlFor="file-filter" className="mb-1 block text-sm font-medium text-foreground">
                    File type
                  </label>
                  <select
                    id="file-filter"
                    className="h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
                    value={urlState.file_type}
                    onChange={(event) => updateState({ file_type: event.target.value })}
                  >
                    <option value="">All file types</option>
                    {fileValues.map((value) => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <main aria-busy={isLoading} className="mx-auto max-w-[1200px] px-4 py-6 md:px-6 lg:px-12">
        <div role="status" aria-live="polite" className="mb-6 flex min-h-5 items-center gap-2 text-sm text-muted-foreground">
          {isLoading && <Search className="h-4 w-4 shrink-0" />}
          {isLoading
            ? 'Searching…'
            : results
              ? `${total} result${total === 1 ? '' : 's'} · ${results.elapsed_ms.toFixed(0)} ms${resultCount > 0 ? ` · showing ${firstResult}–${lastResult}` : ''}`
              : ''}
        </div>

        {results?.correction && !isLoading && (
          <p className="mb-4 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            Did you mean
            <button
              type="button"
              onClick={() => handleSubmit(results.correction ?? '')}
              className="font-medium text-primary underline hover:no-underline focus-visible:ring-2 focus-visible:ring-ring"
            >
              {results.correction}
            </button>
            ?
          </p>
        )}

        {results && !isLoading && !error && (sourceValues.length > 0 || fileValues.length > 0) && (
          <div className="mb-6 flex flex-wrap items-center gap-2 text-xs">
            <span className="font-medium text-muted-foreground">Facets:</span>
            {sourceValues.map((value) => (
              <button
                key={`source-${value}`}
                type="button"
                aria-pressed={urlState.source_type === value}
                onClick={() => updateState({ source_type: urlState.source_type === value ? '' : value })}
                className="rounded-full border border-border bg-card px-3 py-1 text-foreground hover:border-primary focus-visible:ring-2 focus-visible:ring-ring aria-pressed:border-primary aria-pressed:bg-primary/10"
              >
                {value} ({results.facets?.source_type?.[value] ?? 0})
              </button>
            ))}
            {fileValues.map((value) => (
              <button
                key={`file-${value}`}
                type="button"
                aria-pressed={urlState.file_type === value}
                onClick={() => updateState({ file_type: urlState.file_type === value ? '' : value })}
                className="rounded-full border border-border bg-card px-3 py-1 text-foreground hover:border-primary focus-visible:ring-2 focus-visible:ring-ring aria-pressed:border-primary aria-pressed:bg-primary/10"
              >
                {value} ({results.facets?.file_type?.[value] ?? 0})
              </button>
            ))}
          </div>
        )}

        {error && (
          <div role="alert" className="mb-6">
            <ErrorBoundary error={error} onRetry={() => setRetryToken((token) => token + 1)} />
          </div>
        )}

        {isLoading && (
          <div className="mb-6">
            <ResultSkeleton />
          </div>
        )}

        {!isLoading && !error && results && results.results.length > 0 && (
          <div className="min-w-0 space-y-4">
            {results.results.map((result) => (
              <ResultCard
                key={result.doc_id}
                result={result}
                query={debouncedQuery}
                onClick={() => setSelectedResult(result)}
              />
            ))}

            <div className="flex flex-wrap items-center justify-center gap-3 pt-6">
              <Button
                type="button"
                variant="outline"
                disabled={!canGoPrevious}
                className="focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => updateState({ offset: Math.max(0, urlState.offset - PAGE_SIZE) })}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {Math.floor(urlState.offset / PAGE_SIZE) + 1}
              </span>
              <Button
                type="button"
                variant="outline"
                disabled={!canGoNext}
                className="focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => updateState({ offset: urlState.offset + PAGE_SIZE })}
              >
                Next
              </Button>
            </div>
          </div>
        )}

        {!isLoading && !error && results && results.results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <FileSearch className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-foreground">No results found</h3>
            <p className="mt-2 max-w-md break-words text-sm text-muted-foreground">
              Try different terms, lower the relevance threshold, or clear the active filters.
            </p>
          </div>
        )}

        {!isLoading && !error && !results && !query.trim() && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <Search className="h-8 w-8 text-primary" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-foreground">Ready to Search</h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Enter a search query. Use quotes for phrase matching, for example &quot;machine learning&quot;.
            </p>
          </div>
        )}

        {recentSearches.length > 0 && !results && !isLoading && (
          <div className="mx-auto mt-12 max-w-2xl">
            <h2 className="mb-3 text-sm font-semibold text-foreground">Recent searches</h2>
            <div className="flex flex-wrap gap-2">
              {recentSearches.map((item, index) => (
                <button
                  key={`${item}-${index}`}
                  type="button"
                  onClick={() => handleSubmit(item)}
                  className="max-w-full truncate rounded-full border border-border bg-card px-3 py-1 text-sm text-foreground hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <p className="sr-only">
            <AlertCircle className="h-4 w-4" />
            Search failed
          </p>
        )}
      </main>

      <ResultModal
        result={visibleSelectedResult}
        query={debouncedQuery}
        onClose={() => setSelectedResult(null)}
      />
    </div>
  )
}

function cnFilterButton(active: boolean): string {
  return active
    ? 'border-primary text-primary focus-visible:ring-2 focus-visible:ring-ring'
    : 'focus-visible:ring-2 focus-visible:ring-ring'
}

export default function SearchPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background">
        <Header showBackButton />
        <div className="flex items-center justify-center py-32">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      </div>
    }>
      <SearchContent />
    </Suspense>
  )
}
