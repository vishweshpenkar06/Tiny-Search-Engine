import type { SearchResponse, IndexStatus, IndexResponse } from './types'
import { config } from './config'

// Use actual API endpoint
const API_URL = config.apiUrl

// Simple caching implementation
const CACHE_TTL = 5 * 60 * 1000 // 5 minutes
const responseCache = new Map<string, { data: SearchResponse, timestamp: number }>()

// Track pending requests for deduplication
const pendingRequests = new Map<string, Promise<SearchResponse>>()

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_URL}/api/health`, {
      method: 'GET',
    })
    return res.ok
  } catch (error) {
    return false
  }
}

async function fetchSearchFromAPI(query: string, topK: number, threshold: number): Promise<SearchResponse> {
  const url = `${API_URL}/api/search`
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      top_k: topK,
      threshold
    })
  })

  // Provide more context on errors
  if (!response.ok) {
    let errorMessage = `Search API returned ${response.status} ${response.statusText}`
    try {
      const errorData = await response.json()
      if (errorData.error) {
        errorMessage = errorData.error
      }
    } catch {
      // Ignoring json parsing error if the response is not json
    }
    throw new Error(errorMessage)
  }

  return await response.json()
}

export async function search(
  query: string,
  topK: number = 10,
  threshold: number = 0
): Promise<SearchResponse> {
  if (!query || query.trim() === '') {
    return {
      query,
      results_count: 0,
      search_time_ms: 0,
      results: []
    }
  }

  const sanitizedQuery = query.trim()
  
  // Create cache key based on search parameters
  const cacheKey = `${sanitizedQuery}_${topK}_${threshold}`
  
  // Check memory cache first
  const cachedResponse = responseCache.get(cacheKey)
  if (cachedResponse && (Date.now() - cachedResponse.timestamp) < CACHE_TTL) {
    return cachedResponse.data
  }

  // Deduplicate ongoing requests
  if (pendingRequests.has(cacheKey)) {
    return pendingRequests.get(cacheKey)!
  }

  // Define the request promise
  const requestPromise = (async () => {
    try {
      // For fallback - check health
      const isBackendHealthy = await checkBackendHealth()
      if (!isBackendHealthy) {
        throw new Error('Backend is offline. Please start the Python Flask server on port 5000.')
      }

      const result = await fetchSearchFromAPI(sanitizedQuery, topK, threshold)
      
      // Save to cache
      responseCache.set(cacheKey, { 
        data: result, 
        timestamp: Date.now() 
      })
      
      return result
    } finally {
      // Always remove from pending once complete
      pendingRequests.delete(cacheKey)
    }
  })()

  // Track request
  pendingRequests.set(cacheKey, requestPromise)
  
  return requestPromise
}

export async function uploadFiles(files: File[]): Promise<{ folder_path: string, file_count: number }> {
    const isBackendHealthy = await checkBackendHealth()
    if (!isBackendHealthy) {
        throw new Error('Backend is offline. Please start the Python Flask server on port 5000.')
    }

    const formData = new FormData()
    files.forEach(file => {
        formData.append('files', file)
    })

    const response = await fetch(`${API_URL}/api/upload`, {
        method: 'POST',
        body: formData
    })

    if (!response.ok) {
        let errorMsg = 'Failed to upload files'
        try {
            const errorData = await response.json()
            if (errorData.error) errorMsg = errorData.error
        } catch {}
        throw new Error(errorMsg)
    }

    return await response.json()
}

export async function startIndexing(folderPath: string): Promise<IndexResponse> {
  const isBackendHealthy = await checkBackendHealth()
  if (!isBackendHealthy) {
    throw new Error('Backend is offline. Please start the Python Flask server on port 5000.')
  }

  const response = await fetch(`${API_URL}/api/index`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({ folder_path: folderPath })
  })

  if (!response.ok) {
     let errorMsg = 'Failed to start indexing'
     try {
         const errorData = await response.json()
         if (errorData.error) errorMsg = errorData.error
     } catch {}
     throw new Error(errorMsg)
  }

  return await response.json()
}

export async function getIndexStatus(): Promise<IndexStatus> {
  const response = await fetch(`${API_URL}/api/index/status`)
  
  if (!response.ok) {
     throw new Error('Failed to fetch status')
  }

  return await response.json()
}

export async function cancelIndexing(): Promise<void> {
  await fetch(`${API_URL}/api/index/cancel`, {
    method: 'POST'
  })
}
