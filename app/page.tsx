'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/header'
import { UploadZone } from '@/components/upload-zone'
import { Card, CardContent } from '@/components/ui/card'
import { Search, Zap, FileText, Clock, AlertCircle } from 'lucide-react'
import { uploadFiles, startIndexing } from '@/lib/api'
import Link from 'next/link'

export default function HomePage() {
  const router = useRouter()
  const [isStarting, setIsStarting] = useState(false)
  const [recentSearches, setRecentSearches] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem('recentSearches')
    if (saved) {
      setRecentSearches(JSON.parse(saved))
    }
  }, [])

  const handleFilesSelected = async (files: File[]) => {
    setIsStarting(true)
    setError(null)
    try {
      const uploadRes = await uploadFiles(files)
      await startIndexing(uploadRes.folder_path)
      router.push('/progress')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start indexing'
      setError(msg)
      setIsStarting(false)
    }
  }

  // Demo mode - backend is disabled, but UI should simulate
  const handleDemoMode = async () => {
    setIsStarting(true)
    try {
      // Create some dummy file to pass to upload if we want, or just mock it.
      // Easiest is to push to progress directly and rely on mock data later if backend is down.
      // But we can't startIndexing without a valid folder path.
      // Let's just push to progress.
      router.push('/progress')
    } catch (error) {
      console.error('Failed to start demo:', error)
      setIsStarting(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="mx-auto max-w-[1200px] px-4 py-12 md:px-6 lg:px-12">
        {/* Hero Section */}
        <div className="mb-12 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Search Your Documents
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            A functional search engine built from scratch. Index your documents 
            and search with TF-IDF ranking and phrase matching.
          </p>
        </div>

        {/* Upload Section */}
        <div className="mx-auto max-w-2xl">
          {error && (
            <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900/50 dark:bg-red-900/10">
              <AlertCircle className="h-5 w-5 shrink-0 text-red-600 mt-0.5 dark:text-red-500" />
              <div>
                <p className="text-sm font-medium text-red-900 dark:text-red-400">{error}</p>
                <button
                  onClick={() => setError(null)}
                  className="mt-1 text-xs text-red-700 underline hover:text-red-900 dark:text-red-300"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          <UploadZone 
            onFilesSelected={handleFilesSelected}
            isUploading={isStarting}
          />

          {/* Demo Mode Button */}
          <div className="mt-6 text-center">
            <button
              onClick={handleDemoMode}
              disabled={isStarting}
              className="text-sm font-medium text-primary underline-offset-4 hover:underline disabled:opacity-50"
            >
              Or try with sample documents
            </button>
          </div>
        </div>

        {/* Recent Searches */}
        {recentSearches.length > 0 && (
          <div className="mx-auto mt-12 max-w-2xl">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
              <Clock className="h-5 w-5 text-muted-foreground" />
              Recent Searches
            </h2>
            <div className="flex flex-wrap gap-2">
              {recentSearches.map((search, index) => (
                <Link
                  key={index}
                  href={`/search?q=${encodeURIComponent(search)}`}
                  className="rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary hover:bg-primary/5"
                >
                  {search}
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Quick Tips */}
        <div className="mx-auto mt-16 max-w-4xl">
          <h2 className="mb-6 text-center text-lg font-semibold text-foreground">
            How It Works
          </h2>
          <div className="grid gap-6 sm:grid-cols-3">
            <Card className="border-border bg-card">
              <CardContent className="flex flex-col items-center p-6 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <FileText className="h-6 w-6 text-primary" />
                </div>
                <h3 className="mt-4 font-semibold text-foreground">
                  Upload Documents
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Drag and drop your text files, markdown, or HTML documents to build an index.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border bg-card">
              <CardContent className="flex flex-col items-center p-6 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <Zap className="h-6 w-6 text-primary" />
                </div>
                <h3 className="mt-4 font-semibold text-foreground">
                  Fast Indexing
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Our inverted index builds in seconds, tracking word positions for phrase search.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border bg-card">
              <CardContent className="flex flex-col items-center p-6 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <Search className="h-6 w-6 text-primary" />
                </div>
                <h3 className="mt-4 font-semibold text-foreground">
                  Smart Search
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  TF-IDF ranking ensures the most relevant documents appear first in results.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-16 border-t border-border pt-8 text-center">
          <p className="text-sm text-muted-foreground">
            Built to demonstrate data structures, algorithms, and systems design.
          </p>
        </footer>
      </main>
    </div>
  )
}
