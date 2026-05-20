import os, json, requests
from dotenv import load_dotenv
load_dotenv()
auth = (os.environ["ISONE_USERNAME"], os.environ["ISONE_PASSWORD"])
headers = {"Accept": "application/json"}

resp = requests.get(
    "https://webservices.iso-ne.com/api/v1.1/daasreservedata/day/20250624",
    auth=auth, headers=headers
)
print("Status:", resp.status_code)
data = resp.json()
records = data["isone_web_services"]["day_ahead_reserves"]
print("day_ahead_reserves length:", len(records))
for i, r in enumerate(records):
    print(f"\nRecord {i}:")
    print(json.dumps(r, indent=2)[:3000])
