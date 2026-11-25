'use client'

import { useCallback, useMemo, useRef, useState } from 'react'
import { Upload, Folder, File, X, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { formatBytes } from '@/lib/format'
import { DEFAULT_LIMITS } from '@/lib/config'

interface UploadLimits {
  allowed_extensions?: string[]
  max_file_size?: number
  max_files?: number
}

interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void
  isUploading?: boolean
  limits?: UploadLimits
}

interface RejectedFile {
  name: string
  reason: string
}

function extensionOf(name: string): string {
  const index = name.lastIndexOf('.')
  return index === -1 ? '' : name.slice(index + 1).toLowerCase()
}

export function UploadZone({ onFilesSelected, isUploading = false, limits }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [rejected, setRejected] = useState<RejectedFile[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  const allowedExtensions = useMemo(() => {
    const configured = limits?.allowed_extensions ?? DEFAULT_LIMITS.allowed_extensions
    return new Set([
      ...configured.map((extension) => extension.replace(/^\./, '').toLowerCase()),
      'txt',
      'md',
      'markdown',
      'html',
      'htm',
      'csv',
    ])
  }, [limits?.allowed_extensions])

  const maxFileSize = limits?.max_file_size ?? DEFAULT_LIMITS.max_file_size
  const maxFiles = limits?.max_files ?? DEFAULT_LIMITS.max_files
  const totalSize = selectedFiles.reduce((sum, file) => sum + file.size, 0)

  const validate = useCallback((incoming: File[], existing: File[]) => {
    const accepted: File[] = []
    const problems: RejectedFile[] = []
    const names = new Set(existing.map((file) => file.name))

    for (const file of incoming) {
      if (!allowedExtensions.has(extensionOf(file.name))) {
        problems.push({ name: file.name, reason: 'unsupported file type' })
        continue
      }
      if (file.size > maxFileSize) {
        problems.push({ name: file.name, reason: `larger than ${formatBytes(maxFileSize)}` })
        continue
      }
      if (file.size === 0) {
        problems.push({ name: file.name, reason: 'file is empty' })
        continue
      }
      if (names.has(file.name)) {
        problems.push({ name: file.name, reason: 'already selected' })
        continue
      }
      if (existing.length + accepted.length >= maxFiles) {
        problems.push({ name: file.name, reason: `limit of ${maxFiles} files reached` })
        continue
      }
      names.add(file.name)
      accepted.push(file)
    }

    return { accepted, problems }
  }, [allowedExtensions, maxFileSize, maxFiles])

  const addFiles = useCallback((incoming: File[]) => {
    const { accepted, problems } = validate(incoming, selectedFiles)
    if (accepted.length > 0) setSelectedFiles((previous) => [...previous, ...accepted])
    setRejected(problems)
  }, [validate, selectedFiles])

  const handleFileInput = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files ?? []))
    event.target.value = ''
  }, [addFiles])

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragging(false)
    addFiles(Array.from(event.dataTransfer.files))
  }, [addFiles])

  const removeFile = useCallback((index: number) => {
    setSelectedFiles((previous) => previous.filter((_, position) => position !== index))
  }, [])

  const clearFiles = useCallback(() => {
    setSelectedFiles([])
    setRejected([])
  }, [])

  const handleStartIndexing = useCallback(() => {
    if (selectedFiles.length > 0) onFilesSelected(selectedFiles)
  }, [selectedFiles, onFilesSelected])

  const accept = Array.from(allowedExtensions).map((extension) => `.${extension}`).join(',')

  return (
    <div className="space-y-6">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative flex min-h-[300px] flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all duration-200',
          isDragging
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : 'border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50',
          isUploading && 'pointer-events-none opacity-60',
        )}
      >
        <div className={cn(
          'flex h-16 w-16 items-center justify-center rounded-full transition-all duration-200',
          isDragging ? 'bg-primary/10' : 'bg-muted',
        )}>
          {isDragging ? (
            <Folder className="h-8 w-8 text-primary" />
          ) : (
            <Upload className="h-8 w-8 text-muted-foreground" />
          )}
        </div>

        <div className="mt-6 text-center">
          <h3 className="text-lg font-semibold text-foreground">
            {isDragging ? 'Drop files here' : 'Drag & drop your documents'}
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            or use the button below to browse your files
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Supports {accept} · up to {maxFiles} files · {formatBytes(maxFileSize)} each
          </p>
        </div>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          aria-label="Choose documents to upload"
          onChange={handleFileInput}
          disabled={isUploading}
          className="sr-only"
        />
        <Button
          type="button"
          variant="outline"
          size="lg"
          className="mt-6 focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => inputRef.current?.click()}
          disabled={isUploading}
        >
          <Folder className="mr-2 h-4 w-4" />
          Browse Files
        </Button>
      </div>

      {rejected.length > 0 && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900/50 dark:bg-red-900/10">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-500" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-red-900 dark:text-red-400">
                Some files were not added
              </p>
              <ul className="mt-2 space-y-1">
                {rejected.map((item, index) => (
                  <li key={`${item.name}-${index}`} className="break-words text-sm text-red-700 dark:text-red-300/80">
                    {item.name} — {item.reason}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={() => setRejected([])}
                className="mt-2 text-xs text-red-700 underline hover:text-red-900 focus-visible:ring-2 focus-visible:ring-ring dark:text-red-300"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedFiles.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="mb-4 flex items-center justify-between gap-2">
            <h4 className="min-w-0 break-words font-semibold text-foreground">
              {selectedFiles.length} / {maxFiles} file{selectedFiles.length !== 1 ? 's' : ''} selected · {formatBytes(totalSize)}
            </h4>
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0 focus-visible:ring-2 focus-visible:ring-ring"
              onClick={clearFiles}
              disabled={isUploading}
            >
              Clear all
            </Button>
          </div>

          <div className="max-h-[200px] space-y-2 overflow-y-auto">
            {selectedFiles.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="flex min-w-0 items-center justify-between gap-2 rounded-lg bg-muted/50 px-3 py-2"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <File className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 truncate text-sm font-medium text-foreground" title={file.name}>
                    {file.name}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatBytes(file.size)}
                  </span>
                </div>
                <button
                  type="button"
                  aria-label={`Remove ${file.name}`}
                  onClick={() => removeFile(index)}
                  className="shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  disabled={isUploading}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          <Button
            type="button"
            className="mt-4 w-full focus-visible:ring-2 focus-visible:ring-ring"
            size="lg"
            onClick={handleStartIndexing}
            disabled={isUploading}
          >
            {isUploading ? 'Starting...' : 'Start Indexing'}
          </Button>
        </div>
      )}
    </div>
  )
}
