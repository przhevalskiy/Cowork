"""One-off: list Hive projects in the workspace and surface any VDR-related ones.

Reads HIVE_API_KEY / HIVE_USER_ID from environment or backend/.env.
Usage:  python scripts/discover_hive_projects.py
"""
import os
import sys
import json
from pathlib import Path

import httpx

# Load backend/.env if present (no hard dependency on python-dotenv)
env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("HIVE_API_KEY", "")
USER_ID = os.environ.get("HIVE_USER_ID", "")
WORKSPACE_ID = os.environ.get("HIVE_WORKSPACE_ID", "MvJ2A7jmTiCJcheoM")
BASE = "https://app.hive.com/api/v2"

if not API_KEY or not USER_ID:
    sys.exit("Missing HIVE_API_KEY / HIVE_USER_ID (set them in backend/.env or the environment).")

headers = {"api_key": API_KEY, "user_id": USER_ID}

# The v2 projects-for-workspace endpoint; fall back to the query-param form.
candidates = [
    f"{BASE}/workspaces/{WORKSPACE_ID}/projects",
    f"{BASE}/projects?workspaceId={WORKSPACE_ID}",
]

projects = None
with httpx.Client(timeout=20) as client:
    for url in candidates:
        try:
            r = client.get(url, headers=headers)
        except Exception as e:
            print(f"[error] {url} -> {e}")
            continue
        print(f"[try] GET {url} -> {r.status_code}")
        if r.status_code == 200:
            projects = r.json()
            break
        else:
            print("       body:", r.text[:300])

if projects is None:
    sys.exit("Could not retrieve projects from any endpoint variant.")

# Normalize to a list of dicts
items = projects if isinstance(projects, list) else projects.get("projects") or projects.get("data") or []
print(f"\nRetrieved {len(items)} project(s).\n")

def pid(p):  return p.get("id") or p.get("_id")
def name(p): return p.get("name") or p.get("title") or "(no name)"

print("=== ALL PROJECTS (id  |  name) ===")
for p in items:
    print(f"  {pid(p)}  |  {name(p)}")

print("\n=== VDR / IMPACT / AWARDS / MEDIA-MENTION matches ===")
needles = ("vdr", "impact", "award", "media mention", "submission")
hits = [p for p in items if any(n in name(p).lower() for n in needles)]
if hits:
    for p in hits:
        print(json.dumps(p, indent=2)[:1200])
        print("-" * 60)
else:
    print("  (no name matches — VDR may be a separate workspace, or labels inside one project)")
