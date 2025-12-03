# Permit Scraper v1

A Python-based permit scraper that pulls permits from API or HTML pages, normalizes them to a single schema, deduplicates by address and permit number, and optionally geocodes and pushes data to Airtable.

## Features

- **Multi-source scraping**: Supports both API (JSON) and HTML page sources
- **Schema normalization**: Converts all data to a consistent permit schema
- **Deduplication**: Removes duplicates based on (address, permit_number) hash
- **Date filtering**: Filters permits by configurable days back
- **Geocoding**: Optional address geocoding (stub implementation)
- **Airtable integration**: Optional push to Airtable via webhook

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python scraper.py config.yml
```

## Configuration

Edit `config.yml` to configure:

### Basic Settings

```yaml
output_csv: permits.csv  # Output file path
days_back: 7             # Only include permits from last N days
```

### Data Sources

#### API Source Example

```yaml
sources:
  - name: "city_permits_api"
    mode: api
    url: "https://api.example.com/permits"
    method: GET
    list_path: "data.permits"  # JSON path to permit list
    mapping:
      permit_number: "permitNo"
      issue_date: "issuedDate"
      address: "location.street"
      city: "location.city"
      state: "location.state"
      zip: "location.zip"
      work_class: "type"
      description: "description"
      contractor: "contractor.name"
      owner: "owner.name"
      estimated_value: "value"
```

#### HTML Source Example

```yaml
sources:
  - name: "city_permits_html"
    mode: html
    url: "https://example.com/permits"
    row_selector: "table.permits tr"
    fields:
      permit_number: "td:nth-child(1)::text"
      issue_date: "td:nth-child(2)::text"
      address: "td:nth-child(3)::text"
```

### Optional Features

```yaml
geocode:
  enabled: false

airtable:
  enabled: false
  webhook_url: YOUR_WEBHOOK_URL
```

## Output Schema

The scraper outputs a CSV with the following columns:

| Field | Description |
|-------|-------------|
| permit_number | Unique permit identifier |
| issue_date | Date permit was issued (ISO format) |
| work_class | Type/class of work |
| description | Work description |
| address | Street address |
| city | City name |
| state | State code |
| zip | ZIP/postal code |
| contractor | Contractor name |
| owner | Property owner name |
| estimated_value | Estimated project value |
| source_url | URL of data source |
| source_name | Name of configured source |
| hash_id | SHA1 hash for deduplication |

## License

MIT