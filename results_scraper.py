from playwright.sync_api import sync_playwright
import re
import os
import time


from google.oauth2.service_account import Credentials
import gspread

# ====== GOOGLE SHEETS CONFIG ======
SERVICE_ACCOUNT_FILE = "keys.json"        # path to your service account JSON
SHEET_ID = "1GrNsCpFHJ2XtSHw_DgI-_PORGKhBi1tkTSQyALJnKoQ"           # <<< put your sheet ID here

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES,
)
_gclient = gspread.authorize(_creds)
_sheet = _gclient.open_by_key(SHEET_ID).sheet1
# ==================================

# ---------- Generic helpers ----------
def pct_change(curr, prev):
    """Return percentage change (curr vs prev) or None."""
    if curr is None or prev in (None, 0):
        return None
    return (curr - prev) / prev * 100.0

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
        # Keep as raw "% strings", but normalized None where blank
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
    Currently returns a 2-length list in chronological order (older -> newer).
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
                return last_two
    return [None, None]


# ---------- Cash Flow (Cash from Operating Activity) ----------

def extract_recent_cash_from_ops(page):
    """
    Extract most recent and 2nd most recent value for 'Cash from Operating Activity'
    from Cash Flow section. Returns in chronological order (older -> newer).
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

    Returns a 2-length list [oldest, newest] within the slice you care about
    if you adjust it to your preferred ordering (currently you have [latest, prev];
    feel free to keep or tweak).
    """
    try:
        page.wait_for_selector("section#ratios", timeout=10000)
    except Exception:
        return [None, None]

    ratios_section = page.query_selector("section#ratios")
    if not ratios_section:
        return [None, None]

    tables = ratios_section.query_selector_all("table")
    if not tables:
        return [None, None]

    for tbl in tables:
        for tr in tbl.query_selector_all("tr"):
            cells = tr.query_selector_all("td, th")
            if not cells:
                continue

            first_text = cells[0].inner_text().strip().lower()
            if "working capital days" in first_text:
                value_texts = [c.inner_text().strip() for c in cells[1:]]
                if not value_texts:
                    return [None, None]

                # You currently return [latest, prev]; keep as-is if you're happy.
                latest_raw = value_texts[-1]
                prev_raw = value_texts[-2] if len(value_texts) >= 2 else None

                latest = clean_to_float(latest_raw)
                prev = clean_to_float(prev_raw) if prev_raw is not None else None

                return [latest, prev]

    return [None, None]


# ---------- Top Ratios (Market Cap, Stock PE, Industry PE) ----------

def extract_marketcap_stockpe_industrype(page):
    """
    Extract Market Cap, Stock PE, Industry PE from the top ratios block.
    """
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

    # Fallback using positional #top-ratios
    try:
        ratios_list = page.query_selector("#top-ratios")
        if ratios_list:
            items = ratios_list.query_selector_all("li")
            if marketcap is None and len(items) >= 1:
                txt = items[0].inner_text()
                marketcap = extract_first_number(txt)
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
def extract_promoters_last2(page):
    """
    From the Shareholding Pattern → Quarterly tab,
    extract the last 2 promoter shareholding percentages.

    Returns list: [prev, curr]
    Example: [53.44, 48.09]
    If anything unavailable → returns [None, None]
    """

    # Ensure section loads
    try:
        page.wait_for_selector("section#shareholding", timeout=10000)
    except:
        return [None, None]

    section = page.query_selector("section#shareholding")
    if not section:
        return [None, None]

    # Ensure we are on quarterly tab
    quarter_tab = section.query_selector('button.active[data-tab-id="quarterly-shp"]')
    if not quarter_tab:
        try:
            section.query_selector('button[data-tab-id="quarterly-shp"]').click()
            time.sleep(1.5)
        except:
            pass

    # Now get the table
    table = section.query_selector("#quarterly-shp table.data-table")
    if not table:
        return [None, None]

    rows = table.query_selector_all("tbody tr")
    if not rows:
        return [None, None]

    promoters_row = None

    # Find promoters row using FIRST <td> text (not the button)
    for tr in rows:
        first_cell = tr.query_selector("td.text")
        if not first_cell:
            continue

        txt = first_cell.inner_text().strip().lower()
        if "promoters" in txt:
            promoters_row = tr
            break

    if promoters_row is None:
        return [None, None]

    # Extract promoter % values from <td> cells (skip first label cell)
    cells = promoters_row.query_selector_all("td")[1:]
    vals = [c.inner_text().strip() for c in cells]

    # Only numeric-like values
    numeric = []
    for v in reversed(vals):
        m = re.search(r"(\d+\.?\d*)", v)
        if m:
            numeric.append(float(m.group()))
        if len(numeric) == 2:
            break

    if len(numeric) < 2:
        return [None, None]

    # reverse to chronological → [prev, curr]
    return list(reversed(numeric))

def extract_median_pe(page):
    """Navigate to Charts, PE Ratio, then extract the Median PE from the bottom of the graph."""
    try:
        page.click('text="Chart"')
    except:
        return None
    time.sleep(2)

    try:
        page.wait_for_selector("#company-chart-metrics", timeout=5000)
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
            all_buttons = page.query_selector_all("#company-chart-metrics button")
            for btn in all_buttons:
                if "pe" in btn.inner_text().lower():
                    btn.click()
                    break
    except:
        pass
    time.sleep(2)

    try:
        page.wait_for_selector("#chart-legend", timeout=5000)
    except:
        return None
    time.sleep(2)

    labels = page.query_selector_all("#chart-legend > label")
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
def classify_and_append_to_sheet(
    result: dict,
    stock_name: str,
    trade_date_str: str,
    sheet=_sheet
):
    """
    Given the scraped `result` dict and stock metadata, apply filters and
    classification rules. If the stock passes filters, append a row to
    Google Sheets and return True. If filtered out, return False.

    Columns written (suggested header row):

    ["Date",
     "Stock Name",
     "Market Cap (Cr)",
     "Stock PE",
     "Industry/Median PE",
     "Result Type",
     "Valuation",
     "Sales vs last 4",
     "Profit (NP-OI) vs last 4",
     "OPM comment",
     "Borrowings trend",
     "WC days trend",
     "CFO trend",
     "Remarks"]
    """

    sales = result.get("sales") or []
    other_income = result.get("other_income") or []
    net_profit = result.get("net_profit") or []
    opm_percent = result.get("opm_percent") or []
    borrowings = result.get("borrowings") or [None, None]   # [latest, prev]
    cash_from_ops = result.get("cash_from_ops") or [None, None]  # [latest, prev]
    wc_days = result.get("working_capital_days") or [None, None]  # [latest, prev]
    marketcap = result.get("marketcap")
    stock_pe = result.get("stock_pe")
    industry_pe = result.get("industry_pe")
    median_pe = result.get("median_pe")
    promoters_last2 = result.get("promoters_last2") or [None, None]

    prom_prev, prom_curr = promoters_last2

    # Filter rule: If promoters == 0 in either of last 2 quarters → reject stock
    if prom_prev is not None and prom_curr is not None:
        if prom_prev == 0 or prom_curr == 0:
            return False

    # ---------- Derive helper series ----------
    # NP - OtherIncome per quarter (same length as net_profit/other_income)
    profit_core = []
    for npv, oiv in zip(net_profit, other_income):
        if npv is None or oiv is None:
            profit_core.append(None)
        else:
            profit_core.append(npv - oiv)

    curr_sale = sales[-1] if len(sales) >= 1 else None
    last4_sales = sales[-5:-1] if len(sales) >= 5 else sales[:-1]

    curr_profit_core = profit_core[-1] if len(profit_core) >= 1 else None
    last4_profit_core = profit_core[-5:-1] if len(profit_core) >= 5 else profit_core[:-1]

    curr_borrowing = borrowings[0] if len(borrowings) >= 1 else None
    prev_borrowing = borrowings[1] if len(borrowings) >= 2 else None

    curr_wc = wc_days[0] if len(wc_days) >= 1 else None
    prev_wc = wc_days[1] if len(wc_days) >= 2 else None

    curr_cfo = cash_from_ops[0] if len(cash_from_ops) >= 1 else None
    prev_cfo = cash_from_ops[1] if len(cash_from_ops) >= 2 else None

    # baseline PE for valuation rules
    base_pe = industry_pe if industry_pe is not None else median_pe

    # ---------- FILTERS (ignore stock if any fails) ----------

    # 1. If current quarter sales are lower than all past 4 quarters -> ignore
# 1. Reject if current sales < ANY of last 4 quarters
    if curr_sale is not None and last4_sales:
        for s in last4_sales:
            if s is not None and curr_sale < s:
                return False  # reject immediately

    # 2. Reject if current core profit < ANY of last 4 quarters
    if curr_profit_core is not None and last4_profit_core:
        for p in last4_profit_core:
            if p is not None and curr_profit_core < p:
                return False  # reject immediately

    # 3. If market cap < 150 Cr -> ignore
    if marketcap is not None and marketcap < 125:
        return False

    # 4. If borrowing (current) > market cap -> ignore
    if curr_borrowing is not None and marketcap is not None:
        if curr_borrowing > marketcap:
            return False

    # ---------- RESULT TYPE (Good / Best / Normal) ----------

    # Good sales: > 10% above EACH of last 4 quarters (where data exists)
    sales_good = False
    if curr_sale is not None and last4_sales:
        comparisons = []
        for s in last4_sales:
            if s is None or s == 0:
                continue
            pc = pct_change(curr_sale, s)
            if pc is not None:
                comparisons.append(pc > 10.0)
        sales_good = bool(comparisons) and all(comparisons)

    # Good profit: (NP-OI) > 15% vs immediately previous quarter
    profit_good = False
    if curr_profit_core is not None and len(profit_core) >= 2:
        prev_profit_core = profit_core[-2]
        pc = pct_change(curr_profit_core, prev_profit_core)
        profit_good = pc is not None and pc > 15.0

    # Best result criteria:
    #  - OPM% current > all previous 4 values
    #  - Borrowing less than last quarter
    best_margins = False
    if opm_percent and len(opm_percent) >= 2:
        curr_opm = opm_percent[-1]
        prev4_opm = opm_percent[-5:-1] if len(opm_percent) >= 5 else opm_percent[:-1]
        # extract numeric OPM values
        def _opm_to_float(v):
            if v in (None, "", "-"):
                return None
            return clean_to_float(str(v), decimals=None)

        curr_opm_val = _opm_to_float(curr_opm)
        prev4_vals = [_opm_to_float(v) for v in prev4_opm]
        if curr_opm_val is not None and prev4_vals:
            best_margins = all(
                curr_opm_val > v for v in prev4_vals if v is not None
            )

    borrowings_down = (
        curr_borrowing is not None
        and prev_borrowing is not None
        and curr_borrowing < prev_borrowing
    )

    if sales_good and profit_good and best_margins and borrowings_down:
        result_type = "Solid"
    elif sales_good or profit_good:
        result_type = "Best"
    else:
        result_type = "Good"

    # ---------- VALUATION (Over / Fair / Under) ----------

    valuation = "Unknown"
    ref_pe = base_pe
    if stock_pe is not None and ref_pe is not None:
        diff = stock_pe - ref_pe
        if stock_pe > ref_pe:
            valuation = "Over valuation"
        if abs(diff) <= 3:
            valuation = "Fair valuation"
        if stock_pe < ref_pe:
            valuation = "Under valuation"

    # ---------- Trend comments ----------

    # Sales vs last 4 (simple text)
    if sales_good:
        sales_comment = "Sales >10% vs each of last 4"
    else:
        sales_comment = "Sales not strongly higher"

    # Profit vs last 4
    if profit_good:
        profit_comment = "Core profit >15% vs last qtr"
    else:
        profit_comment = "Core profit not strongly higher"

    # OPM comment
    if best_margins:
        opm_comment = "OPM best in 5 qtrs"
    else:
        opm_comment = "OPM not best in 5 qtrs"

    # Borrowings trend
    if curr_borrowing is None or prev_borrowing is None:
        borrow_comment = "N/A"
    elif curr_borrowing < prev_borrowing:
        borrow_comment = "Borrowings lower"
    elif curr_borrowing > prev_borrowing:
        borrow_comment = "Borrowings higher"
    else:
        borrow_comment = "Borrowings flat"

    # Working capital days trend
    if curr_wc is None or prev_wc is None:
        wc_comment = "N/A"
    elif curr_wc < prev_wc:
        wc_comment = "WC days lower (better)"
    elif curr_wc > prev_wc:
        wc_comment = "WC days higher (worse)"
    else:
        wc_comment = "WC days flat"

    # Cash from operations trend
    if curr_cfo is None or prev_cfo is None:
        cfo_comment = "N/A"
    elif curr_cfo > prev_cfo:
        cfo_comment = "CFO increased"
    elif curr_cfo < prev_cfo:
        cfo_comment = "CFO decreased"
    else:
        cfo_comment = "CFO flat"

    # Remarks: combine best/result/valuation briefly
    remarks = f"{result_type} | {valuation}"

    # ---------- Build row & append ----------

    row = [
        trade_date_str,              # Date (e.g. "10-Nov-2025")
        stock_name,                  # Stock name
        marketcap,                   # Market Cap (Cr)
        stock_pe,                    # Stock PE
        base_pe,                     # Industry / Median PE used for valuation
        result_type,                 # Result type
        valuation,                   # Over / Fair / Under
        sales_comment,               # Sales vs last 4
        profit_comment,              # Profit metric vs last 4
        opm_comment,                 # OPM comment
        borrow_comment,              # Borrowings trend
        wc_comment,                  # Working capital days trend
        cfo_comment,                 # Cash from ops trend
        remarks,                     # Final remarks
    ]


    # ----- DUPLICATE CHECK -----
    existing_records = sheet.get_all_values()

    for r in existing_records:
        if len(r) >= 2:
            existing_date = r[0].strip()
            existing_stock = r[1].strip()

            if existing_date == trade_date_str and existing_stock.lower() == stock_name.lower():
                print(f"Duplicate found for {stock_name} on {trade_date_str} — skipping.")
                return False  # Do NOT append the row

    # ----- APPEND IF NOT DUPLICATE -----
    sheet.append_row(row, value_input_option="USER_ENTERED")
    print(f"Added: {stock_name} @ {trade_date_str}")
    return True

# ---------- MAIN SCRAPER FUNCTION (for use from other scripts) ----------

def results_page_scraper(page, stock_name=None, trade_date_str=None):
    """
    Accepts a Playwright `page` that is already on a Screener company URL.
    Navigates to the Quarters tab, scrapes all metrics, logs (optionally) to
    Google Sheets and returns a dict.

    stock_name, trade_date_str are optional but required if you want to
    append to Google Sheets.
    """

    # Ensure we are on the #quarters tab of this company
    base_url = page.url.split("#")[0].rstrip("/")
    quarters_url = f"{base_url}/#quarters"
    if page.url != quarters_url:
        page.goto(quarters_url)
        page.wait_for_load_state("networkidle")

    # ---------- scrape ----------
    quarterly = extract_quarterly_financials(page)
    print("Sales (last 5):", quarterly["sales"])
    print("Other Income (last 5):", quarterly["other_income"])
    print("OPM % (last 5):", quarterly["opm_percent"])
    print("Net Profit (last 5):", quarterly["net_profit"])

    borrowings = extract_recent_borrowings(page)
    print("Borrowings:", borrowings)

    cash_from_ops = extract_recent_cash_from_ops(page)
    print("Cash from Ops:", cash_from_ops)

    wc_days = extract_recent_working_capital_days(page)
    print("Working Capital Days:", wc_days)

    prom_last2 = extract_promoters_last2(page)
    print("Promoters last 2:", prom_last2)
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

    

    # ---------- build result dict using the actual variables we have ----------
    result = {
        **quarterly,                      # expands sales, other_income, opm_percent, net_profit
        "borrowings": borrowings,
        "cash_from_ops": cash_from_ops,
        "working_capital_days": wc_days,
        "marketcap": marketcap,
        "stock_pe": stock_pe,
        "industry_pe": industry_pe,
        "median_pe": median_pe,
        "promoters_last2": prom_last2,
    }
    # ---------- CLEAN STOCK NAME ----------
    if stock_name:
        stock_name = stock_name.split(" | ")[0].strip()
    # ---------- optionally write to Google Sheet ----------
    if stock_name is not None and trade_date_str is not None:
        classify_and_append_to_sheet(
            result=result,
            stock_name=stock_name,
            trade_date_str=trade_date_str,
        )

    print("\n==== FINAL RESULT OBJECT ====")
    for k, v in result.items():
        print(f"{k}: {v}")

    return result


# ---------- Standalone debug harness ----------

if __name__ == "__main__":
    # Quick manual test on a single company
    with sync_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), "user_data")
        browser = p.chromium.launch_persistent_context(user_data_dir, headless=True)
        page = browser.new_page()
        page.goto("https://www.screener.in/company/531802/#quarters")
        page.wait_for_load_state("networkidle")

        results_page_scraper(page)

        browser.close()