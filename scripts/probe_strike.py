import os, json, requests
from dotenv import load_dotenv
load_dotenv()
auth = (os.environ["ISONE_USERNAME"], os.environ["ISONE_PASSWORD"])
headers = {"Accept": "application/json"}

resp = requests.get(
    "https://webservices.iso-ne.com/api/v1.1/daasstrikeprices/day/20250624",
    auth=auth, headers=headers
)
print("Status:", resp.status_code)
data = resp.json()
print("Top-level keys:", list(data.keys()))
print(json.dumps(data, indent=2)[:5000])
