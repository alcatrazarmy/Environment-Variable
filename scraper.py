#!/usr/bin/env python3
"""
Permit Scraper - Pull permit data from city/county sources, normalize it,
and optionally feed Airtable (Solar Scout) via Make.com webhook.

Usage:
    python scraper.py config.yml
"""

import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
import pandas as pd
import yaml
from dateutil import parser as date_parser
from parsel import Selector
from pydantic import BaseModel, Field, field_validator
from tenacity import retry, stop_after_attempt, wait_exponential


class PermitRecord(BaseModel):
    """Normalized permit record model."""

    permit_number: str = Field(default="")
    issue_date: Optional[str] = Field(default=None)
    work_class: str = Field(default="")
    description: str = Field(default="")
    address: str = Field(default="")
    city: str = Field(default="")
    state: str = Field(default="")
    zip: str = Field(default="")
    contractor: str = Field(default="")
    owner: str = Field(default="")
    estimated_value: Optional[float] = Field(default=None)
    source_name: str = Field(default="")
    hash_id: str = Field(default="")
    scraped_at: str = Field(default="")

    @field_validator("estimated_value", mode="before")
    @classmethod
    def parse_estimated_value(cls, v: Any) -> Optional[float]:
        """Parse estimated value to float, handling various formats."""
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Remove currency symbols and commas
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned) if cleaned else None
            except ValueError:
                return None
        return None

    @field_validator("issue_date", mode="before")
    @classmethod
    def parse_issue_date(cls, v: Any) -> Optional[str]:
        """Parse issue date to ISO format string."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                parsed = date_parser.parse(v)
                return parsed.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                return v
        return str(v) if v else None

    def generate_hash(self) -> str:
        """Generate unique hash ID for deduplication."""
        unique_str = f"{self.permit_number}|{self.address}|{self.source_name}"
        return hashlib.sha256(unique_str.encode()).hexdigest()[:16]


class Config(BaseModel):
    """Configuration model."""

    days_back: int = Field(default=30)
    geocode: dict = Field(default_factory=lambda: {"enabled": False, "api_key": ""})
    airtable: dict = Field(
        default_factory=lambda: {"enabled": False, "webhook_url": ""}
    )
    sources: list = Field(default_factory=list)


def get_nested_value(data: dict, path: str) -> Any:
    """Get nested value from dict using dot notation path."""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
        if value is None:
            return None
    return value


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_url(
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """Fetch URL with retry logic."""
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response


def scrape_api_source(source: dict, days_back: int) -> list[PermitRecord]:
    """Scrape permits from an API source."""
    records = []
    url = source.get("url", "")
    list_path = source.get("list_path", "")
    mapping = source.get("mapping", {})
    headers = source.get("headers", {})
    params = source.get("params", {})
    source_name = source.get("name", "Unknown")

    if not url:
        print(f"  [WARN] No URL specified for source: {source_name}")
        return records

    try:
        print(f"  Fetching: {url}")
        response = fetch_url(url, headers=headers, params=params)
        data = response.json()

        # Get list of items from response
        items = get_nested_value(data, list_path) if list_path else data
        if not isinstance(items, list):
            items = [items] if items else []

        cutoff_date = datetime.now() - timedelta(days=days_back)

        for item in items:
            if not isinstance(item, dict):
                continue

            # Map fields
            record_data = {
                "source_name": source_name,
                "scraped_at": datetime.now().isoformat(),
            }

            for field_name, json_path in mapping.items():
                value = get_nested_value(item, json_path)
                record_data[field_name] = value

            try:
                record = PermitRecord(**record_data)
                record.hash_id = record.generate_hash()

                # Filter by date if issue_date exists
                if record.issue_date:
                    try:
                        issue_dt = date_parser.parse(record.issue_date)
                        if issue_dt < cutoff_date:
                            continue
                    except (ValueError, TypeError):
                        pass

                records.append(record)
            except Exception as e:
                print(f"  [WARN] Failed to parse record: {e}")

    except httpx.HTTPStatusError as e:
        print(f"  [ERROR] HTTP error for {source_name}: {e}")
    except Exception as e:
        print(f"  [ERROR] Failed to scrape {source_name}: {e}")

    return records


def scrape_html_source(source: dict, days_back: int) -> list[PermitRecord]:
    """Scrape permits from an HTML source."""
    records = []
    url = source.get("url", "")
    row_selector = source.get("row_selector", "")
    fields = source.get("fields", {})
    headers = source.get("headers", {})
    source_name = source.get("name", "Unknown")

    if not url:
        print(f"  [WARN] No URL specified for source: {source_name}")
        return records

    if not row_selector:
        print(f"  [WARN] No row_selector specified for source: {source_name}")
        return records

    try:
        print(f"  Fetching: {url}")
        response = fetch_url(url, headers=headers)
        selector = Selector(text=response.text)

        rows = selector.css(row_selector)
        cutoff_date = datetime.now() - timedelta(days=days_back)

        for row in rows:
            record_data = {
                "source_name": source_name,
                "scraped_at": datetime.now().isoformat(),
            }

            for field_name, css_selector in fields.items():
                # Handle both ::text and ::attr() selectors
                values = row.css(css_selector).getall()
                value = " ".join(v.strip() for v in values if v.strip()) if values else ""
                record_data[field_name] = value

            try:
                record = PermitRecord(**record_data)
                record.hash_id = record.generate_hash()

                # Filter by date if issue_date exists
                if record.issue_date:
                    try:
                        issue_dt = date_parser.parse(record.issue_date)
                        if issue_dt < cutoff_date:
                            continue
                    except (ValueError, TypeError):
                        pass

                records.append(record)
            except Exception as e:
                print(f"  [WARN] Failed to parse record: {e}")

    except httpx.HTTPStatusError as e:
        print(f"  [ERROR] HTTP error for {source_name}: {e}")
    except Exception as e:
        print(f"  [ERROR] Failed to scrape {source_name}: {e}")

    return records


def airtable_upsert(records: list[PermitRecord], webhook_url: str) -> bool:
    """Send records to Airtable via Make.com webhook."""
    if not webhook_url:
        print("[WARN] No webhook URL configured for Airtable")
        return False

    payload = [record.model_dump() for record in records]

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                webhook_url,
                json={"records": payload},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            print(f"[INFO] Successfully sent {len(records)} records to Airtable webhook")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to send to Airtable: {e}")
        return False


def main(config_path: str) -> None:
    """Main entry point."""
    config_file = Path(config_path)

    if not config_file.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)

    print(f"[INFO] Loading config from: {config_path}")
    with open(config_file, "r") as f:
        config_data = yaml.safe_load(f) or {}

    config = Config(**config_data)
    all_records: list[PermitRecord] = []

    print(f"[INFO] Scraping {len(config.sources)} source(s), days_back={config.days_back}")

    for source in config.sources:
        source_name = source.get("name", "Unknown")
        mode = source.get("mode", "api")
        print(f"\n[INFO] Processing source: {source_name} (mode={mode})")

        if mode == "api":
            records = scrape_api_source(source, config.days_back)
        elif mode == "html":
            records = scrape_html_source(source, config.days_back)
        else:
            print(f"  [WARN] Unknown mode '{mode}' for source: {source_name}")
            continue

        print(f"  Found {len(records)} permits")
        all_records.extend(records)

    print(f"\n[INFO] Total permits scraped: {len(all_records)}")

    # Export to CSV
    if all_records:
        df = pd.DataFrame([r.model_dump() for r in all_records])
        csv_path = "permits.csv"
        df.to_csv(csv_path, index=False)
        print(f"[INFO] Exported to {csv_path}")

        # Write Airtable payload JSON for testing
        json_path = "airtable_payload.json"
        with open(json_path, "w") as f:
            json.dump(
                {"records": [r.model_dump() for r in all_records]},
                f,
                indent=2,
                default=str,
            )
        print(f"[INFO] Wrote {json_path} for webhook testing")

        # Send to Airtable if enabled
        if config.airtable.get("enabled"):
            webhook_url = config.airtable.get("webhook_url", "")
            airtable_upsert(all_records, webhook_url)
    else:
        print("[INFO] No permits found, skipping export")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <config.yml>")
        sys.exit(1)

    main(sys.argv[1])
