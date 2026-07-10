import requests
import json
import sys

url = "http://127.0.0.1:8000/api/v1/migration/request"
with open("sample_files/project.json", "r", encoding="utf-8") as f:
    project_json_content = f.read()

payload = {
    "submitted_by": "stakeholder-123",
    "prompt": "Analyze and migrate Core Banking Legacy Database to AWS, optimize for high availability",
    "project_json": project_json_content
}

try:
    print("Sending real POST request to Gateway...")
    response = requests.post(url, json=payload, timeout=20)
    print("Response status code:", response.status_code)
    print("Response content:", response.json())
except Exception as e:
    print("Failed to send request:", e)
    sys.exit(1)
