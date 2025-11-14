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
    page.goto("https://www.screener.in/company/530439/#quarters")

    time.sleep(3)
    
     


    ### values needed to figure out :: 
    #  quarterly result -->current + past 4 
    sales = [1,2,3,4,5]

    ## instead of this do : last se minus 4 tak till available 
    sales_xp_last = 0
    for i in range(0,30):
        curr_xp = f"/html/body/main/section[4]/div[2]/table/tbody/tr[1]/td[{i}]"

        #print("this is curr xp : " , curr_xp)
        check = page.query_selector(f"xpath={curr_xp}")
        #print("this is check : " , check)
        if(check):
            sales_xp_last = i
            # print(sales_xp_last)
        
            ##end mil gya 
    

    for i in range(0,5):
        #print("this is simple I " , i)
        temp = f"/html/body/main/section[4]/div[2]/table/tbody/tr[1]/td[{sales_xp_last-i}]"
        #print("## this is temp : : " , temp)
        check = page.query_selector(f"xpath = {temp}")
        #print("this is check : " , check)
        if(check):
            sales[i] = page.text_content(f"xpath={temp}")
            #print(page.text_content(f"xpath={temp}"))

    print(sales)


    

    #  borrowing 
   

    #  marketcap 
    page.evaluate("window.scrollTo(0, 0)")
    #  other income , profit --> current + past 4 
    #  stock PE , industry PE  {ADD LATER : MEDIAN PE IN CASE INDUSTRY PE IS NOT GIVEN}
    #  working capital days -->current and last quarter 
    #  cash from operating activity : current and last quarter 

    ## perform ops , compile into final list 

    #spreadsheet_rows(final_list)


    ### scroll accordingly 
     

    time.sleep(3)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)


#def resultspage_scrape(page):