import subprocess
import time
import requests

# Step 1: Start FastAPI server
server_process = subprocess.Popen(
    ["uvicorn", "app.main:app", "--reload"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Step 2: Wait a few seconds for the server to start
print("Waiting for server to start...")
time.sleep(5)  # increase if your server needs more time

# Step 3: Run test request
url = "http://127.0.0.1:8000/jobs/"
payload = {
    "title": "DevOps Engineer",
    "company": "Baalebos Cloud",
    "location": "Remote",
    "description": "Manage CI/CD pipelines and Kubernetes infrastructure"
}

try:
    response = requests.post(url, json=payload)
    print("Status code:", response.status_code)
    print("Response JSON:", response.json())
except requests.exceptions.RequestException as e:
    print("Error connecting to server:", e)

# Step 4: Optionally, stop the server after test
server_process.terminate()
