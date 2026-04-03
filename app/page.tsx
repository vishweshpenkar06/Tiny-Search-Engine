'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/header'
import { UploadZone } from '@/components/upload-zone'
import { Card, CardContent } from '@/components/ui/card'
import { Search, Zap, FileText, Clock } from 'lucide-react'
import { startIndexing, resetIndexState } from '@/lib/api'
import Link from 'next/link'

export default function HomePage() {
  const router = useRouter()
  const [isStarting, setIsStarting] = useState(false)
  const [recentSearches, setRecentSearches] = useState<string[]>([])

  useEffect(() => {
    // Reset any previous indexing state
    resetIndexState()
    
    // Load recent searches from localStorage
    const saved = localStorage.getItem('recentSearches')
    if (saved) {
      setRecentSearches(JSON.parse(saved))
    }
  }, [])

  const handleFilesSelected = async (files: File[]) => {
    setIsStarting(true)
    try {
      await startIndexing(files.length)
      router.push('/progress')
    } catch (error) {
      console.error('Failed to start indexing:', error)
      setIsStarting(false)
    }
  }

  // Demo mode - start with sample files
  const handleDemoMode = async () => {
    setIsStarting(true)
    try {
      await startIndexing(100) // Simulate 100 files
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
