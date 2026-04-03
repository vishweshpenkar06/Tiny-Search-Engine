'use client'

import { useCallback, useState } from 'react'
import { Upload, Folder, File, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void
  isUploading?: boolean
}

export function UploadZone({ onFilesSelected, isUploading }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = Array.from(e.dataTransfer.files).filter(
      file => file.name.endsWith('.txt') || 
              file.name.endsWith('.md') || 
              file.name.endsWith('.html') ||
              file.name.endsWith('.csv')
    )
    
    if (files.length > 0) {
      setSelectedFiles(files)
    }
  }, [])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []).filter(
      file => file.name.endsWith('.txt') || 
              file.name.endsWith('.md') || 
              file.name.endsWith('.html') ||
              file.name.endsWith('.csv')
    )
    
    if (files.length > 0) {
      setSelectedFiles(files)
    }
  }, [])

  const removeFile = useCallback((index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }, [])

  const clearFiles = useCallback(() => {
    setSelectedFiles([])
  }, [])

  const handleStartIndexing = useCallback(() => {
    if (selectedFiles.length > 0) {
      onFilesSelected(selectedFiles)
    }
  }, [selectedFiles, onFilesSelected])

  return (
    <div className="space-y-6">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative flex min-h-[300px] flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all duration-200',
          isDragging
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : 'border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50',
          isUploading && 'pointer-events-none opacity-60'
        )}
      >
        <div className={cn(
          'flex h-16 w-16 items-center justify-center rounded-full transition-all duration-200',
          isDragging ? 'bg-primary/10' : 'bg-muted'
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
            or click to browse your files
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Supports .txt, .md, .html, .csv files
          </p>
        </div>

        <label className="mt-6 cursor-pointer">
          <input
            type="file"
            multiple
            accept=".txt,.md,.html,.csv"
            onChange={handleFileInput}
            className="hidden"
            disabled={isUploading}
          />
          <Button variant="outline" size="lg" asChild disabled={isUploading}>
            <span>
              <Folder className="mr-2 h-4 w-4" />
              Browse Files
            </span>
          </Button>
        </label>
      </div>

      {/* Selected Files Preview */}
      {selectedFiles.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="mb-4 flex items-center justify-between">
            <h4 className="font-semibold text-foreground">
              {selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''} selected
            </h4>
            <Button
              variant="ghost"
              size="sm"
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
                className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2"
              >
                <div className="flex items-center gap-3">
                  <File className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium text-foreground">
                    {file.name}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  disabled={isUploading}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          <Button
            className="mt-4 w-full"
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
