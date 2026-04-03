'use client'

import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { SearchResult } from '@/lib/types'
import { cn } from '@/lib/utils'
import { 
  File, 
  Copy, 
  Check, 
  ExternalLink, 
  Calendar, 
  FileText,
  Hash
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

function highlightMatches(text: string, query: string): React.ReactNode[] {
  if (!query.trim()) return [text]
  
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  const regex = new RegExp(`(${words.join('|')})`, 'gi')
  const parts = text.split(regex)
  
  return parts.map((part, index) => {
    const isMatch = words.some(word => 
      part.toLowerCase() === word.toLowerCase()
    )
    
    if (isMatch) {
      return (
        <mark 
          key={index} 
          className="bg-primary/20 text-primary font-medium rounded px-0.5"
        >
          {part}
        </mark>
      )
    }
    
    return part
  })
}

export function ResultModal({ result, query, onClose }: ResultModalProps) {
  const [copied, setCopied] = useState(false)

  const handleCopyPath = async () => {
    if (result) {
      await navigator.clipboard.writeText(result.path)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (!result) return null

  const scoreVariant = getScoreVariant(result.score)

  return (
    <Dialog open={!!result} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-muted">
              <File className="h-6 w-6 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <DialogTitle className="text-xl">
                {result.filename}
              </DialogTitle>
              <div className="mt-1 flex items-center gap-2">
                <p className="truncate font-mono text-sm text-muted-foreground">
                  {result.path}
                </p>
                <button
                  onClick={handleCopyPath}
                  className="shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  title="Copy path"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-[#22C55E]" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </DialogHeader>

        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg bg-muted/50 p-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Badge 
                className={cn(
                  'h-5 px-2',
                  scoreVariant === 'success' && 'bg-[#22C55E] text-white border-[#22C55E]',
                  scoreVariant === 'warning' && 'bg-[#F59E0B] text-white border-[#F59E0B]',
                  scoreVariant === 'destructive' && 'bg-[#EF4444] text-white border-[#EF4444]'
                )}
              >
                {(result.score * 100).toFixed(0)}%
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Relevance</p>
          </div>

          {result.word_count && (
            <div className="rounded-lg bg-muted/50 p-3">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="font-semibold text-foreground">
                  {result.word_count.toLocaleString()}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Words</p>
            </div>
          )}

          {result.file_size && (
            <div className="rounded-lg bg-muted/50 p-3">
              <div className="flex items-center gap-2">
                <File className="h-4 w-4 text-muted-foreground" />
                <span className="font-semibold text-foreground">
                  {result.file_size}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Size</p>
            </div>
          )}

          <div className="rounded-lg bg-muted/50 p-3">
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4 text-muted-foreground" />
              <span className="font-semibold text-foreground">
                {result.matched_positions.length}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Matches</p>
          </div>
        </div>

        {/* Indexed Date */}
        {result.indexed_at && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="h-4 w-4" />
            <span>
              Indexed on {new Date(result.indexed_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        )}

        {/* Snippet */}
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-foreground">
            Document Excerpt
          </h4>
          <p className="text-sm leading-relaxed text-foreground">
            {highlightMatches(result.snippet, query)}
          </p>
        </div>

        {/* Match Positions */}
        <div>
          <h4 className="mb-2 text-sm font-semibold text-foreground">
            Match Positions
          </h4>
          <div className="flex flex-wrap gap-2">
            {result.matched_positions.map((pos, index) => (
              <span
                key={index}
                className="rounded bg-primary/10 px-2 py-1 font-mono text-xs text-primary"
              >
                Position {pos}
              </span>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button variant="outline" className="flex-1" onClick={handleCopyPath}>
            <Copy className="mr-2 h-4 w-4" />
            {copied ? 'Copied!' : 'Copy Path'}
          </Button>
          <Button className="flex-1" asChild>
            <a href={result.path} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />
              View File
            </a>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
