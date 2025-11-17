from playwright.sync_api import sync_playwright
import re
import os
import time

def safe_float_extract(text: str) -> float:
    """Unified float extraction: removes symbols, commas, converts to float, rounds to 2dp."""
    if not text:
        return None
    try:
        cleaned = text.replace(',', '').replace('₹', '').replace('Cr.', '').replace('%', '').strip()
        return round(float(cleaned), 2)
    except:
        return None


def extract_quarterly_financials(page):
    """Extract Sales, Other Income, OPM%, Net Profit for last 5 quarters from Quarterly Results section."""
    # Anchor to the correct section
    page.wait_for_selector('section#quarters', timeout=10000)
    qr_section = page.query_selector('section#quarters')
    
    if not qr_section:
        print("⚠ Quarterly Results section not found")
        return {
            "sales": [None]*5,
            "other_income": [None]*5,
            "opm_percent": [None]*5,
            "net_profit": [None]*5
        }
    
    # Get the table under this section
    qr_table = qr_section.query_selector('table')
    if not qr_table:
        print("⚠ Quarterly Results table not found")
        return {
            "sales": [None]*5,
            "other_income": [None]*5,
            "opm_percent": [None]*5,
            "net_profit": [None]*5
        }
    
    def get_row_values(row_label):
        """Extract last 5 quarter values for a given row label."""
        for tr in qr_table.query_selector_all('tr'):
            cells = tr.query_selector_all('td, th')
            if cells and row_label.lower() in cells[0].inner_text().lower():
                # Get all cell values (skip first which is label)
                vals = [c.inner_text().strip() for c in cells[1:]]
                # Filter out non-quarter columns (TTM, consolidated, etc.)
                # Take rightmost 5 numeric values
                numeric_vals = []
                for v in reversed(vals):
                    if v and (v.replace('.', '').replace('-', '').replace('%', '').replace(',', '').strip().isdigit() or 
                              re.search(r'-?\d+\.?\d*', v)):
                        numeric_vals.append(v)
                    if len(numeric_vals) == 5:
                        break
                return numeric_vals[::-1]  # reverse to get chronological order
        return [None] * 5
    
    sales = [safe_float_extract(v) for v in get_row_values("Sales")]
    other_income = [safe_float_extract(v) for v in get_row_values("Other Income")]
    opm_raw = get_row_values("OPM %")
    opm_percent = [v if v else None for v in opm_raw]  # Keep as string with %
    net_profit = [safe_float_extract(v) for v in get_row_values("Net Profit")]
    
    return {
        "sales": sales,
        "other_income": other_income,
        "opm_percent": opm_percent,
        "net_profit": net_profit
    }


def extract_balance_sheet_borrowings(page):
    """Extract most recent and 2nd most recent Borrowings from Balance Sheet section."""
    page.wait_for_selector('section#balance-sheet', timeout=10000)
    bs_section = page.query_selector('section#balance-sheet')
    
    if not bs_section:
        return [None, None]
    
    bs_table = bs_section.query_selector('table')
    if not bs_table:
        return [None, None]
    
    for row in bs_table.query_selector_all('tr'):
        cells = row.query_selector_all('td, th')
        if cells and "borrowings" in cells[0].inner_text().lower():
            values = [c.inner_text().replace(",", "").strip() for c in cells[1:]]
            numbers = [safe_float_extract(v) for v in values if safe_float_extract(v) is not None]
            if len(numbers) >= 2:
                return [numbers[-1], numbers[-2]]  # [most recent, 2nd most recent]
            return [None, None]
    
    return [None, None]


def extract_cashflow_operations(page):
    """Extract most recent and 2nd most recent Cash from Operating Activity."""
    page.wait_for_selector('section#cash-flow', timeout=10000)
    cf_section = page.query_selector('section#cash-flow')
    
    if not cf_section:
        return [None, None]
    
    cf_table = cf_section.query_selector('table')
    if not cf_table:
        return [None, None]
    
    for row in cf_table.query_selector_all('tr'):
        cells = row.query_selector_all('td, th')
        if cells and "cash from operating activity" in cells[0].inner_text().lower():
            values = [c.inner_text().replace(",", "").strip() for c in cells[1:]]
            numbers = [safe_float_extract(v) for v in values if safe_float_extract(v) is not None]
            if len(numbers) >= 2:
                return [numbers[-1], numbers[-2]]
            return [None, None]
    
    return [None, None]


def extract_working_capital_days(page):
    """Extract most recent and 2nd most recent Working Capital Days from shareholding ratios."""
    print("\n🔍 Extracting Working Capital Days...")
    
    # Wait for shareholding section
    try:
        page.wait_for_selector('section#shareholding', timeout=10000)
        print("✓ Shareholding section found")
    except Exception as e:
        print(f"✗ Shareholding section not found: {e}")
        return [None, None]
    
    sh_section = page.query_selector('section#shareholding')
    if not sh_section:
        print("✗ Could not query shareholding section")
        return [None, None]
    
    # Find all tables in this section
    sh_tables = sh_section.query_selector_all('table')
    print(f"Found {len(sh_tables)} table(s) in shareholding section")
    
    if not sh_tables:
        print("✗ No tables found in shareholding section")
        return [None, None]
    
    # Search through all tables for Working Capital Days row
    for table_idx, sh_table in enumerate(sh_tables):
        print(f"\nSearching table {table_idx + 1}...")
        
        for row in sh_table.query_selector_all('tr'):
            cells = row.query_selector_all('td, th')
            if not cells:
                continue
            
            first_cell_text = cells.inner_text().lower().strip()
            
            # Match "Working Capital Days" or "Working capital days" or "working capital"
            if "working capital" in first_cell_text and "days" in first_cell_text:
                print(f"✓ Found row: '{cells.inner_text()}'")
                
                # Extract all cell values except first (label)
                values = []
                for c in cells[1:]:
                    val_text = c.inner_text().replace(",", "").strip()
                    if val_text:
                        print(f"  Cell value: '{val_text}'")
                        values.append(val_text)
                
                # Convert to floats, filtering out non-numeric
                numbers = []
                for v in values:
                    extracted = safe_float_extract(v)
                    if extracted is not None:
                        numbers.append(extracted)
                
                print(f"✓ Extracted numbers: {numbers}")
                
                # Get last 2 values (most recent, 2nd most recent)
                if len(numbers) >= 2:
                    result = [numbers[-1], numbers[-2]]
                    print(f"✓ Working Capital Days (recent, prev): {result}")
                    return result
                elif len(numbers) == 1:
                    result = [numbers[-1], None]
                    print(f"⚠ Only 1 value found: {result}")
                    return result
                else:
                    print("✗ No numeric values found in row")
                    return [None, None]
    
    print("✗ Working Capital Days row not found in any table")
    return [None, None]



def extract_top_ratios(page):
    """Extract Market Cap, Stock PE, Industry PE from top ratios section."""
    page.wait_for_selector('#top .company-ratios', timeout=10000)
    ratios_div = page.query_selector('#top .company-ratios')
    
    marketcap, stock_pe, industry_pe = None, None, None
    
    if not ratios_div:
        return marketcap, stock_pe, industry_pe
    
    lines = [l.strip() for l in ratios_div.inner_text().splitlines() if l.strip()]
    last_label = None
    
    for line in lines:
        low = line.lower()
        
        # Check if previous line was a label
        if last_label == "market cap":
            marketcap = safe_float_extract(line)
            last_label = None
        elif last_label == "stock p/e":
            stock_pe = safe_float_extract(line)
            last_label = None
        elif last_label == "industry p/e":
            industry_pe = safe_float_extract(line)
            last_label = None
        
        # Check if current line is a label
        if low == "market cap":
            last_label = "market cap"
        elif low == "stock p/e":
            last_label = "stock p/e"
        elif low == "industry p/e":
            last_label = "industry p/e"
    
    return marketcap, stock_pe, industry_pe


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


def run(playwright):
    user_data_dir = os.path.join(os.getcwd(), "user_data")
    browser = playwright.chromium.launch_persistent_context(user_data_dir, headless=False)
    page = browser.new_page()
    
    # Navigate to company page
    page.goto("https://www.screener.in/company/521216/")
    page.wait_for_load_state('networkidle')
    
    # Extract all financial data
    print("\n📊 Extracting Quarterly Financials...")
    quarterly_data = extract_quarterly_financials(page)
    print(f"✓ Sales: {quarterly_data['sales']}")
    print(f"✓ Other Income: {quarterly_data['other_income']}")
    print(f"✓ OPM %: {quarterly_data['opm_percent']}")
    print(f"✓ Net Profit: {quarterly_data['net_profit']}")
    
    print("\n📊 Extracting Balance Sheet...")
    borrowings = extract_balance_sheet_borrowings(page)
    print(f"✓ Borrowings (recent, prev): {borrowings}")
    
    print("\n📊 Extracting Cash Flow...")
    cash_from_ops = extract_cashflow_operations(page)
    print(f"✓ Cash from Ops (recent, prev): {cash_from_ops}")
    
    print("\n📊 Extracting Working Capital...")
    wc_days = extract_working_capital_days(page)
    print(f"✓ Working Capital Days (recent, prev): {wc_days}")
    
    print("\n📊 Extracting Top Ratios...")
    marketcap, stock_pe, industry_pe = extract_top_ratios(page)
    print(f"✓ Market Cap: {marketcap}")
    print(f"✓ Stock PE: {stock_pe}")
    print(f"✓ Industry PE: {industry_pe}")
    
    # If Industry PE is missing, get Median PE
    median_pe = None
    if industry_pe is None:
        print("\n📊 Industry PE not found, extracting Median PE from chart...")
        median_pe = extract_median_pe(page)
        print(f"✓ Median PE: {median_pe}")
    
    # Return structured data
    result = {
        **quarterly_data,
        "borrowings": borrowings,
        "cash_from_ops": cash_from_ops,
        "working_capital_days": wc_days,
        "marketcap": marketcap,
        "stock_pe": stock_pe,
        "industry_pe": industry_pe,
        "median_pe": median_pe
    }
    
    print("\n" + "="*50)
    print("✅ EXTRACTION COMPLETE")
    print("="*50)
    
    browser.close()
    return result


with sync_playwright() as playwright:
    data = run(playwright)
