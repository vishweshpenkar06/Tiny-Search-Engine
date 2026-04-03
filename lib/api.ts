import type { SearchResponse, IndexStatus, IndexResponse } from './types'

// Mock data for demonstration
const mockResults = [
  {
    doc_id: 'doc_0',
    filename: 'artificial-intelligence.txt',
    path: '/data/documents/artificial-intelligence.txt',
    score: 0.92,
    snippet: 'Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience. Deep learning neural networks have revolutionized the field...',
    matched_positions: [0, 15, 45],
    word_count: 1250,
    file_size: '12.5 KB',
    indexed_at: '2026-04-03T10:30:00Z',
  },
  {
    doc_id: 'doc_1',
    filename: 'ml-guide.md',
    path: '/data/guides/ml-guide.md',
    score: 0.85,
    snippet: 'Learn machine learning from scratch with this comprehensive guide. We cover supervised learning, unsupervised learning, and reinforcement learning techniques...',
    matched_positions: [6, 52],
    word_count: 2400,
    file_size: '24.1 KB',
    indexed_at: '2026-04-03T10:30:00Z',
  },
  {
    doc_id: 'doc_2',
    filename: 'neural-networks.txt',
    path: '/data/research/neural-networks.txt',
    score: 0.78,
    snippet: 'Neural networks are computing systems inspired by biological neural networks. They consist of interconnected nodes that process information using machine learning algorithms...',
    matched_positions: [89],
    word_count: 890,
    file_size: '8.9 KB',
    indexed_at: '2026-04-03T10:30:00Z',
  },
  {
    doc_id: 'doc_3',
    filename: 'data-science-intro.txt',
    path: '/data/tutorials/data-science-intro.txt',
    score: 0.71,
    snippet: 'Data science combines statistics, machine learning, and domain expertise to extract insights from data. Modern machine learning techniques are essential tools...',
    matched_positions: [25, 72],
    word_count: 1800,
    file_size: '18.2 KB',
    indexed_at: '2026-04-03T10:30:00Z',
  },
  {
    doc_id: 'doc_4',
    filename: 'python-ml-tutorial.md',
    path: '/data/tutorials/python-ml-tutorial.md',
    score: 0.65,
    snippet: 'Python is the most popular language for machine learning development. Libraries like scikit-learn, TensorFlow, and PyTorch make implementing machine learning models straightforward...',
    matched_positions: [38, 115],
    word_count: 3200,
    file_size: '32.0 KB',
    indexed_at: '2026-04-03T10:30:00Z',
  },
  {
    doc_id: 'doc_5',
    filename: 'deep-learning-basics.txt',
    path: '/data/courses/deep-learning-basics.txt',
    score: 0.58,
    snippet: 'Deep learning is a subset of machine learning that uses multi-layered neural networks. These networks can automatically discover representations needed for classification...',
    matched_positions: [28],
    word_count: 1560,
    file_size: '15.6 KB',
    indexed_at: '2026-04-03T10:30:00Z',
  },
]

// Simulated delay for realistic API behavior
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

// Mock search API
export async function search(
  query: string,
  topK: number = 10,
  threshold: number = 0
): Promise<SearchResponse> {
  await delay(150 + Math.random() * 100)
  
  if (!query.trim()) {
    return {
      query: '',
      results_count: 0,
      search_time_ms: 0,
      results: [],
    }
  }

  const filteredResults = mockResults
    .filter(r => r.score >= threshold)
    .slice(0, topK)

  return {
    query,
    results_count: filteredResults.length,
    search_time_ms: Math.round(100 + Math.random() * 100),
    results: filteredResults,
  }
}

// Index status state (simulated)
let indexingState: IndexStatus = {
  status: 'idle',
  progress: 0,
  files_indexed: 0,
  total_files: 0,
  elapsed_time: '0s',
  estimated_remaining: '0s',
}

let indexingInterval: NodeJS.Timeout | null = null

// Start indexing
export async function startIndexing(fileCount: number = 100): Promise<IndexResponse> {
  await delay(200)
  
  indexingState = {
    status: 'indexing',
    progress: 0,
    files_indexed: 0,
    total_files: fileCount,
    elapsed_time: '0s',
    estimated_remaining: `~${Math.ceil(fileCount / 20)}s`,
    current_file: 'Preparing...',
  }

  // Simulate indexing progress
  let elapsed = 0
  const mockFiles = [
    'document1.txt', 'research-paper.md', 'notes.txt', 'data.csv',
    'report.html', 'article.txt', 'guide.md', 'readme.txt',
    'analysis.txt', 'summary.md', 'overview.txt', 'manual.md',
  ]

  if (indexingInterval) clearInterval(indexingInterval)
  
  indexingInterval = setInterval(() => {
    elapsed += 0.5
    const progress = Math.min(elapsed / (fileCount / 20), 1)
    const filesIndexed = Math.floor(progress * fileCount)
    
    indexingState = {
      status: progress >= 1 ? 'complete' : 'indexing',
      progress: progress * 100,
      files_indexed: filesIndexed,
      total_files: fileCount,
      elapsed_time: `${Math.floor(elapsed)}s`,
      estimated_remaining: progress >= 1 ? '0s' : `~${Math.ceil((fileCount / 20) - elapsed)}s`,
      current_file: progress >= 1 ? undefined : mockFiles[filesIndexed % mockFiles.length],
    }

    if (progress >= 1 && indexingInterval) {
      clearInterval(indexingInterval)
      indexingInterval = null
    }
  }, 500)

  return {
    status: 'indexing',
    files_count: fileCount,
    estimated_time: `~${Math.ceil(fileCount / 20)}s`,
  }
}

// Get indexing status
export async function getIndexStatus(): Promise<IndexStatus> {
  await delay(50)
  return { ...indexingState }
}

// Cancel indexing
export async function cancelIndexing(): Promise<void> {
  if (indexingInterval) {
    clearInterval(indexingInterval)
    indexingInterval = null
  }
  indexingState = {
    status: 'idle',
    progress: 0,
    files_indexed: 0,
    total_files: 0,
    elapsed_time: '0s',
    estimated_remaining: '0s',
  }
}

// Reset index state (for navigation)
export function resetIndexState(): void {
  if (indexingInterval) {
    clearInterval(indexingInterval)
    indexingInterval = null
  }
  indexingState = {
    status: 'idle',
    progress: 0,
    files_indexed: 0,
    total_files: 0,
    elapsed_time: '0s',
    estimated_remaining: '0s',
  }
}
