'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Header } from '@/components/header'
import { UploadZone } from '@/components/upload-zone'
import { Card, CardContent } from '@/components/ui/card'
import { Search, Zap, FileText, Clock, AlertCircle } from 'lucide-react'
import { getConfig, startIndexing, uploadFiles } from '@/lib/api'
import { readRecentSearches } from '@/lib/search-state'
import type { PublicConfig } from '@/lib/types'

const SAMPLE_FILES = [
  { name: 'ai.txt', content: 'Machine learning is a field of study in AI.\n' },
  { name: 'fox.txt', content: 'The quick brown fox jumps over the lazy dog.\n' },
  { name: 'web.md', content: 'React and Next.js are great frontend frameworks.\n' },
]

function createSampleFiles(): File[] {
  return SAMPLE_FILES.map((sample) => new File(
    [sample.content],
    sample.name,
    { type: sample.name.endsWith('.md') ? 'text/markdown' : 'text/plain' },
  ))
}

export default function HomePage() {
  const router = useRouter()
  const [isStarting, setIsStarting] = useState(false)
  const [recentSearches] = useState<string[]>(() => readRecentSearches())
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [limits, setLimits] = useState<Partial<PublicConfig>>()

  useEffect(() => {
    let active = true
    getConfig()
      .then((data) => {
        if (!active) return
        setLimits({
          allowed_extensions: data.allowed_extensions,
          max_file_size: data.max_file_size,
          max_files: data.max_files,
        })
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [])

  const handleFilesSelected = useCallback(async (files: File[]) => {
    setIsStarting(true)
    setError(null)
    setNotice(null)
    try {
      const upload = await uploadFiles(files)
      if (upload.rejected.length > 0) {
        setNotice(`${upload.rejected.length} file(s) were rejected by the server.`)
      }
      const job = await startIndexing(upload.upload_id, 'bm25')
      router.push(`/progress?jobId=${encodeURIComponent(job.job_id)}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start indexing')
      setIsStarting(false)
    }
  }, [router])

  const handleDemoMode = useCallback(() => {
    void handleFilesSelected(createSampleFiles())
  }, [handleFilesSelected])

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="mx-auto max-w-[1200px] px-4 py-12 md:px-6 lg:px-12">
        <div className="mb-12 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Search Your Documents
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            A search engine built from scratch. Index your documents and search with
            BM25 and TF-IDF ranking across lexical, semantic, and hybrid modes.
          </p>
        </div>

        <div className="mx-auto max-w-2xl">
          {error && (
            <div role="alert" className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900/50 dark:bg-red-900/10">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-500" />
              <div className="min-w-0 flex-1">
                <p className="break-words text-sm font-medium text-red-900 dark:text-red-400">{error}</p>
                <button
                  type="button"
                  onClick={() => setError(null)}
                  className="mt-1 text-xs text-red-700 underline hover:text-red-900 focus-visible:ring-2 focus-visible:ring-ring dark:text-red-300"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {notice && (
            <div role="status" className="mb-4 break-words rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-900/10 dark:text-amber-300">
              {notice}
            </div>
          )}

          <UploadZone
            onFilesSelected={handleFilesSelected}
            isUploading={isStarting}
            limits={limits}
          />

          <div className="mt-6 text-center">
            <button
              type="button"
              onClick={handleDemoMode}
              disabled={isStarting}
              className="text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              {isStarting ? 'Indexing sample documents...' : 'Or try with sample documents'}
            </button>
            <p className="mt-1 text-xs text-muted-foreground">
              Uploads ai.txt, fox.txt, and web.md from the bundled samples through the API.
            </p>
          </div>
        </div>

        {recentSearches.length > 0 && (
          <div className="mx-auto mt-12 max-w-2xl">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
              <Clock className="h-5 w-5 text-muted-foreground" />
              Recent Searches
            </h2>
            <div className="flex flex-wrap gap-2">
              {recentSearches.map((search, index) => (
                <Link
                  key={`${search}-${index}`}
                  href={`/search?q=${encodeURIComponent(search)}`}
                  className="max-w-full truncate rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {search}
                </Link>
              ))}
            </div>
          </div>
        )}

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
                <h3 className="mt-4 font-semibold text-foreground">Upload Documents</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Drag and drop text, markdown, or HTML documents to build an index.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border bg-card">
              <CardContent className="flex flex-col items-center p-6 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <Zap className="h-6 w-6 text-primary" />
                </div>
                <h3 className="mt-4 font-semibold text-foreground">Fast Indexing</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  An inverted index stores term positions and BM25 statistics for each document.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border bg-card">
              <CardContent className="flex flex-col items-center p-6 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <Search className="h-6 w-6 text-primary" />
                </div>
                <h3 className="mt-4 font-semibold text-foreground">Smart Search</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  BM25 relevance scoring ranks results, with filters and explanations for every match.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

        <footer className="mt-16 border-t border-border pt-8 text-center">
          <p className="text-sm text-muted-foreground">
            Built to demonstrate data structures, algorithms, and systems design.
          </p>
        </footer>
      </main>
    </div>
  )
}
