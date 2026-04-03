import math
import os
import hashlib
from typing import List, Dict, Any, Set
from collections import defaultdict

from core.tokenizer import Tokenizer
from core.file_parser import FileParser

class SearchEngine:
    """Core TF-IDF search engine with inverted index."""
    
    def __init__(self):
        # Maps a token to a dictionary of {doc_id: [positions]}
        self.inverted_index: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
        
        # Stores document metadata and original content
        # doc_id -> {filename, path, content, tokens, word_count, hash}
        self.documents: Dict[str, Dict[str, Any]] = {}
        
        # Tracks how many documents contain each term
        self.doc_frequencies: Dict[str, int] = defaultdict(int)
        
        self.tokenizer = Tokenizer()
        
        # Track duplicate files by hash
        self.seen_hashes: Set[str] = set()
        
        # State tracking for indexing
        self.state = {
            "status": "idle",
            "progress": 0,
            "files_indexed": 0,
            "total_files": 0,
            "current_file": None,
            "error": None
        }

    def _get_file_hash(self, parsed_content: str) -> str:
        """Calculate a hash of the file content to detect duplicates."""
        return hashlib.sha256(parsed_content.encode('utf-8')).hexdigest()

    def index_folder(self, folder_path: str):
        """Index all supported files in a folder recursively."""
        self.state["status"] = "indexing"
        self.state["progress"] = 0
        self.state["files_indexed"] = 0
        self.state["error"] = None
        
        # First pass to count files
        files_to_index = []
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if filename.endswith(('.txt', '.md', '.html', '.htm', '.csv')):
                    files_to_index.append(os.path.join(root, filename))
                    
        self.state["total_files"] = len(files_to_index)
        
        if len(files_to_index) == 0:
            self.state["status"] = "complete"
            return
            
        print(f"Starting to index {self.state['total_files']} files...")
            
        # Second pass to actually index them
        for i, filepath in enumerate(files_to_index):
            filename = os.path.basename(filepath)
            self.state["current_file"] = filename
            
            try:
                self.index_file(filepath)
            except Exception as e:
                print(f"Error indexing {filepath}: {e}")
                
            self.state["files_indexed"] += 1
            self.state["progress"] = int((self.state["files_indexed"] / self.state["total_files"]) * 100)
            
        # Give a slight delay before marking complete so frontend sees 100%
        import time
        time.sleep(0.5)
        self.state["status"] = "complete"
        self.state["current_file"] = None
        self.state["progress"] = 100
        print(f"Indexing complete. Indexed {self.state['files_indexed']} unique files.")

    def index_file(self, filepath: str):
        """Parse and index a single file using TF-IDF."""
        parsed_data = FileParser.parse_file(filepath)
        
        if not parsed_data or not parsed_data.get('content'):
            return
            
        content = parsed_data['content']
        file_hash = self._get_file_hash(content)
        
        # Deduplication
        if file_hash in self.seen_hashes:
            print(f"Skipping duplicate file: {filepath}")
            return
            
        self.seen_hashes.add(file_hash)
        
        # Create a unique ID for the document (can just use the basename if we handle temp uploads, 
        # but adding a prefix or hash ensures uniqueness if same filename exists in different dirs)
        doc_id = hashlib.md5(filepath.encode()).hexdigest()[:8] + "_" + os.path.basename(filepath)
        filename = os.path.basename(filepath)
        
        # Tokenize
        tokens = self.tokenizer.tokenize(content)
        word_count = len(tokens)
        
        if word_count == 0:
            return
            
        # Build inverted index
        unique_tokens_in_doc = set()
        for pos, token in enumerate(tokens):
            self.inverted_index[token][doc_id].append(pos)
            unique_tokens_in_doc.add(token)
            
        # Update document frequencies (in how many docs does a term appear?)
        for token in unique_tokens_in_doc:
            self.doc_frequencies[token] += 1
            
        # Store document metadata
        self.documents[doc_id] = {
            "id": doc_id,
            "filename": filename,
            "path": filepath,
            "content": content,
            "tokens": tokens,
            "word_count": word_count,
            "hash": file_hash
        }

    def _calculate_tf(self, term: str, doc_id: str) -> float:
        """Calculate Term Frequency (TF)."""
        term_count = len(self.inverted_index.get(term, {}).get(doc_id, []))
        total_tokens = self.documents[doc_id]['word_count']
        
        # TF = count of term in doc / total words in doc
        return term_count / total_tokens if total_tokens > 0 else 0
        
    def _calculate_idf(self, term: str) -> float:
        """Calculate Inverse Document Frequency (IDF)."""
        total_docs = len(self.documents)
        docs_with_term = self.doc_frequencies.get(term, 0)
        
        if docs_with_term == 0:
            return 0
            
        # IDF = log(total docs / docs with term)
        # Using base e (natural log), $+ 1$ smoothing helps prevent 0 division/log(0) issues in some setups
        return math.log(total_docs / (docs_with_term))

    def search(self, query: str, top_k: int = 10, threshold: float = 0.0) -> List[Dict[str, Any]]:
        """Search the indexed documents using TF-IDF ranking."""
        query_tokens = self.tokenizer.tokenize(query)
        
        if not query_tokens or not self.documents:
            return []
            
        # Phase 1 simple implementation: AND logic - docs must contain ALL query terms
        # (Alternatively, we could do OR logic with TF-IDF scoring, which is more standard. Let's do OR but score highly for AND)
        
        # Find all documents that contain at least one query token
        matching_docs = set()
        for token in query_tokens:
            if token in self.inverted_index:
                matching_docs.update(self.inverted_index[token].keys())
                
        if not matching_docs:
            return []
            
        # Score each matching document
        scores = {}
        matched_positions_by_doc = defaultdict(list)
        
        for doc_id in matching_docs:
            score = 0
            doc_contains_all = True
            
            for token in query_tokens:
                if token not in self.inverted_index or doc_id not in self.inverted_index[token]:
                    doc_contains_all = False
                    continue
                    
                # Calculate TF-IDF
                tf = self._calculate_tf(token, doc_id)
                idf = self._calculate_idf(token)
                
                # TF-IDF weight
                weight = tf * idf
                score += weight
                
                # Keep track of positions for highlighting
                matched_positions_by_doc[doc_id].extend(self.inverted_index[token][doc_id])
                
            # Bonus multiplier for containing ALL query terms
            if doc_contains_all and len(query_tokens) > 1:
                score *= 1.5
                
            scores[doc_id] = score
            
        # Sort and filter
        ranked_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Format results
        results = []
        for doc_id, score in ranked_docs:
            if score < threshold:
                continue
                
            doc = self.documents[doc_id]
            positions = sorted(matched_positions_by_doc[doc_id])
            
            # Generate snippet - try to start around the first match
            content = doc['content']
            snippet_start = 0
            
            # Very basic snippet generation
            if positions:
                # Find the actual text index roughly corresponding to the token position
                # This is an approximation since tokenization removes punctuation
                first_pos = positions[0]
                words = content.split()
                if first_pos < len(words):
                    snippet_word_start = max(0, first_pos - 10)
                    snippet_word_end = min(len(words), first_pos + 40)
                    snippet = " ".join(words[snippet_word_start:snippet_word_end])
                    if snippet_word_start > 0:
                        snippet = "..." + snippet
                    if snippet_word_end < len(words):
                        snippet = snippet + "..."
                else:
                    snippet = content[:300] + ("..." if len(content) > 300 else "")
            else:
                snippet = content[:300] + ("..." if len(content) > 300 else "")
            
            # Normalize score to 0-1 range for the frontend (rough approximation)
            # Find max possible score roughly to normalize.
            normalized_score = min(1.0, score * 10) # arbitrary scaling factor for demo
                
            results.append({
                "doc_id": doc_id,
                "filename": doc["filename"],
                "path": doc["path"],
                "score": round(normalized_score, 4),
                "raw_score": score,
                "snippet": snippet,
                "word_count": doc["word_count"],
                "file_size": f"{len(doc['content']) / 1024:.1f} KB",
                "indexed_at": "2024-01-01T00:00:00Z", # Placeholder
                "matched_positions": positions[:10] # Just first 10 for UI
            })
            
            if len(results) >= top_k:
                break
                
        return results
