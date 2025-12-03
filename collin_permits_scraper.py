import asyncio
from datetime import date, timedelta

import pandas as pd
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

# Collin County Self-Service portal
PORTAL = "https://collincountytx-energovweb.tylerhost.net/apps/selfservice"
DAYS_BACK = 14
GRID_TIMEOUT_MS = 15000

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(1,4))
async def run():
    since = date.today() - timedelta(days=DAYS_BACK)
    rows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        # 1) Open portal home
        await page.goto(PORTAL, wait_until="domcontentloaded")

        # 2) Navigate to Search
        # Most EnerGov portals have a "Search" tile or a "Search" link in the header
        # Try common selectors first, then fallback
        SELS = [
            'a:has-text("Search")',
            'button:has-text("Search")',
            'a[ui-sref="search"]',
            'a[href*="#/search"]'
        ]
        clicked = False
        for s in SELS:
            if await page.locator(s).first.is_visible():
                await page.locator(s).first.click()
                clicked = True
                break
        if not clicked:
            # some portals show tiles with aria labels
            await page.locator('css=[aria-label*="Search"]').first.click()

        await page.wait_for_timeout(1500)

        # 3) Select the Permits tab in the search view
        PTABS = [
            'a:has-text("Permits")',
            'button:has-text("Permits")',
            'li:has-text("Permits")'
        ]
        for s in PTABS:
            if await page.locator(s).first.is_visible():
                await page.locator(s).first.click()
                break
        await page.wait_for_timeout(1200)

        # 4) Optional: set date filter to last N days if filter controls exist
        # Many EnerGov UIs have a "Issued Date From / To" or "Date Applied From/To"
        for label in ["Issue Date From", "Issued From", "Applied From", "Date From"]:
            loc = page.get_by_label(label)
            if await loc.count():
                await loc.fill(since.isoformat())
                break

        # 5) Submit / Search
        for s in ['button:has-text("Search")', 'button[ng-click*="search"]', 'button:has-text("Apply")']:
            if await page.locator(s).first.is_visible():
                await page.locator(s).first.click()
                break

        # 6) Wait for results grid
        # Typical grid table role=grid or table.data-grid
        await page.wait_for_selector('table[role="grid"], table.data-grid, div.ui-grid-render-container', timeout=GRID_TIMEOUT_MS)

        # 7) Extract rows across pages
        async def extract_current_page():
            # Try plain table first
            if await page.locator('table[role="grid"]').count():
                trs = page.locator('table[role="grid"] tbody tr')
            elif await page.locator('table.data-grid').count():
                trs = page.locator('table.data-grid tbody tr')
            else:
                # Angular ui-grid virtual rows
                trs = page.locator('div.ui-grid-canvas div.ui-grid-row')

            n = await trs.count()
            for i in range(n):
                row = trs.nth(i)
                # Extract common columns by header order; adjust if needed
                raw_lines = (await row.inner_text()).splitlines()
                texts = [line.strip() for line in raw_lines if line.strip()]
                # Heuristic mapping
                record = {
                    "permit_number": None,
                    "issue_date": None,
                    "address": None,
                    "description": None,
                    "status": None
                }
                # Try to map by patterns
                for t in texts:
                    parts = t.split()
                    if not record["permit_number"] and any(k in t.lower() for k in ["permit", "prmt"]):
                        record["permit_number"] = parts[-1] if parts else t
                    if not record["issue_date"] and any(k in t.lower() for k in ["issued", "issue date", "date issued"]):
                        record["issue_date"] = parts[-1] if parts else t
                # Fallback: positional
                if not record["permit_number"] and texts:
                    record["permit_number"] = texts[0]
                if len(texts) >= 2 and not record["address"]:
                    record["address"] = texts[1]
                if len(texts) >= 3 and not record["description"]:
                    record["description"] = texts[2]
                if len(texts) >= 4 and not record["status"]:
                    record["status"] = texts[3]
                rows.append(record)

        # Loop pages if paginator present
        while True:
            await extract_current_page()
            next_btn = page.locator('button[aria-label*="Next"], a[aria-label*="Next"], button:has-text("Next")').first
            if await next_btn.is_enabled():
                await next_btn.click()
                await page.wait_for_timeout(800)
            else:
                break

        await browser.close()

    # Save CSV
    df = pd.DataFrame(rows).drop_duplicates()
    df.to_csv("collin_permits.csv", index=False)
    print(f"Wrote {len(df)} rows to collin_permits.csv")

if __name__ == "__main__":
    asyncio.run(run())
