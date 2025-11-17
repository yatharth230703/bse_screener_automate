from playwright.sync_api import sync_playwright
import time
import os
from results_scraper import results_page_scraper
## placeholder func ; 
# def right_page (page) --> ## returns the page on which I am supposed to be scrolling 

# def stock_page (page) --> ## operate on the stock page on which I reach 

# def excel (values [] -> list ) --> ## returns a list to be uploaded on excel spreadsheet 
from datetime import datetime
from results_scraper import results_page_scraper
year = datetime.now().year
print("the year is  :" , year)
def parse_date(date_str: str) -> list:
    # Map month names to month numbers
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }

    day_str, month_str = date_str.split()
    day = int(day_str)
    month = months[month_str]

    return [day, month]
def run(playwright):
    
    # Define where to store browser state (cookies, sessions, localStorage)
    for itn in range(0,2):
        user_data_dir = os.path.join(os.getcwd(), "user_data")

        # Launch persistent context instead of a new browser each time
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=False # Set True to run in background
        )

        # Reuse the same context tab
        page = browser.new_page()

        #page.goto("https://www.google.com/")
        page.goto("https://www.screener.in/results/latest/")
        time.sleep(15)
        

        ### october xpath : /html/body/div/div[2]/main/div[1]/nav/a[2]
        ### november xpath : /html/body/div/div[2]/main/div[1]/nav/a[3]
        ### invalid xpath : /html/body/div/div[2]/main/div[1]/nav/a[4] --> just go from 1->not found , last one found is the one to click , just check for existance first 
        final_month_xpath = ""
        for i in range(1,13):
            month_xpath = f"/html/body/div/div[2]/main/div[1]/nav/a[{i}]"
            element = page.query_selector(f"xpath={month_xpath}")
            if(element):
                final_month_xpath = month_xpath
                print("fine ")
            else:
                break
        # now I am outside loop which brings me to the most recent month which is a valid option 
        page.dblclick(f"xpath={final_month_xpath}")
        
        time.sleep(3)
        ### now i've navigated to the most recent month ,I'll navigate now to the most recent date 

        final_day_xpath = ""
        final_prev_day_xpath = ""
        for i in range(1,32):
            day_xpath = f"/html/body/div/div[2]/main/div[1]/nav/a[{i}]"
                          
            prev_day_xpath = f"/html/body/div/div[2]/main/div[1]/nav/a[{i-1}]"
            element = page.query_selector(f"xpath={day_xpath}")
            if(element):
                final_day_xpath = day_xpath
                final_prev_day_xpath = prev_day_xpath
            else:
                break
        
        ## now I have have final day and prev final day , both of which need to be scraped 
        ## I have arrived on desired page ,will start scraping function differently assuming it's on this page 
        #page.dbclick(f"xpath={final_day_xpath}")
        today = page.text_content(f"xpath={final_day_xpath}")
        print(today)

        #page.dbclick(f"xpath={final_prev_day_xpath}")
        prev_day = page.text_content(f"xpath={final_prev_day_xpath}")
        print(prev_day)
        

        if(itn==0):

            print("\n\n====================")
            print("ENTERED itn == 0 BLOCK")
            print("====================\n")

            print(f"Double clicking FINAL DAY XPATH: {final_day_xpath}")
            page.dblclick(f"xpath={final_day_xpath}")
            print("Successfully navigated into today's updates page.")
            time.sleep(3)

            

            for current_page in range(1,40):


                print("\n====================")
                print("STARTING STOCK LOOP")
                print("====================\n")

                for i in range(0, 30):

                    print(f"\n--- Loop iteration i = {i} ---")
                    link_xpath = f"/html/body/div/div[2]/main/div[2]/div[{2*i+1}]/div[1]/a[1]/span" 
                    print(f"Trying to click row with XPATH: {link_xpath}")

                    try:
                        # Check if element exists
                        element = page.query_selector(f"xpath={link_xpath}")
                        if not element:
                            print(f"❌ Element not found: {link_xpath}")
                            continue

                        print("✔ Element FOUND. Now waiting for new page to open...")

                        with browser.expect_page() as new_page_info:
                            page.click(f"xpath={link_xpath}")

                        print("✔ New tab OPENED")

                        new_page = new_page_info.value
                        print("Waiting for new page load state...")
                        new_page.wait_for_load_state()
                        #time.sleep(3)

                        # title
                        page_title = new_page.title()
###### scrape results page
                        #results_page_scraper(new_page)
                        results_page_scraper(
                            new_page,
                            stock_name=page_title,       # or better extract company name
                            trade_date_str=today         # the extracted date string
                        )

                        print(f"--- NEW COMPANY PAGE TITLE: {page_title}")
                        #time.sleep(3)

                        # -------------- Close the tab --------------
                        print("Closing new page/tab...")
                        new_page.close()
                        print("✔ New page closed.")

                        # -------------- Restore old page --------------
                        print("Bringing original page to front...")
                        page.bring_to_front()
                        print("✔ Original page focused.")

                        # Requested: ADD sleep after close
                        print("Sleeping for 3 seconds after closing tab...")
                        #time.sleep(3)

                        # Requested: scroll down 300px
                        print("Scrolling down 300px on original page...")
                        page.evaluate("window.scrollBy(0, 300)")

                        #time.sleep(4)

                    except Exception as e:
                        print("\n⚠⚠⚠ ERROR inside row loop:")
                        print("Error:", e)
                        print("Continuing loop...\n")
                time.sleep(3)



                print("\n====================")
                print("ATTEMPTING NEXT PAGE CLICK")
                print("====================\n")

                try:
                    next_page_xpath = f"/html/body/div/div[2]/main/p/a[{current_page}]"
                    print(f"Clicking NEXT PAGE button XPATH = {next_page_xpath}")
                    page.click(f"xpath={next_page_xpath}")
                    print("✔ Successfully clicked NEXT PAGE button")
                    time.sleep(3)
                except Exception as e:
                    print("The day has been scraped. No NEXT PAGE found.")
                    print("Error:", e)
                    print("Exiting day loop...\n")
                


        else:
            #page.dblclick(prev_day_xpath)
            break


        browser.close()

with sync_playwright() as playwright:
    run(playwright)


