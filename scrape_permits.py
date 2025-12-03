import os
import sys
from pyairtable import Table
from airtable_io import AirtableIO

# Prefer TABLE ID once you have it; name also works if exact
TABLE_REF = os.environ.get("AIRTABLE_TABLE_ID") or os.environ.get("AIRTABLE_TABLE_NAME") or "Permits"

def scrape_permits():
    # TODO: replace with your real scraper
    return [
        {
            "permit_number": "2025-00123",
            "address": "123 Main St",
            "city": "Springfield",
            "status": "Approved",
            "issue_date": "2025-11-01",
            "contractor": "ACME Solar",
            "system_size_kw": 7.2,
        }
    ]

def main():
    key = os.environ.get("AIRTABLE_API_KEY")
    base = os.environ.get("AIRTABLE_BASE_ID")
    if not key or not base:
        print("Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID"); sys.exit(1)

    table = Table(key, base, TABLE_REF)
    io = AirtableIO(table, dedupe_field="permit_number")

    rows = scrape_permits()
    if not rows:
        print("No rows scraped"); return

    # Fast path: batch dedupe + upsert by permit_number
    io.batch_upsert(rows, key_field="permit_number", chunk=10)
    print(f"Upserted {len(rows)} rows into {TABLE_REF}")

if __name__ == "__main__":
    main()
