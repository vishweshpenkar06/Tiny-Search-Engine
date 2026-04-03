'use client'

import { useState, useEffect, useCallback, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { Header } from '@/components/header'
import { SearchBar } from '@/components/search-bar'
import { ResultCard } from '@/components/result-card'
import { ResultModal } from '@/components/result-modal'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { search } from '@/lib/api'
import type { SearchResult, SearchResponse } from '@/lib/types'
import { Search, SlidersHorizontal, FileSearch, AlertCircle } from 'lucide-react'
import { useDebounce } from '@/hooks/use-debounce'
import { ResultSkeleton } from '@/components/result-skeleton'
import { ErrorBoundary } from '@/components/error-boundary'

function SearchContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [threshold, setThreshold] = useState(0)
  
  const [displayCount, setDisplayCount] = useState(10)
  const [sortBy, setSortBy] = useState<'relevance' | 'filename' | 'size'>('relevance')

  const debouncedQuery = useDebounce(query, 500)

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults(null)
      setError(null)
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const data = await search(searchQuery, 100, threshold)
      setResults(data)
      setDisplayCount(10) // Reset pagination on new search
      
      const saved = localStorage.getItem('recentSearches')
      const recent: string[] = saved ? JSON.parse(saved) : []
      const updated = [searchQuery, ...recent.filter(s => s !== searchQuery)].slice(0, 5)
      localStorage.setItem('recentSearches', JSON.stringify(updated))
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Search failed'
      setError(msg)
      setResults(null)
    } finally {
      setIsLoading(false)
    }
  }, [threshold])

  useEffect(() => {
    // Only search if it's the debounced value and not empty
    if (debouncedQuery) {
      performSearch(debouncedQuery)
    } else {
      setResults(null)
    }
  }, [debouncedQuery, performSearch])

  useEffect(() => {
    const initialQuery = searchParams.get('q')
    if (initialQuery && !query) {
      setQuery(initialQuery)
      // performSearch is handled by the debounced effect now
    }
  }, [searchParams, query])

  const sortedResults = results ? [...results.results].sort((a, b) => {
    if (sortBy === 'filename') return a.filename.localeCompare(b.filename)
    if (sortBy === 'size') {
        // basic approximation sorting: 
        const asize = a.file_size ? parseFloat(a.file_size) : 0
        const bsize = b.file_size ? parseFloat(b.file_size) : 0
        return bsize - asize
    }
    return b.score - a.score // relevance
  }) : []

  const handleSearch = (value: string) => {
    router.push(`/search?q=${encodeURIComponent(value)}`, { scroll: false })
    // performSearch is triggered by debounced effect
  }

  return (
    <div className="min-h-screen bg-background">
      <Header showBackButton />
      
      {/* Sticky Search Bar */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto max-w-[1200px] px-4 py-4 md:px-6 lg:px-12">
          <div className="flex items-center gap-4">
            <SearchBar
              value={query}
              onChange={setQuery}
              onSubmit={handleSearch}
              placeholder="Search indexed documents..."
              isLoading={isLoading}
              autoFocus
              className="flex-1"
            />
            <Button
              variant="outline"
              size="icon"
              onClick={() => setShowFilters(!showFilters)}
              className={showFilters ? 'border-primary text-primary' : ''}
            >
              <SlidersHorizontal className="h-4 w-4" />
            </Button>
          </div>

          {/* Filters */}
          {showFilters && (
            <div className="mt-4 rounded-lg border border-border bg-card p-4">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                <div className="flex items-center gap-4 flex-1">
                  <span className="text-sm font-medium text-foreground whitespace-nowrap">
                    Min Relevance:
                  </span>
                  <Slider
                    value={[threshold * 100]}
                    onValueChange={(value) => setThreshold(value[0] / 100)}
                    max={100}
                    step={5}
                    className="w-32 sm:w-48"
                  />
                  <span className="w-12 text-sm text-muted-foreground">
                    {(threshold * 100).toFixed(0)}%
                  </span>
                </div>
                
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium text-foreground whitespace-nowrap">Sort By:</span>
                  <select 
                    className="h-9 rounded-md border border-input bg-transparent px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as any)}
                  >
                    <option value="relevance">Relevance</option>
                    <option value="filename">Filename</option>
                    <option value="size">Size</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      <main className="mx-auto max-w-[1200px] px-4 py-6 md:px-6 lg:px-12">
        {/* Results Stats */}
        {results && (
          <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
            <Search className="h-4 w-4" />
            Found {results.results_count} result{results.results_count !== 1 ? 's' : ''} 
            {' '}in {results.search_time_ms}ms
          </div>
        )}

        {error && (
            <div className="mb-6">
                <ErrorBoundary error={error} onRetry={() => performSearch(query)} />
            </div>
        )}

        {/* Loading Skeletons */}
        {isLoading && (
            <div className="mb-6">
                <ResultSkeleton />
            </div>
        )}

        {/* Results List */}
        {!isLoading && sortedResults.length > 0 && (
          <div className="space-y-4">
            {sortedResults.slice(0, displayCount).map((result) => (
              <ResultCard
                key={result.doc_id}
                result={result}
                query={query}
                onClick={() => setSelectedResult(result)}
              />
            ))}
            
            {displayCount < sortedResults.length && (
              <div className="pt-6 flex justify-center">
                  <Button 
                      variant="outline" 
                      onClick={() => setDisplayCount(prev => prev + 10)}
                  >
                      Load More Results
                  </Button>
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && results && results.results.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <FileSearch className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-foreground">
              No results found
            </h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Try adjusting your search terms or lowering the relevance threshold.
            </p>
          </div>
        )}

        {/* Initial State */}
        {!results && !isLoading && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <Search className="h-8 w-8 text-primary" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-foreground">
              Ready to Search
            </h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Enter a search query to find documents. Use quotes for phrase search,
              e.g., &quot;machine learning&quot;
            </p>
          </div>
        )}
      </main>

      {/* Result Detail Modal */}
      <ResultModal
        result={selectedResult}
        query={query}
        onClose={() => setSelectedResult(null)}
      />
    </div>
  )
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
