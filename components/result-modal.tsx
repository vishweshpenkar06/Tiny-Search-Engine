'use client'

import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { SearchResult } from '@/lib/types'
import { cn } from '@/lib/utils'
import { formatBytes } from '@/lib/format'
import { getDocument, getDocumentUrl } from '@/lib/api'
import { exportAsJSON, exportAsCSV } from '@/lib/export'
import {
  File,
  Copy,
  Check,
  Download,
  ExternalLink,
  Calendar,
  FileText,
  Hash,
} from 'lucide-react'

interface ResultModalProps {
  result: SearchResult | null
  query: string
  onClose: () => void
}

function getScoreVariant(score: number): 'success' | 'warning' | 'destructive' {
  if (score >= 0.8) return 'success'
  if (score >= 0.6) return 'warning'
  return 'destructive'
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function highlightMatches(text: string, query: string): React.ReactNode[] {
  const words = query.trim().split(/\s+/).filter(Boolean).map((word) => escapeRegExp(word.replace(/^"|"$/g, '')))
  if (words.length === 0) return [text]
  const lowered = new Set(words.map((word) => word.toLowerCase()))
  const regex = new RegExp(`(${words.join('|')})`, 'gi')

  return text.split(regex).map((part, index) => (
    lowered.has(part.toLowerCase())
      ? <mark key={index} className="rounded bg-primary/20 px-0.5 font-medium text-primary">{part}</mark>
      : part
  ))
}

function formatExplanationValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function formatIndexedAt(value: string): string {
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

export function ResultModal({ result, query, onClose }: ResultModalProps) {
  const [documentState, setDocumentState] = useState<{
    docId: string
    text: string | null
    error: string | null
  }>({ docId: '', text: null, error: null })
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle')
  const docId = result?.doc_id ?? null

  useEffect(() => {
    if (!docId) return
    const controller = new AbortController()
    getDocument(docId, { signal: controller.signal })
      .then((text) => setDocumentState({ docId, text, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setDocumentState({ docId, text: null, error: error instanceof Error ? error.message : 'Could not load the document.' })
        }
      })
    return () => controller.abort()
  }, [docId])

  if (!result) return null

  const activeDocument = documentState.docId === docId ? documentState : null
  const documentText = activeDocument?.text ?? null
  const documentError = activeDocument?.error ?? null

  const scoreVariant = getScoreVariant(result.score)
  const documentUrl = getDocumentUrl(result.doc_id)
  const copyTarget = result.source_url ?? documentUrl
  const shownPositions = result.matched_positions.slice(0, 20)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(copyTarget)
      setCopyState('copied')
    } catch {
      setCopyState('error')
    }
  }

  return (
    <Dialog open={!!result} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader className="min-w-0">
          <div className="flex min-w-0 items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-muted">
              <File className="h-6 w-6 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <DialogTitle className="break-words text-xl">{result.filename}</DialogTitle>
              <DialogDescription className="sr-only">Document details and ranking explanation</DialogDescription>
              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                {result.source_type} · {result.doc_id}
              </p>
            </div>
          </div>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="min-w-0 rounded-lg bg-muted/50 p-3">
            <div className="flex items-center gap-2">
              <Badge
                className={cn(
                  'h-5 px-2',
                  scoreVariant === 'success' && 'border-[#22C55E] bg-[#22C55E] text-white',
                  scoreVariant === 'warning' && 'border-[#F59E0B] bg-[#F59E0B] text-white',
                  scoreVariant === 'destructive' && 'border-[#EF4444] bg-[#EF4444] text-white',
                )}
              >
                {(result.score * 100).toFixed(0)}%
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Relevance</p>
          </div>

          <div className="min-w-0 rounded-lg bg-muted/50 p-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate font-semibold text-foreground">{result.word_count.toLocaleString()}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Words</p>
          </div>

          <div className="min-w-0 rounded-lg bg-muted/50 p-3">
            <div className="flex items-center gap-2">
              <File className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate font-semibold text-foreground">{formatBytes(result.file_size_bytes)}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Size</p>
          </div>

          <div className="min-w-0 rounded-lg bg-muted/50 p-3">
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate font-semibold text-foreground">{result.total_matches}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Total matches</p>
          </div>
        </div>

        <div className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="h-4 w-4 shrink-0" />
          <span className="min-w-0 break-words">Indexed on {formatIndexedAt(result.indexed_at)}</span>
        </div>

        <div className="min-w-0 rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-foreground">Document excerpt</h4>
          <p className="break-words text-sm leading-relaxed text-foreground">
            {highlightMatches(result.snippet, query)}
          </p>
        </div>

        <details className="min-w-0 rounded-lg border border-border bg-muted/30 p-4">
          <summary className="cursor-pointer text-sm font-semibold text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
            Ranking explanation
          </summary>
          <div className="mt-3 space-y-1">
            {Object.entries(result.explanation).map(([key, value]) => (
              <div key={key} className="flex min-w-0 flex-wrap gap-2 text-xs">
                <span className="shrink-0 font-medium text-muted-foreground">{key}:</span>
                <span className="min-w-0 break-words text-foreground">{formatExplanationValue(value)}</span>
              </div>
            ))}
            {Object.keys(result.explanation).length === 0 && (
              <p className="text-xs text-muted-foreground">No explanation available.</p>
            )}
            <p className="text-xs text-muted-foreground">
              Normalized score {(result.score * 100).toFixed(0)}% · raw score {result.raw_score.toFixed(3)}
            </p>
          </div>
        </details>

        <div className="min-w-0">
          <h4 className="mb-2 text-sm font-semibold text-foreground">Match positions</h4>
          <div className="flex flex-wrap gap-2">
            {shownPositions.map((position, index) => (
              <span key={index} className="rounded bg-primary/10 px-2 py-1 font-mono text-xs text-primary">
                {position}
              </span>
            ))}
            {result.matched_positions.length === 0 && (
              <span className="text-xs text-muted-foreground">No positions recorded.</span>
            )}
            {result.matched_positions.length > shownPositions.length && (
              <span className="text-xs text-muted-foreground">
                +{result.matched_positions.length - shownPositions.length} more
              </span>
            )}
          </div>
        </div>

        <div className="min-w-0">
          <h4 className="mb-2 text-sm font-semibold text-foreground">Document content</h4>
          {documentText === null && !documentError && (
            <p className="text-sm text-muted-foreground" role="status">Loading document…</p>
          )}
          {documentError && (
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-900/10 dark:text-red-300">
              {documentError}
            </div>
          )}
          {documentText !== null && (
            <pre className="max-h-64 min-w-0 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/30 p-4 text-xs leading-relaxed text-foreground">
              {documentText}
            </pre>
          )}
        </div>

        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            variant="outline"
            aria-label={result.source_url ? 'Copy source URL' : 'Copy document link'}
            className="min-w-0 flex-1 focus-visible:ring-2 focus-visible:ring-ring"
            onClick={handleCopy}
          >
            {copyState === 'copied' ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
            {copyState === 'copied' ? 'Copied' : 'Copy link'}
          </Button>
          <Button type="button" variant="outline" className="focus-visible:ring-2 focus-visible:ring-ring" onClick={() => exportAsJSON([result])}>
            <Download className="mr-2 h-4 w-4" />
            JSON
          </Button>
          <Button type="button" variant="outline" className="focus-visible:ring-2 focus-visible:ring-ring" onClick={() => exportAsCSV([result])}>
            <Download className="mr-2 h-4 w-4" />
            CSV
          </Button>
          <Button type="button" asChild className="focus-visible:ring-2 focus-visible:ring-ring">
            <a href={documentUrl} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />
              Open document
            </a>
          </Button>
          {result.source_url && (
            <Button type="button" variant="ghost" asChild className="focus-visible:ring-2 focus-visible:ring-ring">
              <a href={result.source_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                View source
              </a>
            </Button>
          )}
        </div>

        <p role="status" aria-live="polite" className="min-h-4 text-xs text-muted-foreground">
          {copyState === 'error' ? 'Copy failed. Open the link and copy it from the address bar.' : ''}
        </p>
      </DialogContent>
    </Dialog>
  )
}
