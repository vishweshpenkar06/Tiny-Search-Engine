'use client'

import { useState } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ErrorBoundaryProps {
  children?: React.ReactNode
  error?: string | Error | null
  onRetry?: () => void
}

export function ErrorBoundary({ children, error: propError, onRetry }: ErrorBoundaryProps) {
  const [internalError, setInternalError] = useState<Error | null>(null)

  const activeError = propError || internalError

  if (activeError) {
    const message = activeError instanceof Error ? activeError.message : String(activeError)
    
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900/50 dark:bg-red-900/10">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 dark:text-red-500" />
          <div className="flex-1">
            <h3 className="font-semibold text-red-900 dark:text-red-400">
              Something went wrong
            </h3>
            <p className="text-sm text-red-700 mt-1 dark:text-red-300/80">
              {message}
            </p>
            {onRetry && (
              <Button
                size="sm"
                variant="outline"
                className="mt-3 border-red-200 text-red-700 hover:bg-red-100 hover:text-red-800 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/40"
                onClick={onRetry}
              >
                <RefreshCw className="mr-2 h-3.5 w-3.5" />
                Try again
              </Button>
            )}
            {!onRetry && propError === undefined && (
              <Button
                size="sm"
                variant="outline"
                className="mt-3 border-red-200 text-red-700 hover:bg-red-100 hover:text-red-800 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/40"
                onClick={() => setInternalError(null)}
              >
                Dismiss
              </Button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
