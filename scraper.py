"""
Permit Scraper v1
- Pulls permits from API or HTML pages
- Normalizes to a single schema
- Dedupes by (address, permit_number)
- Optional: geocodes and pushes to Airtable

Python 3.10+
pip install httpx parsel pandas pydantic python-dateutil tenacity pyyaml
"""

import re
import sys
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import httpx
from parsel import Selector
import pandas as pd
from dateutil import parser as dtp
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
import yaml

# ---------- Config ----------

class Config:
    def __init__(self, path: str):
        with open(path, "r") as f:
            self.cfg = yaml.safe_load(f)
        self.sources = self.cfg.get("sources", [])
        self.geocode = self.cfg.get("geocode", {})
        self.output_csv = self.cfg.get("output_csv", "permits.csv")
        self.days_back = int(self.cfg.get("days_back", 7))
        self.airtable = self.cfg.get("airtable", {})
        self.enable_airtable = bool(self.airtable.get("enabled", False))

# ---------- Utils ----------

def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def sha1(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update((p or "").encode("utf-8"))
    return h.hexdigest()

def parse_date(s: str):
    if not s:
        return None
    try:
        return dtp.parse(s).date().isoformat()
    except Exception:
        return None

# ---------- HTTP ----------

DEFAULT_HEADERS = {
    "User-Agent": "PermitScraper/1.0"
}

@retry(stop=stop_after_attempt(5), wait=wait_exponential_jitter(1, 5))
def fetch(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None) -> httpx.Response:
    headers = {**DEFAULT_HEADERS, **(headers or {})}
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        if method.upper() == "GET":
            r = client.get(url, params=params)
        else:
            r = client.request(method.upper(), url, params=params, data=data, json=json_body)
        r.raise_for_status()
        return r

# ---------- Parsers ----------

def parse_api_json(item: Dict[str,Any], mapping: Dict[str,str]) -> Dict[str,Any]:
    out = {}
    for k, path in mapping.items():
        cur = item
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                cur = None
                break
        out[k] = cur
    return out

def parse_html_list(html: str, row_selector: str, fields: Dict[str,str]):
    sel = Selector(text=html)
    rows = []
    for row in sel.css(row_selector):
        rec = {}
        for k, css in fields.items():
            rec[k] = normalize_whitespace("".join(row.css(css).getall()))
        rows.append(rec)
    return rows

# ---------- Geocode (stub) ----------

def geocode_address(addr: str, city: str, state: str, zip_code: str, cfg):
    # Stub to avoid external calls in starter kit
    full = normalize_whitespace(f"{addr} {city} {state} {zip_code}")
    return {"full_address": full, "lat": None, "lng": None}

# ---------- Airtable Push (optional) ----------

def airtable_upsert(df: pd.DataFrame, cfg):
    webhook = cfg.get("webhook_url")
    if not webhook:
        print("Airtable webhook_url not set. Skipping push.")
        return
    payload_path = cfg.get("debug_payload_path", "airtable_payload.json")
    with open(payload_path, "w") as f:
        json.dump(df.to_dict(orient="records"), f, indent=2)
    print(f"Wrote payload to {payload_path}")

# ---------- Main ----------

REQUIRED_SCHEMA = [
    "permit_number","issue_date","work_class","description",
    "address","city","state","zip","contractor","owner",
    "estimated_value","source_url","source_name"
]

def clean_record(rec):
    rec["issue_date"] = parse_date(rec.get("issue_date"))
    rec["address"] = normalize_whitespace(rec.get("address",""))
    rec["city"] = normalize_whitespace(rec.get("city",""))
    rec["state"] = normalize_whitespace(rec.get("state",""))
    rec["zip"] = normalize_whitespace(rec.get("zip",""))
    rec["description"] = normalize_whitespace(rec.get("description",""))
    rec["hash_id"] = sha1(rec.get("permit_number",""), rec.get("address",""))
    return rec

def run(cfg_path: str):
    conf = Config(cfg_path)
    all_rows = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=conf.days_back)).date().isoformat()

    for src in conf.sources:
        name = src["name"]
        mode = src["mode"]
        print(f"[{name}] mode={mode}")
        if mode == "api":
            r = fetch(src["url"], method=src.get("method","GET"), params=src.get("params"), json_body=src.get("json"))
            data = r.json()
            items = data
            for key in src.get("list_path","").split("."):
                if key:
                    items = items.get(key, [])
            for it in items:
                rec = parse_api_json(it, src["mapping"])
                rec["source_url"] = src["url"]
                rec["source_name"] = name
                all_rows.append(clean_record(rec))
        elif mode == "html":
            r = fetch(src["url"])
            rows = parse_html_list(r.text, src["row_selector"], src["fields"])
            for rec in rows:
                rec["source_url"] = src["url"]
                rec["source_name"] = name
                all_rows.append(clean_record(rec))
        else:
            print(f"Unknown mode: {mode}")

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("No rows scraped.")
        return

    if "issue_date" in df.columns:
        # Filter permits: include those with valid dates >= cutoff, exclude null dates
        df = df[df["issue_date"].notna() & (df["issue_date"] >= cutoff)]
    df = df.drop_duplicates(subset=["hash_id"])

    if conf.geocode.get("enabled"):
        geo = df.apply(lambda r: geocode_address(r["address"], r["city"], r["state"], r["zip"], conf.geocode), axis=1, result_type="expand")
        for k in geo.columns:
            df[k] = geo[k]

    for k in REQUIRED_SCHEMA:
        if k not in df.columns:
            df[k] = None

    out_path = conf.output_csv
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} permits to {out_path}")

    if conf.enable_airtable:
        airtable_upsert(df, conf.airtable)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scraper.py config.yml")
        sys.exit(1)
    run(sys.argv[1])
