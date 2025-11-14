from playwright.sync_api import sync_playwright
import time
import os


def run(playwright):

    user_data_dir = os.path.join(os.getcwd(), "user_data")
    # Launch persistent context instead of a new browser each time
    browser = playwright.chromium.launch_persistent_context(
        user_data_dir,
        headless=False  # Set True to run in background
    )

    # Reuse the same context tab
    page = browser.new_page()

    #page.goto("https://www.google.com/")
    page.goto("https://www.screener.in/company/504180/#quarters")

    time.sleep(3)
    page.evaluate("window.scrollTo(0, 0)")
     


    ### values needed to figure out :: 
    #  quarterly result -->current + past 4 
    #  borrowing 
    #  marketcap 
    #  other income , profit --> current + past 4 
    #  stock PE , industry PE  {ADD LATER : MEDIAN PE IN CASE INDUSTRY PE IS NOT GIVEN}
    #  working capital days -->current and last quarter 
    #  cash from operating activity : current and last quarter 

    ## perform ops , compile into final list 

    spreadsheet_rows(final_list)


    ### scroll accordingly 
     

    time.sleep(3)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)


#def resultspage_scrape(page):