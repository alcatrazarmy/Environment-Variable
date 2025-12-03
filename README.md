# Environment-Variable

## Collin County Permit Scraper

A Python script that scrapes permit data from Collin County, TX Energov web portal.

### Prerequisites

- Python 3.8+
- Chromium browser (installed via Playwright)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install chromium
```

### Usage

Run the scraper:
```bash
python collin_permits_scraper.py
```

The script will:
1. Open the Collin County permit search page
2. Navigate to the Permits tab
3. Extract permit data from the results grid
4. Save results to `collin_permits.csv`

### Output

The script outputs a CSV file with the following columns:
- `permit_number`: The permit identifier
- `issue_date`: Date the permit was issued
- `address`: Property address
- `description`: Permit description
- `status`: Current permit status

### Debug Files

If an error occurs during scraping, the script saves:
- `collin_debug.png`: Screenshot of the page
- `collin_debug.html`: HTML content of the page