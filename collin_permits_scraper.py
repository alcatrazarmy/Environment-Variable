import traceback
import asyncio
from datetime import date, timedelta
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

PORTAL = "https://collincountytx-energovweb.tylerhost.net/apps/selfservice"
DAYS_BACK = 14
GLOBAL_TIMEOUT = 30000
PERMIT_COLS = ["permit_number","issue_date","address","description","status"]

@retry(stop=stop_after_attempt(2), wait=wait_exponential_jitter(2,5))
async def scrape():
    since = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    rows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await ctx.new_page()
        page.set_default_timeout(45000)

        page.on("console", lambda msg: print(f"[console] {msg.type}:", msg.text()))
        try:
            print("Opening search page…")
            await page.goto(PORTAL + "/#/search", wait_until="domcontentloaded", timeout=GLOBAL_TIMEOUT)
            await page.wait_for_selector('text=Permits', timeout=GLOBAL_TIMEOUT)

            # Click the Permits tab
            for sel in ['[role="tab"]:has-text(\"Permits\")','a:has-text(\"Permits\")','button:has-text(\"Permits\")']:
                loc = page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=5000)
                    break

            # Click Search or Apply
            for sel in ['button:has-text(\"Search\")','button:has-text(\"Apply\")']:
                loc = page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=5000)
                    break

            # Wait for grid
            grid_selectors = [
                'table.k-grid-table',
                'div.ui-grid-canvas div.ui-grid-row',
                'div.ag-center-cols-clipper div.ag-row',
                'table[role=\"grid\"]',
                'table.data-grid'
            ]
            await page.wait_for_selector(','.join(grid_selectors), timeout=GLOBAL_TIMEOUT)

            async def extract_current_page():
                trs = page.locator('table.k-grid-table tbody tr, table.data-grid tbody tr, div.ui-grid-row, div.ag-row')
                n = await trs.count()
                for i in range(n):
                    t = (await trs.nth(i).inner_text()).splitlines()
                    t = [s.strip() for s in t if s.strip()]
                    rows.append(map_row(t))

            def map_row(texts):
                rec = {k: None for k in PERMIT_COLS}
                if texts:
                    rec["permit_number"] = texts[0]
                if len(texts) > 1:
                    rec["address"] = texts[1]
                if len(texts) > 2:
                    rec["description"] = texts[2]
                if len(texts) > 3:
                    rec["status"] = texts[3]
                for s in texts:
                    if "202" in s or "issued" in s.lower():
                        rec["issue_date"] = s
                        break
                return rec

            await extract_current_page()

        except Exception as e:
            await page.screenshot(path="collin_debug.png", full_page=True)
            html = await page.content()
            with open("collin_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Saved collin_debug.png and collin_debug.html")
            raise e
        finally:
            await browser.close()

    df = pd.DataFrame(rows).drop_duplicates()
    df.to_csv("collin_permits.csv", index=False)
    print(f"Wrote {len(df)} rows to collin_permits.csv")

if __name__ == "__main__":
    asyncio.run(scrape())
