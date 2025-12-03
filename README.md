# Environment-Variable

A Python script for scraping permit data and syncing it with Airtable.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set the required environment variables:
   ```bash
   export AIRTABLE_API_KEY="your_api_key"
   export AIRTABLE_BASE_ID="your_base_id"
   ```

3. Optionally, set the table reference (defaults to "Permits"):
   ```bash
   export AIRTABLE_TABLE_ID="your_table_id"
   # or
   export AIRTABLE_TABLE_NAME="your_table_name"
   ```

## Usage

Run the scraper:
```bash
python scrape_permits.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AIRTABLE_API_KEY` | Yes | Your Airtable API key |
| `AIRTABLE_BASE_ID` | Yes | The ID of your Airtable base |
| `AIRTABLE_TABLE_ID` | No | The ID of the target table (preferred) |
| `AIRTABLE_TABLE_NAME` | No | The name of the target table (fallback) |

If neither `AIRTABLE_TABLE_ID` nor `AIRTABLE_TABLE_NAME` is set, the script defaults to a table named "Permits".