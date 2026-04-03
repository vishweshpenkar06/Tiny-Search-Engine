import requests
import time
import os

API_URL = "http://localhost:5000/api"

# 1. Upload the files
files_to_upload = [
    r"C:\Users\MANSI\Desktop\VISHWESH\Projects\Projects for GITHUB\Tiny Search Engine AG\sample_docs\ai.txt",
    r"C:\Users\MANSI\Desktop\VISHWESH\Projects\Projects for GITHUB\Tiny Search Engine AG\sample_docs\web.md",
    r"C:\Users\MANSI\Desktop\VISHWESH\Projects\Projects for GITHUB\Tiny Search Engine AG\sample_docs\fox.txt"
]

files_payload = []
for file_path in files_to_upload:
    files_payload.append(
        ('files', (os.path.basename(file_path), open(file_path, 'rb'), 'text/plain'))
    )

print("📤 Uploading files...")
upload_res = requests.post(f"{API_URL}/upload", files=files_payload)
upload_data = upload_res.json()
print("Upload Result:", upload_data)
folder_path = upload_data.get('folder_path')

# 2. Start Indexing
print("\n⚙️ Starting Indexing...")
index_res = requests.post(f"{API_URL}/index", json={"folder_path": folder_path})
print("Index Start Result:", index_res.json())

# Wait for indexing to complete
for i in range(10):
    status_res = requests.get(f"{API_URL}/index/status")
    status_data = status_res.json()
    print(f"Status: {status_data['status']} | Progress: {status_data['progress']}% | Files Indexed: {status_data['files_indexed']}/{status_data['total_files']}")
    if status_data['status'] == 'complete':
        break
    time.sleep(1)

# 3. Test Search
print("\n🔍 Testing Search for 'Next.js'...")
search_res = requests.post(f"{API_URL}/search", json={"query": "Next.js", "top_k": 10})
print("Result 1:", search_res.json())

print("\n🔍 Testing Search for 'machine learning'...")
search_res = requests.post(f"{API_URL}/search", json={"query": "machine learning", "top_k": 10})
print("Result 2:", search_res.json())
