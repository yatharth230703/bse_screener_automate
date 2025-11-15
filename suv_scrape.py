import asyncio
from playwright.async_api import async_playwright

async def fetch_screener_quarterly(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        # Find the Quarterly Results table
        table_handle = await page.query_selector('text="Quarterly Results"')
        if not table_handle:
            # Try alternate selector (sometimes it's inside a section with heading)
            table_handle = await page.query_selector('section:has-text("Quarterly Results")')
        if not table_handle:
            print("Table not found")
            await browser.close()
            return

        # Find the actual Results Table (usually the next table after the heading)
        tables = await page.query_selector_all('table')
        if not tables:
            print("No tables found")
            await browser.close()
            return
        
        # The correct table is the one with quarter names like 'Sep 2025', etc.
        # Let's extract all tables and pick the one containing 'Sales'
        target_table = None
        for t in tables:
            html_content = await t.inner_html()
            if "Sales" in html_content and "Other Income" in html_content:
                target_table = t
                break
        if not target_table:
            print("Target table not found")
            await browser.close()
            return

        # Fetch table rows
        rows = await target_table.query_selector_all('tr')
        results = {}
        # These labels are consistent for all screener stock pages
        wanted_labels = ['Sales', 'Other Income', 'OPM %', 'Net Profit']
        wanted_rows = {}
        for label in wanted_labels:
            for row in rows:
                cell = await row.query_selector('td')
                if cell:
                    text = await cell.inner_text()
                    if label in text:
                        cells = await row.query_selector_all('td')
                        values = []
                        for c in cells[1:]:  # skip the label cell
                            values.append(await c.inner_text())
                        wanted_rows[label] = values
                        break

        # Now get the most recent 5 quarters' values for each metric
        # Assuming all rows have matching columns for quarters
        most_recent_5 = {}
        for label in wanted_labels:
            data = wanted_rows.get(label, [])
            most_recent_5[label] = data[-5:] if len(data) >= 5 else data

        await browser.close()
        return most_recent_5

# Example usage:
url = "https://www.screener.in/company/524564/#quarters"  # Replace with any screener stock page
data = asyncio.run(fetch_screener_quarterly(url))
print(data)
