import { useState, useCallback } from 'react'
import { search } from '@/lib/api'
import type { SearchResponse } from '@/lib/types'

export function useSearch() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<SearchResponse | null>(null)

  const performSearch = useCallback(async (query: string, topK: number = 10, threshold: number = 0) => {
    if (!query.trim()) {
      setResults(null)
      setError(null)
      return null
    }

    setIsLoading(true)
    setError(null)

    try {
      const data = await search(query, topK, threshold)
      setResults(data)
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred during search'
      setError(message)
      setResults(null)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { performSearch, results, isLoading, error, setResults, setError }
}
