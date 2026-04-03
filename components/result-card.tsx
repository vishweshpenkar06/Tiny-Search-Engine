'use client'

import { File } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { SearchResult } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Copy, Download } from 'lucide-react'
import { exportAsJSON, exportAsCSV } from '@/lib/export'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

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

export function ResultCard({ result, query, onClick }: ResultCardProps) {
  const scoreVariant = getScoreVariant(result.score)
  const scoreLabel = getScoreLabel(result.score)
  const [copied, setCopied] = useState(false)

  const handleCopyPath = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(result.path)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExportJSON = (e: React.MouseEvent) => {
    e.stopPropagation()
    exportAsJSON([result])
  }

  const handleExportCSV = (e: React.MouseEvent) => {
    e.stopPropagation()
    exportAsCSV([result])
  }

  return (
    <Card 
      className="cursor-pointer border-border bg-card transition-all duration-200 hover:border-primary/30 hover:shadow-[0_8px_20px_rgba(15,23,42,0.08)]"
      onClick={onClick}
    >
      <CardContent className="p-5 relative group">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
              <File className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">
                {result.filename}
              </h3>
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                {result.path}
              </p>
            </div>
          </div>
          
          <div className="flex flex-col items-end gap-2">
            <Badge 
              className={cn(
                'shrink-0',
                scoreVariant === 'success' && 'bg-[#22C55E] text-white border-[#22C55E]',
                scoreVariant === 'warning' && 'bg-[#F59E0B] text-white border-[#F59E0B]',
                scoreVariant === 'destructive' && 'bg-[#EF4444] text-white border-[#EF4444]'
              )}
            >
              {scoreLabel} ({(result.score * 100).toFixed(0)}%)
            </Badge>

            {/* Quick Actions - visible on hover */}
            <div className="hidden group-hover:flex items-center gap-1">
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-7 px-2 text-xs" 
                onClick={handleCopyPath}
              >
                <Copy className="mr-1 h-3 w-3" />
                {copied ? 'Copied' : 'Path'}
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-7 px-2 text-xs" 
                onClick={handleExportJSON}
              >
                <Download className="mr-1 h-3 w-3" />
                JSON
              </Button>
            </div>
          </div>
        </div>

        {/* Snippet */}
        <div className="mt-4">
          <p className="text-sm leading-relaxed text-foreground">
            {highlightMatches(result.snippet, query)}
          </p>
        </div>

        {/* Footer */}
        <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
          {result.word_count && (
            <span>{result.word_count.toLocaleString()} words</span>
          )}
          {result.file_size && (
            <span>{result.file_size}</span>
          )}
          <span>{result.matched_positions.length} matches</span>
        </div>

        {/* Score bar */}
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
          <div 
            className={cn(
              'h-full transition-all duration-300',
              scoreVariant === 'success' && 'bg-[#22C55E]',
              scoreVariant === 'warning' && 'bg-[#F59E0B]',
              scoreVariant === 'destructive' && 'bg-[#EF4444]'
            )}
            style={{ width: `${result.score * 100}%` }}
          />
        </div>
      </CardContent>
    </Card>
  )
}
