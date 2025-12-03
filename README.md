# Environment-Variable

A Python-based web scraper for extracting permit data from the Collin County Self-Service Portal.

## Description

This tool uses Playwright to automate the extraction of permit data from the Collin County EnerGov portal. It scrapes permit information including permit numbers, issue dates, addresses, descriptions, and statuses, then exports the data to a CSV file.

## Requirements

- Python 3.8+
- Chromium browser (installed via Playwright)

## Installation

1. Install the required Python packages:

```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:

```bash
playwright install chromium
```

## Usage

Run the scraper:

```bash
python collin_permits_scraper.py
```

The script will:
1. Navigate to the Collin County Self-Service Portal
2. Search for permits issued in the last 14 days
3. Extract permit data from the results
4. Save the data to `collin_permits.csv`

## Configuration

You can modify the following variables in `collin_permits_scraper.py`:

- `PORTAL`: The URL of the Collin County portal
- `DAYS_BACK`: Number of days to look back for permits (default: 14)

## Output

The script generates a CSV file (`collin_permits.csv`) with the following columns:

- `permit_number`: The permit identifier
- `issue_date`: When the permit was issued
- `address`: Property address
- `description`: Description of the permit
- `status`: Current status of the permit