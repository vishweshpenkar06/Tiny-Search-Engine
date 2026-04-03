import os
import threading
import tempfile
from datetime import datetime
import time

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from core.search_engine import SearchEngine
from utils.validation import validate_search_query, validate_file_upload
from utils.error_handler import api_error, api_success
from utils.logger import logger

app = Flask(__name__)
# Enable CORS for Next.js frontend
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Global search engine instance
engine = SearchEngine()
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'tiny_search_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return api_success({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Handle file uploads to a temporary directory."""
    try:
        files = request.files.getlist('files')
        
        if not files or all(f.filename == '' for f in files):
            return api_error("No files provided", 400)
            
        # Create a unique session folder for this upload batch
        session_id = str(int(time.time()))
        session_folder = os.path.join(UPLOAD_FOLDER, session_id)
        os.makedirs(session_folder, exist_ok=True)
        
        saved_count = 0
        for file in files:
            if file and file.filename:
                # Basic validation
                content_loc = file.read()
                is_valid, err_msg = validate_file_upload(file.filename, len(content_loc))
                file.seek(0) # Reset pointer
                
                if not is_valid:
                    logger.warning(f"File validation failed for {file.filename}: {err_msg}")
                    continue
                    
                filename = secure_filename(file.filename)
                filepath = os.path.join(session_folder, filename)
                file.save(filepath)
                saved_count += 1
                
        if saved_count == 0:
            return api_error("No valid files were uploaded", 400)
            
        logger.info(f"Successfully uploaded {saved_count} files to {session_folder}")
        return api_success({
            "status": "uploaded",
            "folder_path": session_folder,
            "file_count": saved_count
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return api_error("Internal server error during upload", 500)

@app.route('/api/index', methods=['POST'])
def start_indexing():
    """Start the indexing process in a background thread."""
    try:
        data = request.get_json()
        if not data or 'folder_path' not in data:
            return api_error("folder_path is required", 400)
            
        folder_path = data['folder_path']
        if not os.path.exists(folder_path):
            return api_error("Folder not found", 404)
            
        # Optional: Prevent concurrent indexing
        if engine.state["status"] == "indexing":
            return api_error("Indexing already in progress", 409)
            
        logger.info(f"Starting background indexing for {folder_path}")
        
        # Start indexing in a background thread
        thread = threading.Thread(target=engine.index_folder, args=(folder_path,))
        thread.daemon = True
        thread.start()
        
        return api_success({
            "status": "indexing_started",
            "index_id": "default"
        }, 202)
        
    except Exception as e:
        logger.error(f"Index start error: {e}")
        return api_error("Failed to start indexing", 500)

@app.route('/api/index/status', methods=['GET'])
def index_status():
    """Get the current indexing status."""
    return api_success(engine.state)

@app.route('/api/index/cancel', methods=['POST'])
def index_cancel():
    """Cancel indexing (simplified for now, just resets state)."""
    # Note: Actually terminating a thread is complex in Python.
    # In a real app, we'd use a threading.Event flag that the indexer checks.
    if engine.state["status"] == "indexing":
        engine.state["status"] = "error"
        engine.state["error"] = "Cancelled by user"
        logger.info("Indexing cancelled")
    return api_success({"status": "cancelled"})

@app.route('/api/search', methods=['POST'])
def search_documents():
    """Search the index."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Invalid JSON", 400)
            
        query = data.get('query', '')
        top_k = data.get('top_k', 10)
        threshold = data.get('threshold', 0.0)
        
        # Input validation
        is_valid, err_msg, sanitized_query = validate_search_query(query)
        if not is_valid:
            return api_error(err_msg, 400)
            
        # Ensure top_k is reasonable
        try:
            top_k = int(top_k)
            top_k = max(1, min(100, top_k))
        except ValueError:
            top_k = 10
            
        # Ensure threshold is reasonable
        try:
            threshold = float(threshold)
            threshold = max(0.0, min(1.0, threshold))
        except ValueError:
            threshold = 0.0
            
        start_time = time.time()
        
        logger.info(f"Searching for: '{sanitized_query}', top_k: {top_k}, threshold: {threshold}")
        results = engine.search(sanitized_query, top_k, threshold)
        
        end_time = time.time()
        search_time_ms = int((end_time - start_time) * 1000)
        
        return api_success({
            "query": sanitized_query,
            "results_count": len(results),
            "search_time_ms": search_time_ms,
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return api_error("Internal server error during search", 500)

if __name__ == '__main__':
    logger.info("Starting Tiny Search Engine backend...")
    app.run(debug=True, port=5000, host="0.0.0.0")
