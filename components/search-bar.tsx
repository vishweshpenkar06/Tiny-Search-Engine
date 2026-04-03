'use client'

import { useState, useRef, useEffect } from 'react'
import { Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  onSubmit: (value: string) => void
  placeholder?: string
  autoFocus?: boolean
  isLoading?: boolean
  className?: string
}

export function SearchBar({
  value,
  onChange,
  onSubmit,
  placeholder = 'Search documents...',
  autoFocus = false,
  isLoading = false,
  className,
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isFocused, setIsFocused] = useState(false)

  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus()
    }
  }, [autoFocus])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(value)
  }

  const handleClear = () => {
    onChange('')
    inputRef.current?.focus()
  }

  return (
    <form onSubmit={handleSubmit} className={cn('relative w-full', className)}>
      <div
        className={cn(
          'flex items-center rounded-lg border bg-card transition-all duration-200',
          isFocused
            ? 'border-primary ring-[3px] ring-primary/10'
            : 'border-border hover:border-primary/50'
        )}
      >
        <div className="flex h-12 w-12 items-center justify-center">
          <Search className={cn(
            'h-5 w-5 transition-colors',
            isFocused ? 'text-primary' : 'text-muted-foreground'
          )} />
        </div>
        
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          className="h-12 flex-1 bg-transparent pr-4 text-base text-foreground placeholder:text-muted-foreground focus:outline-none"
        />

        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="mr-2 flex h-8 w-8 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}

        {isLoading && (
          <div className="mr-4">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}
      </div>
    </form>
  )
}
