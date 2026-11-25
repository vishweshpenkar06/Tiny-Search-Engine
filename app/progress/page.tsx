'use client'

import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Header } from '@/components/header'
import { ProgressCircle } from '@/components/progress-circle'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cancelIndexing, getIndexStatus } from '@/lib/api'
import type { IndexStatus } from '@/lib/types'
import { formatDate } from '@/lib/format'
import { Clock, FileText, CheckCircle, XCircle, AlertCircle, Ban } from 'lucide-react'

const POLL_INTERVAL_MS = 1000
const TERMINAL_STATUSES = new Set([
  'complete',
  'completed',
  'failed',
  'error',
  'cancelled',
  'canceled',
  'interrupted',
])
const SUCCESS_STATUSES = new Set(['complete', 'completed'])

function normalizeProgress(value: number): number {
  if (!Number.isFinite(value)) return 0
  if (value >= 0 && value <= 1) return value * 100
  return Math.min(100, Math.max(0, value))
}

function ProgressContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const jobId = searchParams.get('jobId') || searchParams.get('job_id') || ''

  const [status, setStatus] = useState<IndexStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isCancelling, setIsCancelling] = useState(false)

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const redirectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inFlightRef = useRef(false)
  const activeRef = useRef(true)
  const terminalRef = useRef(false)
  const pollRef = useRef<() => void>(() => undefined)

  const poll = useCallback(async () => {
    if (!jobId || inFlightRef.current || terminalRef.current || !activeRef.current) return
    inFlightRef.current = true

    try {
      const data = await getIndexStatus(jobId, { timeoutMs: 10000 })
      if (!activeRef.current) return
      setStatus(data)
      setError(null)

      const normalized = data.status.toLowerCase()
      if (TERMINAL_STATUSES.has(normalized)) {
        terminalRef.current = true
        if (timerRef.current) {
          clearTimeout(timerRef.current)
          timerRef.current = null
        }
        if (SUCCESS_STATUSES.has(normalized) && !redirectRef.current) {
          redirectRef.current = setTimeout(() => {
            if (activeRef.current) router.push('/search')
          }, 1500)
        }
        return
      }
    } catch (err) {
      if (!activeRef.current) return
      setError(err instanceof Error ? err.message : 'Could not check indexing status.')
    } finally {
      inFlightRef.current = false
      if (activeRef.current && !terminalRef.current && jobId && timerRef.current === null) {
        timerRef.current = setTimeout(() => {
          timerRef.current = null
          pollRef.current()
        }, POLL_INTERVAL_MS)
      }
    }
  }, [jobId, router])

  useEffect(() => {
    activeRef.current = true
    terminalRef.current = false
    pollRef.current = () => { void poll() }

    if (!jobId) return

    void poll()

    return () => {
      activeRef.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
      if (redirectRef.current) clearTimeout(redirectRef.current)
      timerRef.current = null
      redirectRef.current = null
    }
  }, [jobId, poll])

  const handleCancel = async () => {
    if (!jobId || isCancelling) return
    setIsCancelling(true)
    setError(null)
    try {
      await cancelIndexing(jobId)
      terminalRef.current = true
      if (timerRef.current) clearTimeout(timerRef.current)
      if (redirectRef.current) clearTimeout(redirectRef.current)
      router.push('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel indexing.')
      setIsCancelling(false)
    }
  }

  const normalizedStatus = status?.status.toLowerCase() ?? ''
  const isSuccess = SUCCESS_STATUSES.has(normalizedStatus)
  const isCancelled = normalizedStatus === 'cancelled' || normalizedStatus === 'canceled' || normalizedStatus === 'interrupted'
  const isFailed = !isSuccess && !isCancelled && (
    normalizedStatus === 'error' || normalizedStatus === 'failed' || Boolean(status?.error)
  )
  const isTerminal = isSuccess || isCancelled || isFailed
  const progress = status ? normalizeProgress(status.progress) : 0
  const displayError = error ?? (jobId ? null : 'Missing job id. Start indexing from the home page.')

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="mx-auto flex min-h-[calc(100vh-64px)] max-w-[1200px] flex-col items-center justify-center px-4 py-12 md:px-6 lg:px-12">
        <Card className="w-full max-w-md border-border bg-card">
          <CardContent className="flex flex-col items-center p-8">
            <ProgressCircle value={progress} />

            <div role="status" aria-live="polite" className="mt-8 min-h-6 text-center">
              {isSuccess ? (
                <>
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#22C55E]/10">
                    <CheckCircle className="h-6 w-6 text-[#22C55E]" />
                  </div>
                  <h2 className="mt-4 text-xl font-semibold text-foreground">Indexing Complete</h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {status?.succeeded ?? 0} document(s) indexed. Redirecting to search…
                  </p>
                </>
              ) : isCancelled ? (
                <>
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                    <Ban className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <h2 className="mt-4 text-xl font-semibold text-foreground">Indexing Stopped</h2>
                  <p className="mt-2 break-words text-sm text-muted-foreground">
                    {status?.error ?? 'The job was cancelled or interrupted.'}
                  </p>
                </>
              ) : isFailed ? (
                <>
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
                    <XCircle className="h-6 w-6 text-destructive" />
                  </div>
                  <h2 className="mt-4 text-xl font-semibold text-foreground">Indexing Failed</h2>
                  <p className="mt-2 break-words text-sm text-muted-foreground">
                    {status?.error ?? 'An error occurred during indexing.'}
                  </p>
                </>
              ) : (
                <>
                  <h2 className="text-xl font-semibold text-foreground">Indexing Documents</h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Building the inverted index with BM25 statistics…
                  </p>
                </>
              )}
            </div>

            {displayError && (
              <div role="alert" className="mt-6 flex w-full items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900/50 dark:bg-red-900/10">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-500" />
                <div className="min-w-0 flex-1">
                  <p className="break-words text-sm text-red-800 dark:text-red-300">{displayError}</p>
                  {jobId && (
                    <button
                      type="button"
                      onClick={() => { setError(null); pollRef.current() }}
                      className="mt-1 text-xs text-red-700 underline hover:text-red-900 focus-visible:ring-2 focus-visible:ring-ring dark:text-red-300"
                    >
                      Retry
                    </button>
                  )}
                </div>
              </div>
            )}

            <div className="mt-8 grid w-full grid-cols-2 gap-4">
              <div className="flex min-w-0 items-center gap-3 rounded-lg bg-muted/50 p-3">
                <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">Processed</p>
                  <p className="truncate font-semibold text-foreground">
                    {status?.processed ?? 0} ({status?.succeeded ?? 0} ok, {status?.skipped ?? 0} skipped, {status?.failed ?? 0} failed)
                  </p>
                </div>
              </div>

              <div className="flex min-w-0 items-center gap-3 rounded-lg bg-muted/50 p-3">
                <Clock className="h-5 w-5 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">Updated</p>
                  <p className="truncate font-semibold text-foreground">
                    {status?.updated_at ? formatDate(status.updated_at) : 'Waiting…'}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4 w-full min-w-0 space-y-1 text-xs text-muted-foreground">
              <p className="break-words">Job: {jobId || 'missing'}</p>
              <p className="break-words">Generation: {status?.generation ?? '—'}</p>
              <p className="break-words">Created: {status?.created_at ? formatDate(status.created_at) : '—'}</p>
              <p className="break-words">Finished: {status?.finished_at ? formatDate(status.finished_at) : '—'}</p>
            </div>

            <div className="mt-8 flex w-full gap-3">
              {isSuccess ? (
                <Button className="w-full focus-visible:ring-2 focus-visible:ring-ring" size="lg" onClick={() => router.push('/search')}>
                  Start Searching
                </Button>
              ) : isTerminal ? (
                <Button className="w-full focus-visible:ring-2 focus-visible:ring-ring" size="lg" onClick={() => router.push('/')}>
                  Back to Upload
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="destructive"
                  className="w-full focus-visible:ring-2 focus-visible:ring-ring"
                  size="lg"
                  onClick={() => void handleCancel()}
                  disabled={isCancelling || !jobId}
                >
                  {isCancelling ? 'Cancelling…' : 'Cancel'}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

export default function ProgressPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background">
        <Header />
        <div className="flex items-center justify-center py-32">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      </div>
    }>
      <ProgressContent />
    </Suspense>
  )
}
