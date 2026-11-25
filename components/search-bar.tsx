'use client'

import { useState } from 'react'
import { Search, X, Command } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  onSubmit: (value: string) => void
  placeholder?: string
  autoFocus?: boolean
  isLoading?: boolean
  maxLength?: number
  className?: string
}

export function SearchBar({
  value,
  onChange,
  onSubmit,
  placeholder = 'Search documents...',
  autoFocus = false,
  isLoading = false,
  maxLength = 500,
  className,
}: SearchBarProps) {
  const inputRef = useKeyboardShortcuts()
  const [isFocused, setIsFocused] = useState(false)

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    onSubmit(value)
  }

  const handleClear = () => {
    onChange('')
    inputRef.current?.focus()
  }

  return (
    <form
      role="search"
      aria-busy={isLoading}
      onSubmit={handleSubmit}
      className={cn('relative w-full', className)}
    >
      <div
        className={cn(
          'flex items-center rounded-lg border bg-card transition-all duration-200',
          isFocused
            ? 'border-primary ring-[3px] ring-primary/10'
            : 'border-border hover:border-primary/50',
        )}
      >
        <div className="flex h-12 w-12 items-center justify-center">
          <Search className={cn(
            'h-5 w-5 transition-colors',
            isFocused ? 'text-primary' : 'text-muted-foreground',
          )} />
        </div>

        <input
          ref={inputRef}
          type="search"
          aria-label="Search documents"
          aria-busy={isLoading}
          autoFocus={autoFocus}
          maxLength={maxLength}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          className="h-12 min-w-0 flex-1 bg-transparent pr-4 text-base text-foreground placeholder:text-muted-foreground focus:outline-none"
        />

        {value && (
          <button
            type="button"
            aria-label="Clear search"
            title="Clear search"
            onClick={handleClear}
            className="mr-2 flex h-8 w-8 shrink-0 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <X className="h-4 w-4" />
          </button>
        )}

        {!isFocused && !value && (
          <div className="mr-3 flex shrink-0 items-center rounded border border-border bg-muted/50 px-1.5 py-0.5 text-xs text-muted-foreground">
            <Command className="mr-1 h-3 w-3" />
            <span>K</span>
          </div>
        )}

        {isLoading && (
          <div className="mr-4 shrink-0" aria-hidden="true">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}
      </div>
    </form>
  )
}
