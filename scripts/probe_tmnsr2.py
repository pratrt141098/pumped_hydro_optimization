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
raw = resp.json()
# dump the entire response to a file so we can inspect it
with open("data/tmnsr_raw.json", "w") as f:
    json.dump(raw, f, indent=2)
print("Wrote data/tmnsr_raw.json")
print("Top-level keys:", list(raw.keys()))
ws = raw["isone_web_services"]
print("isone_web_services keys:", list(ws.keys()))
dar = ws["day_ahead_reserves"]
print("day_ahead_reserves type:", type(dar), "len:", len(dar))
# inspect each item
for i, item in enumerate(dar):
    print(f"\nitem[{i}] type: {type(item)}")
    if isinstance(item, dict):
        print("  keys:", list(item.keys()))
    elif isinstance(item, str):
        print("  value:", repr(item[:200]))
    elif isinstance(item, list):
        print("  list len:", len(item))
        if item:
            print("  first element:", json.dumps(item[0], indent=4)[:500])
