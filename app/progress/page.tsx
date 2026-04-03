'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/header'
import { ProgressCircle } from '@/components/progress-circle'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { getIndexStatus, cancelIndexing } from '@/lib/api'
import type { IndexStatus } from '@/lib/types'
import { Clock, FileText, CheckCircle, XCircle, File } from 'lucide-react'

export default function ProgressPage() {
  const router = useRouter()
  const [status, setStatus] = useState<IndexStatus>({
    status: 'indexing',
    progress: 0,
    files_indexed: 0,
    total_files: 0,
    elapsed_time: '0s',
    estimated_remaining: 'Calculating...',
  })
  const [isCancelling, setIsCancelling] = useState(false)

  const pollStatus = useCallback(async () => {
    try {
      const data = await getIndexStatus()
      setStatus(data)

      if (data.status === 'complete') {
        // Auto-redirect to search after a brief delay
        setTimeout(() => {
          router.push('/search')
        }, 1500)
      }
    } catch (error) {
      console.error('Failed to get status:', error)
    }
  }, [router])

  useEffect(() => {
    // Initial poll
    pollStatus()

    // Poll every 500ms while indexing
    const interval = setInterval(() => {
      if (status.status === 'indexing') {
        pollStatus()
      }
    }, 500)

    return () => clearInterval(interval)
  }, [pollStatus, status.status])

  const handleCancel = async () => {
    setIsCancelling(true)
    try {
      await cancelIndexing()
      router.push('/')
    } catch (error) {
      console.error('Failed to cancel:', error)
      setIsCancelling(false)
    }
  }

  const handleContinue = () => {
    router.push('/search')
  }

  const isComplete = status.status === 'complete'
  const hasError = status.status === 'error'

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="mx-auto flex min-h-[calc(100vh-64px)] max-w-[1200px] flex-col items-center justify-center px-4 py-12 md:px-6 lg:px-12">
        <Card className="w-full max-w-md border-border bg-card">
          <CardContent className="flex flex-col items-center p-8">
            {/* Progress Circle */}
            <ProgressCircle value={status.progress} />

            {/* Status Icon & Text */}
            <div className="mt-8 text-center">
              {isComplete ? (
                <>
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#22C55E]/10">
                    <CheckCircle className="h-6 w-6 text-[#22C55E]" />
                  </div>
                  <h2 className="mt-4 text-xl font-semibold text-foreground">
                    Indexing Complete!
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {status.files_indexed} files have been indexed and are ready to search.
                  </p>
                </>
              ) : hasError ? (
                <>
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
                    <XCircle className="h-6 w-6 text-destructive" />
                  </div>
                  <h2 className="mt-4 text-xl font-semibold text-foreground">
                    Indexing Failed
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {status.error_message || 'An error occurred during indexing.'}
                  </p>
                </>
              ) : (
                <>
                  <h2 className="text-xl font-semibold text-foreground">
                    Indexing Documents
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Building inverted index with TF-IDF scoring...
                  </p>
                </>
              )}
            </div>

            {/* Stats */}
            <div className="mt-8 grid w-full grid-cols-2 gap-4">
              <div className="flex items-center gap-3 rounded-lg bg-muted/50 p-3">
                <FileText className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Files</p>
                  <p className="font-semibold text-foreground">
                    {status.files_indexed} / {status.total_files}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 rounded-lg bg-muted/50 p-3">
                <Clock className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Elapsed</p>
                  <p className="font-semibold text-foreground">
                    {status.elapsed_time}
                  </p>
                </div>
              </div>
            </div>

            {/* Current File */}
            {status.current_file && !isComplete && (
              <div className="mt-4 flex w-full items-center gap-2 rounded-lg bg-muted/50 p-3">
                <File className="h-4 w-4 shrink-0 text-muted-foreground" />
                <p className="truncate text-sm text-muted-foreground">
                  {status.current_file}
                </p>
              </div>
            )}

            {/* ETA */}
            {!isComplete && !hasError && status.estimated_remaining && (
              <p className="mt-4 text-sm text-muted-foreground">
                Estimated time remaining: {status.estimated_remaining}
              </p>
            )}

            {/* Actions */}
            <div className="mt-8 flex w-full gap-3">
              {isComplete ? (
                <Button 
                  className="w-full" 
                  size="lg"
                  onClick={handleContinue}
                >
                  Start Searching
                </Button>
              ) : hasError ? (
                <Button 
                  className="w-full" 
                  size="lg"
                  onClick={() => router.push('/')}
                >
                  Try Again
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  className="w-full"
                  size="lg"
                  onClick={handleCancel}
                  disabled={isCancelling}
                >
                  {isCancelling ? 'Cancelling...' : 'Cancel'}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
