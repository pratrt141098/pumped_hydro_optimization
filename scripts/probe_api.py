"""
One-shot probe: hit the DA LMP endpoint and pretty-print the raw JSON structure
so we can see the shape before writing any parsers.
"""
import os, json
import requests
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.environ["ISONE_USERNAME"]
PASSWORD  = os.environ["ISONE_PASSWORD"]
HEADERS  = {"Accept": "application/json"}

URL = "https://webservices.iso-ne.com/api/v1.1/hourlylmp/da/final/day/20250624/location/4000"

resp = requests.get(URL, auth=(USERNAME, PASSWORD), headers=HEADERS)
if not resp.ok:
    raise RuntimeError(f"Request failed {resp.status_code}: {resp.text}")

data = resp.json()

print("=== Top-level keys ===")
print(list(data.keys()))

print("\n=== Second level (value types) ===")
for k, v in data.items():
    if isinstance(v, list):
        print(f"  {k!r}: list of {len(v)} items")
        if v:
            print(f"    first item keys: {list(v[0].keys()) if isinstance(v[0], dict) else type(v[0])}")
            print(f"    first item: {json.dumps(v[0], indent=6)}")
    elif isinstance(v, dict):
        print(f"  {k!r}: dict with keys {list(v.keys())}")
    else:
        print(f"  {k!r}: {type(v).__name__} = {v!r}")

print("\n=== Full first two records (pretty) ===")
# find the first list value and show its first 2 entries
for k, v in data.items():
    if isinstance(v, list) and v:
        print(json.dumps(v[:2], indent=2))
        break
