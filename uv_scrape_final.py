from playwright.sync_api import sync_playwright
import re
import os
import time 
def extract_float(text: str) -> float:
    match = re.search(r"[-+]?\d*\.?\d+", text.replace(",", ""))
    return round(float(match.group()), 2) if match else None
def safe_float(val):
    try:
        v = val.replace(',', '').replace('₹', '').replace('Cr.', '').replace('%','').strip()
        return float(v)
    except:
        return None

def extract_marketcap_stockpe_industrype(page):
    ratios_div = page.query_selector('#top > div.company-info > div.company-ratios')
    marketcap, stock_pe, industry_pe = None, None, None

    if not ratios_div:
        return marketcap, stock_pe, industry_pe

    lines = [l.strip() for l in ratios_div.inner_text().splitlines() if l.strip()]
    last_label = None

    for line in lines:
        low = line.lower()

        if last_label == "market cap":
            marketcap = safe_float(line)
            last_label = None
        elif last_label == "stock p/e":
            stock_pe = safe_float(line)
            last_label = None
        elif last_label == "industry p/e":
            industry_pe = safe_float(line)
            last_label = None

        if low == "market cap":
            last_label = "market cap"
        elif low == "stock p/e":
            last_label = "stock p/e"
        elif low == "industry p/e":
            last_label = "industry p/e"

    return marketcap, stock_pe, industry_pe




import time
import re

def extract_median_pe(page):
    """Navigate to Charts, PE Ratio, then extract the Median PE from the bottom of the graph."""
    
    try:
        page.click('text="Chart"')
    except:
        return None
    time.sleep(2)
    
    try:
        page.wait_for_selector('#company-chart-metrics', timeout=5000)
    except:
        return None
    time.sleep(2)
    
    try:
        pe_button = page.query_selector('button:has-text("PE")')
        if not pe_button:
            pe_button = page.query_selector('button:has-text("PE Ratio")')
        
        if pe_button:
            pe_button.click()
        else:
            all_buttons = page.query_selector_all('#company-chart-metrics button')
            for btn in all_buttons:
                if 'pe' in btn.inner_text().lower():
                    btn.click()
                    break
    except:
        pass
    time.sleep(2)
    
    try:
        page.wait_for_selector('#chart-legend', timeout=5000)
    except:
        return None
    time.sleep(2)
    
    labels = page.query_selector_all('#chart-legend > label')
    median_pe = None
    
    for label in labels:
        txt = label.inner_text()
        if "median" in txt.lower() and "pe" in txt.lower():
            match = re.search(r"(\d+[.,]?\d*)", txt)
            if match:
                try:
                    median_pe = float(match.group(1).replace(",", ""))
                except:
                    pass
            break
    
    return median_pe
    
def extract_recent_working_capital_days(page):
    """Extract the most recent and 2nd most recent value for 'Working Capital Days' from the ratios table."""
    ratios_tables = page.query_selector_all('table')
    wc_row = None

    for table in ratios_tables:
        for row in table.query_selector_all('tr'):
            cells = row.query_selector_all('td,th')
            if cells and "working capital days" in cells[0].inner_text().lower():
                wc_row = cells
                break
        if wc_row: break

    if not wc_row:
        return [None, None]

    # Remove header cell, get numbers only
    values = [c.inner_text().replace(",", "").strip() for c in wc_row[1:]]
    numbers = [float(v) for v in values if v.replace("-", "", 1).replace('.', '', 1).isdigit()]
    wc_days = numbers[-2:] if len(numbers) >= 2 else [None, None]
    wc_days = wc_days[::-1]
    return wc_days


def extract_recent_cash_from_ops(page):
    """Extract the most recent and second most recent value for 'Cash from Operating Activity' from the current cash flow table."""
    cf_tables = page.query_selector_all('table')
    cash_row = None

    for t in cf_tables:
        for row in t.query_selector_all('tr'):
            cells = row.query_selector_all('td,th')
            if cells and "cash from operating activity" in cells[0].inner_text().lower():
                cash_row = cells
                break
        if cash_row: break

    if not cash_row:
        # Return 2 None values if not found
        return [None, None]

    # Remove header cell (label) and get values only
    values = [c.inner_text().replace(",", "").strip() for c in cash_row[1:]]
    # Only numbers, ignore empty/invalid
    numbers = [float(v) for v in values if v.replace('.', '', 1).replace('-', '', 1).isdigit()]
    # get last two (rightmost/most recent)
    cash_from_ops = numbers[-2:] if len(numbers) >= 2 else [None, None]
    # Reverse for [most recent, second most recent]
    cash_from_ops = cash_from_ops[::-1]
    return cash_from_ops



def extract_recent_borrowings_from_balance_sheet(page):
    """Extract the most recent and second most recent quarter values for Borrowings from the current balance sheet table."""
    # Find the first table on the balance sheet section (should be visible as you scrolled there)
    bs_tables = page.query_selector_all('table')
    borrowings_row = None

    # Search all rows for 'Borrowings' label in first column.
    for t in bs_tables:
        for row in t.query_selector_all('tr'):
            cells = row.query_selector_all('td,th')
            if cells and "borrowings" in cells[0].inner_text().lower():
                borrowings_row = cells
                break
        if borrowings_row: break

    if not borrowings_row:
        # Return 2 None values if not found
        return [None, None]

    # Remove header cell (label) and get values only
    values = [c.inner_text().replace(",", "").strip() for c in borrowings_row[1:]]
    # Only numbers, ignore empty/invalid
    numbers = [float(v) for v in values if v.replace('.', '', 1).isdigit()]
    # get last two (rightmost/most recent)
    borrowings = numbers[-2:] if len(numbers) >= 2 else [None, None]
    # Reverse for [most recent, second most recent]
    borrowings = borrowings[::-1]
    return borrowings



def run(playwright):
    user_data_dir = os.path.join(os.getcwd(), "user_data")
    browser = playwright.chromium.launch_persistent_context(user_data_dir, headless=False)
    page = browser.new_page()
    page.goto("https://www.screener.in/company/521216/#quarters")
    page.wait_for_selector('text="Quarterly Results"', timeout=5000)

    # Locate the "Quarterly Results" table
    tables = page.query_selector_all("table")
    qr_table = None
    for tbl in tables:
        thead = tbl.query_selector("thead")
        if thead and "Sep 2025" in thead.inner_text():
            qr_table = tbl
            break

    if not qr_table:
        print("Quarterly Results table not found!")
        browser.close()
        return

    def get_row_values(row_label, convert_float=True):
        for tr in qr_table.query_selector_all("tr"):
            tds = tr.query_selector_all("td")
            if tds and row_label.lower() in tds[0].inner_text().lower():
                vals = [td.inner_text().strip() for td in tds[1:]]
                vals = vals[-5:] # last 5 (rightmost)
                if convert_float:
                    vals = [extract_float(v) if v else None for v in vals]
                return vals
        return [None] * 5

    # Get all required values from the table
    sales = get_row_values("Sales")
    other_income = get_row_values("Other Income")
    opm_percent = get_row_values("OPM %", convert_float=False)
    net_profit = get_row_values("Net Profit")

    # Print and/or save as needed
    print("Sales:", sales)              # List of float
    print("Other Income:", other_income)# List of float
    print("OPM %:", opm_percent)        # List of string with %
    print("Net Profit:", net_profit)    # List of float
    
    # BORROWING 
    page.locator("#balance-sheet > div.flex-row.flex-space-between.flex-gap-16 > div:nth-child(1)").scroll_into_view_if_needed()
    time.sleep(1)

        # === USAGE IN SCRIPT (ensure page is already at balance sheet!) ===
    borrowings = extract_recent_borrowings_from_balance_sheet(page)
    print("Borrowings, most recent/second most recent:", borrowings)

    # cash flow 
    page.locator("#cash-flow > div.flex-row.flex-space-between.flex-gap-16 > div:nth-child(1) > h2").scroll_into_view_if_needed()
    time.sleep(1)
    # === USAGE IN SCRIPT (ensure page is already at cash flow section!) ===
    cash_from_ops = extract_recent_cash_from_ops(page)
    print("Cash from Operating Activity - most recent/second most recent:", cash_from_ops)
    
    ## WORKING CAPITAL DAYS 
    page.locator("#shareholding > div.flex.flex-space-between.flex-wrap.margin-bottom-8.flex-align-center > div:nth-child(1) > h2").scroll_into_view_if_needed()
    time.sleep(1)

    # === USAGE IN SCRIPT (ensure page is at ratios section!) ===
    working_capital_days = extract_recent_working_capital_days(page)
    print("Working Capital Days (most recent, 2nd most recent):", working_capital_days)

    # Usage
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)
    marketcap, stock_pe, industry_pe = extract_marketcap_stockpe_industrype(page)
    print("Market Cap:", marketcap)
    print("Stock PE:", stock_pe)
    print("Industry PE:", industry_pe)  # None if not present

    # Usage
    median_pe = extract_median_pe(page)
    print("Median PE:", median_pe)


    browser.close()

with sync_playwright() as playwright:
    run(playwright)
