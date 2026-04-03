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
import { Search, SlidersHorizontal, FileSearch } from 'lucide-react'

function SearchContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [threshold, setThreshold] = useState(0)

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults(null)
      return
    }

    setIsLoading(true)
    try {
      const data = await search(searchQuery, 10, threshold)
      setResults(data)
      
      // Save to recent searches
      const saved = localStorage.getItem('recentSearches')
      const recent: string[] = saved ? JSON.parse(saved) : []
      const updated = [searchQuery, ...recent.filter(s => s !== searchQuery)].slice(0, 5)
      localStorage.setItem('recentSearches', JSON.stringify(updated))
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setIsLoading(false)
    }
  }, [threshold])

  useEffect(() => {
    const initialQuery = searchParams.get('q')
    if (initialQuery) {
      setQuery(initialQuery)
      performSearch(initialQuery)
    }
  }, [searchParams, performSearch])

  const handleSearch = (value: string) => {
    router.push(`/search?q=${encodeURIComponent(value)}`, { scroll: false })
    performSearch(value)
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
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-foreground">
                  Min Relevance:
                </span>
                <Slider
                  value={[threshold * 100]}
                  onValueChange={(value) => setThreshold(value[0] / 100)}
                  max={100}
                  step={5}
                  className="w-48"
                />
                <span className="w-12 text-sm text-muted-foreground">
                  {(threshold * 100).toFixed(0)}%
                </span>
                <Button
                  size="sm"
                  onClick={() => performSearch(query)}
                  disabled={isLoading}
                >
                  Apply
                </Button>
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

        {/* Results List */}
        {results && results.results.length > 0 && (
          <div className="space-y-4">
            {results.results.map((result) => (
              <ResultCard
                key={result.doc_id}
                result={result}
                query={query}
                onClick={() => setSelectedResult(result)}
              />
            ))}
          </div>
        )}

        {/* Empty State */}
        {results && results.results.length === 0 && (
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
