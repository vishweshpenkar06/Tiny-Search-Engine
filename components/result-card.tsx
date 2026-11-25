'use client'

import { useState } from 'react'
import { File, Copy, Check, Download, ExternalLink, AlertCircle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { SearchResult } from '@/lib/types'
import { cn } from '@/lib/utils'
import { formatBytes } from '@/lib/format'
import { exportAsJSON, exportAsCSV } from '@/lib/export'
import { getDocumentUrl } from '@/lib/api'

interface ResultCardProps {
  result: SearchResult
  query: string
  onClick: () => void
}

function getScoreVariant(score: number): 'success' | 'warning' | 'destructive' {
  if (score >= 0.8) return 'success'
  if (score >= 0.6) return 'warning'
  return 'destructive'
}

function getScoreLabel(score: number): string {
  if (score >= 0.8) return 'High'
  if (score >= 0.6) return 'Medium'
  return 'Low'
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

export function ResultCard({ result, query, onClick }: ResultCardProps) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle')
  const scoreVariant = getScoreVariant(result.score)
  const scoreLabel = getScoreLabel(result.score)
  const copyTarget = result.source_url ?? getDocumentUrl(result.doc_id)
  const shownPositions = result.matched_positions.slice(0, 12)

  const handleCopy = async (event: React.MouseEvent) => {
    event.stopPropagation()
    try {
      await navigator.clipboard.writeText(copyTarget)
      setCopyState('copied')
    } catch {
      setCopyState('error')
    }
  }

  const stopAndRun = (event: React.MouseEvent, action: () => void) => {
    event.stopPropagation()
    action()
  }

  return (
    <Card
      className="min-w-0 cursor-pointer border-border bg-card transition-all duration-200 hover:border-primary/30 hover:shadow-[0_8px_20px_rgba(15,23,42,0.08)]"
      onClick={onClick}
    >
      <CardContent className="relative min-w-0 p-5">
        <div className="flex min-w-0 items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
              <File className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <h3 className="break-words font-semibold text-foreground">{result.filename}</h3>
              <p className="mt-0.5 break-all font-mono text-xs text-muted-foreground">
                {result.source_type} · {result.doc_id}
              </p>
              {result.source_url && (
                <a
                  href={result.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(event) => event.stopPropagation()}
                  className="mt-1 inline-flex max-w-full items-center gap-1 break-all text-xs text-primary hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <ExternalLink className="h-3 w-3 shrink-0" />
                  <span className="truncate">{result.source_url}</span>
                </a>
              )}
            </div>
          </div>

          <div className="flex shrink-0 flex-col items-end gap-2">
            <Badge
              className={cn(
                'shrink-0',
                scoreVariant === 'success' && 'border-[#22C55E] bg-[#22C55E] text-white',
                scoreVariant === 'warning' && 'border-[#F59E0B] bg-[#F59E0B] text-white',
                scoreVariant === 'destructive' && 'border-[#EF4444] bg-[#EF4444] text-white',
              )}
            >
              {scoreLabel} ({(result.score * 100).toFixed(0)}%)
            </Badge>

            <div className="flex flex-wrap items-center justify-end gap-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label="View result details"
                className="h-7 px-2 text-xs focus-visible:ring-2 focus-visible:ring-ring"
                onClick={(event) => stopAndRun(event, onClick)}
              >
                Details
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={result.source_url ? 'Copy source URL' : 'Copy document link'}
                className="h-7 px-2 text-xs focus-visible:ring-2 focus-visible:ring-ring"
                onClick={handleCopy}
              >
                {copyState === 'copied' ? <Check className="mr-1 h-3 w-3" /> : <Copy className="mr-1 h-3 w-3" />}
                {copyState === 'copied' ? 'Copied' : 'Copy'}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label="Export result as JSON"
                className="h-7 px-2 text-xs focus-visible:ring-2 focus-visible:ring-ring"
                onClick={(event) => stopAndRun(event, () => exportAsJSON([result]))}
              >
                <Download className="mr-1 h-3 w-3" />
                JSON
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label="Export result as CSV"
                className="h-7 px-2 text-xs focus-visible:ring-2 focus-visible:ring-ring"
                onClick={(event) => stopAndRun(event, () => exportAsCSV([result]))}
              >
                <Download className="mr-1 h-3 w-3" />
                CSV
              </Button>
            </div>
          </div>
        </div>

        <p role="status" aria-live="polite" className="mt-1 min-h-4 text-xs text-muted-foreground">
          {copyState === 'error' ? 'Copy failed. Use the source URL above.' : ''}
        </p>

        <div className="mt-3 min-w-0">
          <p className="break-words text-sm leading-relaxed text-foreground">
            {highlightMatches(result.snippet, query)}
          </p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>{result.total_matches} total matches</span>
          <span>{shownPositions.length > 0 ? `Positions: ${shownPositions.join(', ')}` : 'No positions'}</span>
          <span>{result.word_count.toLocaleString()} words</span>
          <span>{formatBytes(result.file_size_bytes)}</span>
        </div>

        <details className="mt-3 min-w-0 rounded-lg border border-border bg-muted/30 p-3">
          <summary className="cursor-pointer text-xs font-medium text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
            Ranking explanation
          </summary>
          <div className="mt-2 space-y-1">
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

        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              'h-full transition-all duration-300',
              scoreVariant === 'success' && 'bg-[#22C55E]',
              scoreVariant === 'warning' && 'bg-[#F59E0B]',
              scoreVariant === 'destructive' && 'bg-[#EF4444]',
            )}
            style={{ width: `${Math.min(100, Math.max(0, result.score * 100))}%` }}
          />
        </div>

        {copyState === 'error' && (
          <p className="sr-only" role="alert">
            <AlertCircle className="h-4 w-4" />
            Copy failed
          </p>
        )}
      </CardContent>
    </Card>
  )
}
