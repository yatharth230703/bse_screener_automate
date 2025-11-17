from playwright.sync_api import sync_playwright
import re
import os
import time


# ---------- Generic helpers ----------

def clean_to_float(text: str, decimals: int = 2):
    """Sanitize common Screener formats (₹, Cr., %, commas) and return rounded float or None."""
    if not text:
        return None
    try:
        cleaned = (
            text.replace(",", "")
                .replace("₹", "")
                .replace("Cr.", "")
                .replace("%", "")
                .strip()
        )
        if cleaned == "" or cleaned == "-":
            return None
        value = float(cleaned)
        if decimals is not None:
            return round(value, decimals)
        return value
    except Exception:
        return None


def extract_first_number(text: str, decimals: int = 2):
    """Use regex to extract the first numeric token from a string, like Script 1's extract_float_2dp."""
    if not text:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", text.replace(",", ""))
    if not match:
        return None
    val = float(match.group())
    return round(val, decimals) if decimals is not None else val


def last_n_numeric(values, n=5):
    """
    Given a list of cell strings (e.g. td texts),
    return the last N *numeric-looking* entries in chronological order.
    This is the "keyword-independent last-column" logic inspired by Script 1,
    but done at DOM level like Script 2.
    """
    numeric_vals = []
    for v in reversed(values):
        if not v:
            continue
        # Check if string contains a number
        if re.search(r"-?\d+\.?\d*", v.replace(",", "")):
            numeric_vals.append(v)
        if len(numeric_vals) == n:
            break
    return list(reversed(numeric_vals)) if numeric_vals else [None] * n


# ---------- Quarterly results (Sales, Other Income, OPM%, Net Profit) ----------

def find_row_in_tables(section, label_substring: str):
    """
    Search all tables inside a section for a row whose first cell contains label_substring.
    Returns the list of cell texts (including the label cell) or None.
    """
    tables = section.query_selector_all("table")
    for tbl in tables:
        for tr in tbl.query_selector_all("tr"):
            cells = tr.query_selector_all("td, th")
            if not cells:
                continue
            first_text = cells[0].inner_text().strip().lower()
            if label_substring.lower() in first_text:
                return [c.inner_text().strip() for c in cells]
    return None


def extract_quarterly_financials(page):
    """Extract last 5 quarters of Sales, Other Income, OPM%, Net Profit from the Quarters section."""
    page.wait_for_selector("section#quarters", timeout=10000)
    qr_section = page.query_selector("section#quarters")
    if not qr_section:
        return {
            "sales": [None] * 5,
            "other_income": [None] * 5,
            "opm_percent": [None] * 5,
            "net_profit": [None] * 5,
        }

    # Sales row (from main quarterly table)
    sales_row = find_row_in_tables(qr_section, "sales")
    if sales_row:
        sales_cells = sales_row[1:]  # skip label
        sales_vals_raw = last_n_numeric(sales_cells, n=5)
        sales_vals = [clean_to_float(v) for v in sales_vals_raw]
    else:
        sales_vals = [None] * 5

    # Other Income row
    oi_row = find_row_in_tables(qr_section, "other income")
    if oi_row:
        oi_cells = oi_row[1:]
        oi_vals_raw = last_n_numeric(oi_cells, n=5)
        other_income_vals = [clean_to_float(v) for v in oi_vals_raw]
    else:
        other_income_vals = [None] * 5

    # Net Profit row
    np_row = find_row_in_tables(qr_section, "net profit")
    if np_row:
        np_cells = np_row[1:]
        np_vals_raw = last_n_numeric(np_cells, n=5)
        net_profit_vals = [clean_to_float(v) for v in np_vals_raw]
    else:
        net_profit_vals = [None] * 5

    # OPM % row (often in a separate margins table under the same section)
    opm_row = find_row_in_tables(qr_section, "opm")
    if opm_row:
        opm_cells = opm_row[1:]
        opm_vals_raw = last_n_numeric(opm_cells, n=5)
        # Keep as raw "% strings" (like Script 2), but normalized None where blank
        opm_percent_vals = [v if v not in ("", "-") else None for v in opm_vals_raw]
    else:
        opm_percent_vals = [None] * 5

    return {
        "sales": sales_vals,
        "other_income": other_income_vals,
        "opm_percent": opm_percent_vals,
        "net_profit": net_profit_vals,
    }


# ---------- Balance Sheet (Borrowings) ----------

def extract_recent_borrowings(page):
    """
    Extract most recent and 2nd most recent Borrowings from Balance Sheet section.
    Mixes Script 1's "last columns" idea with Script 2's section anchoring.
    """
    page.wait_for_selector("section#balance-sheet", timeout=10000)
    bs_section = page.query_selector("section#balance-sheet")
    if not bs_section:
        return [None, None]

    tables = bs_section.query_selector_all("table")
    for tbl in tables:
        for tr in tbl.query_selector_all("tr"):
            cells = tr.query_selector_all("td, th")
            if not cells:
                continue
            first = cells[0].inner_text().strip().lower()
            if "borrowings" in first:
                value_cells = [c.inner_text().strip() for c in cells[1:]]
                last_two_raw = last_n_numeric(value_cells, n=2)
                last_two = [clean_to_float(v) for v in last_two_raw]
                # last_two is in chronological order: [most_recent, prev]
                return last_two
    return [None, None]


# ---------- Cash Flow (Cash from Operating Activity) ----------

def extract_recent_cash_from_ops(page):
    """
    Extract most recent and 2nd most recent value for 'Cash from Operating Activity'
    from Cash Flow section.
    """
    page.wait_for_selector("section#cash-flow", timeout=10000)
    cf_section = page.query_selector("section#cash-flow")
    if not cf_section:
        return [None, None]

    tables = cf_section.query_selector_all("table")
    for tbl in tables:
        for tr in tbl.query_selector_all("tr"):
            cells = tr.query_selector_all("td, th")
            if not cells:
                continue
            first = cells[0].inner_text().strip().lower()
            if "cash from operating activity" in first:
                value_cells = [c.inner_text().strip() for c in cells[1:]]
                last_two_raw = last_n_numeric(value_cells, n=2)
                last_two = [clean_to_float(v) for v in last_two_raw]
                return last_two
    return [None, None]


# ---------- Working Capital Days ----------

def extract_recent_working_capital_days(page):
    """
    Extract most recent and previous 'Working Capital Days' from the Ratios section.

    Returns:
        [latest_value, previous_value]  # e.g. [11.0, 0.0]
    """
    # The table is under section#ratios, not shareholding
    try:
        page.wait_for_selector("section#ratios", timeout=10000)
    except Exception:
        return [None, None]

    ratios_section = page.query_selector("section#ratios")
    if not ratios_section:
        return [None, None]

    # There can be multiple tables in this section; we scan them all
    tables = ratios_section.query_selector_all("table")
    if not tables:
        return [None, None]

    for tbl in tables:
        for tr in tbl.query_selector_all("tr"):
            cells = tr.query_selector_all("td, th")
            if not cells:
                continue

            first_text = cells[0].inner_text().strip().lower()
            # Match exactly this row
            if "working capital days" in first_text:
                # All the year values, left→right (oldest→newest)
                value_texts = [c.inner_text().strip() for c in cells[1:]]

                if not value_texts:
                    return [None, None]

                # Latest = last column; previous = second last (if present)
                latest_raw = value_texts[-1]
                prev_raw = value_texts[-2] if len(value_texts) >= 2 else None

                latest = clean_to_float(latest_raw)
                prev = clean_to_float(prev_raw) if prev_raw is not None else None

                # Return in [most recent, previous] order
                return [latest, prev]

    # If row not found
    return [None, None]


# ---------- Top Ratios (Market Cap, Stock PE, Industry PE) ----------

def extract_marketcap_stockpe_industrype(page):
    """
    Extract Market Cap, Stock PE, Industry PE from the top ratios block.
    Combines Script 1's knowledge of #top-ratios with Script 2's text parsing.
    """
    # Try robust text-based parsing under company-ratios
    ratios_div = page.query_selector("#top > div.company-info > div.company-ratios")
    marketcap = stock_pe = industry_pe = None

    if ratios_div:
        lines = [l.strip() for l in ratios_div.inner_text().splitlines() if l.strip()]
        last_label = None
        for line in lines:
            low = line.lower()
            if last_label == "market cap":
                marketcap = clean_to_float(line)
                last_label = None
            elif last_label == "stock p/e":
                stock_pe = clean_to_float(line)
                last_label = None
            elif last_label == "industry p/e":
                industry_pe = clean_to_float(line)
                last_label = None

            if low == "market cap":
                last_label = "market cap"
            elif low == "stock p/e":
                last_label = "stock p/e"
            elif low == "industry p/e":
                last_label = "industry p/e"

    # Fallback using positional #top-ratios like Script 1, if anything missing
    try:
        ratios_list = page.query_selector("#top-ratios")
        if ratios_list:
            items = ratios_list.query_selector_all("li")
            # item 0 usually Market Cap
            if marketcap is None and len(items) >= 1:
                txt = items[0].inner_text()
                marketcap = extract_first_number(txt)
            # item 3 or 4 often Stock P/E depending on layout; try scanning by label
            if stock_pe is None:
                for li in items:
                    if "stock p/e" in li.inner_text().lower():
                        stock_pe = extract_first_number(li.inner_text())
                        break
            if industry_pe is None:
                for li in items:
                    if "industry p/e" in li.inner_text().lower():
                        industry_pe = extract_first_number(li.inner_text())
                        break
    except Exception:
        pass

    return marketcap, stock_pe, industry_pe


# ---------- Median PE from Charts tab ----------


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


# ---------- Main runner combining everything ----------

def run(playwright):
    user_data_dir = os.path.join(os.getcwd(), "user_data")
    browser = playwright.chromium.launch_persistent_context(user_data_dir, headless=False)
    page = browser.new_page()

    # Use the #quarters URL like Script 1 (works fine for our needs)
    page.goto("https://www.screener.in/company/GULFPETRO/#quarters")
    page.wait_for_load_state("networkidle")

    # Quarterly data
    quarterly = extract_quarterly_financials(page)
    print("Sales (last 5):", quarterly["sales"])
    print("Other Income (last 5):", quarterly["other_income"])
    print("OPM % (last 5):", quarterly["opm_percent"])
    print("Net Profit (last 5):", quarterly["net_profit"])

    # Borrowings
    borrowings = extract_recent_borrowings(page)
    print("Borrowings [most recent, prev]:", borrowings)

    # Cash from operating activity
    cash_from_ops = extract_recent_cash_from_ops(page)
    print("Cash from Ops [most recent, prev]:", cash_from_ops)

    # Working capital days
    wc_days = extract_recent_working_capital_days(page)
    print("Working Capital Days [most recent, prev]:", wc_days)

    # Top ratios (Market Cap, Stock PE, Industry PE)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)
    marketcap, stock_pe, industry_pe = extract_marketcap_stockpe_industrype(page)
    print("Market Cap:", marketcap)
    print("Stock PE:", stock_pe)
    print("Industry PE:", industry_pe)

    # Fallback to Median PE if Industry PE missing
    median_pe = None
    if industry_pe is None:
        median_pe = extract_median_pe(page)
        print("Median PE (fallback):", median_pe)
    else:
        print("Median PE not needed, Industry PE present.")

    result = {
        **quarterly,
        "borrowings": borrowings,
        "cash_from_ops": cash_from_ops,
        "working_capital_days": wc_days,
        "marketcap": marketcap,
        "stock_pe": stock_pe,
        "industry_pe": industry_pe,
        "median_pe": median_pe,
    }

    print("\n==== FINAL RESULT OBJECT ====")
    for k, v in result.items():
        print(f"{k}: {v}")

    browser.close()
    return result


if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)