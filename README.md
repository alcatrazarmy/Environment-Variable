# Permit Scraper

A Python-based permit data scraper that pulls permit information from city/county sources, normalizes it, and optionally feeds **Airtable (Solar Scout)** via Make.com webhooks.

## Features

- **Multi-source support**: Scrape from API endpoints or HTML pages
- **Data normalization**: Pydantic models ensure consistent data structure
- **Date filtering**: Filter permits by issue date (configurable days_back)
- **Deduplication**: Automatic hash-based deduplication via `hash_id`
- **Retry logic**: Automatic retries with exponential backoff for failed requests
- **CSV export**: Output normalized data to `permits.csv`
- **Airtable integration**: Optional webhook support for Make.com automation

## Quick Start

```bash
# Create and activate virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run scraper
python scraper.py config.yml
```

This outputs `permits.csv` and optionally writes `airtable_payload.json` for Make.com webhook testing.

## Configuration

Edit `config.yml` to configure your data sources:

### Global Settings

```yaml
# Number of days to look back for permits
days_back: 30

# Geocoding settings (for future Google Maps integration)
geocode:
  enabled: false
  api_key: ""

# Airtable/Make.com webhook settings
airtable:
  enabled: false
  webhook_url: "https://hook.make.com/your-webhook-id"
```

### API Source Example

```yaml
sources:
  - name: CityAPIExample
    mode: api
    url: https://api.example.gov/permits
    list_path: results
    headers:
      Authorization: "Bearer YOUR_TOKEN"
    params:
      limit: 100
    mapping:
      permit_number: permitNumber
      issue_date: issueDate
      work_class: workClass
      description: description
      address: address.street
      city: address.city
      state: address.state
      zip: address.zip
      contractor: contractor.name
      owner: owner.name
      estimated_value: estimatedValue
```

### HTML Source Example

```yaml
sources:
  - name: CountyHTMLExample
    mode: html
    url: https://county.example.gov/permits/recent
    row_selector: "table#permits tr.data"
    fields:
      permit_number: "td:nth-child(1)::text"
      issue_date: "td:nth-child(2)::text"
      work_class: "td:nth-child(3)::text"
      description: "td:nth-child(4)::text"
      address: "td:nth-child(5)::text"
      city: "td:nth-child(6)::text"
      state: "td:nth-child(7)::text"
      zip: "td:nth-child(8)::text"
      contractor: "td:nth-child(9)::text"
      owner: "td:nth-child(10)::text"
      estimated_value: "td:nth-child(11)::text"
```

## Airtable Integration

1. Set `airtable.enabled: true` in `config.yml`
2. Set `webhook_url` to your Make.com webhook URL
3. The scraper will POST records to the webhook after scraping

### Make.com Automation Flow

1. **Trigger**: Custom webhook receives JSON payload
2. **Router**: Split by source if needed
3. **Airtable**: Upsert into `Leads` table using `hash_id` as dedupe key
4. **Qualification**: Set `Status=Qualified` based on business rules
5. **Auto-text**: Send Calendly link via Twilio
6. **OpenSolar**: Create placeholder project when qualified

## Output Format

### CSV Fields

| Field | Description |
|-------|-------------|
| `permit_number` | Permit identifier |
| `issue_date` | Date permit was issued (ISO format) |
| `work_class` | Type of work (e.g., Residential, Commercial) |
| `description` | Work description |
| `address` | Street address |
| `city` | City name |
| `state` | State abbreviation |
| `zip` | ZIP code |
| `contractor` | Contractor name |
| `owner` | Property owner name |
| `estimated_value` | Estimated project value |
| `source_name` | Name of the data source |
| `hash_id` | Unique hash for deduplication |
| `scraped_at` | Timestamp when record was scraped |

## Dependencies

- `httpx` - HTTP client with async support
- `parsel` - HTML/XML parsing (CSS selectors)
- `pandas` - Data manipulation and CSV export
- `pydantic` - Data validation and models
- `python-dateutil` - Flexible date parsing
- `tenacity` - Retry logic with backoff
- `pyyaml` - YAML configuration parsing

## Notes

- Geocoding is disabled by default. Enable when ready with a valid Google Maps API key.
- Airtable push is disabled by default. Enable and configure webhook URL when ready.
- For blocked sources, consider adding rotating proxies and respectful request intervals.
- If your city has an official API with Postman collection, import endpoints into `sources` with `mode: api`.