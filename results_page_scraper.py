from playwright.sync_api import sync_playwright
import time
import os

def extract_float_2dp(text: str) -> float:
    # Find the numeric part (supports integers or decimals)
    import re
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return None
    return round(float(match.group()), 2) 

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
    page.goto("https://www.screener.in/company/521216/#quarters")

    time.sleep(1)
    
     


    ### values needed to figure out :: 
    #  quarterly result sale -->current + past 4 
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
            if(len(page.text_content(f"xpath={temp}")) == 0):
                print("NULL VALUE ")
                sales[i] = 99999
            else:

                sales[i] = float(page.text_content(f"xpath={temp}"))
            #print(page.text_content(f"xpath={temp}"))
        else:
            continue

    print(sales)  ## ---> sales is done 

    print("this is blank text type : " , len(page.text_content("xpath=/html/body/main/section[4]/div[2]/table/tbody/tr[4]/td[13]")))

    #  other income , profit --> current + past 4 

    netp_minus_otherinc = [1,2,3,4,5]
    for i in range(0,5):
        temp = f"/html/body/main/section[4]/div[2]/table/tbody/tr[10]/td[{sales_xp_last-i}]" ## net p
        #print("this is netp " , page.text_content(f"xpath={temp}"))
        tempo = f"/html/body/main/section[4]/div[2]/table/tbody/tr[5]/td[{sales_xp_last-i}]" ## other income 
        #print("this is other income  : " , page.text_content(f"xpath={tempo}"))
        check = page.query_selector(f"xpath = {temp}")
        #print("this is check : " , check)
        if(check):
            if(len(page.text_content(f"xpath={temp}")) == 0 or page.text_content(f"xpath={tempo}")==0):
                print("NULL VALUE ")
 
                netp_minus_otherinc[i] = 99999
            else:
                a = float(page.text_content(f"xpath={temp}"))
                b = float(page.text_content(f"xpath={tempo}"))
                netp_minus_otherinc[i] = round(a-b,2) 
        else:
            continue

    print(netp_minus_otherinc)


    #  scroll into view in sabki headings 

    #  borrowing 
    page.locator("#balance-sheet > div.flex-row.flex-space-between.flex-gap-16 > div:nth-child(1)").scroll_into_view_if_needed()
    time.sleep(1)

    borrowing_xp = ""
    
    for i in range(0,30):

        temp = f"/html/body/main/section[6]/div[2]/table/tbody/tr[3]/td[{i}]"
        
        check = page.query_selector(f"xpath={temp}")

        if(check):
            borrowing_xp = temp 
    
    borrowing = int(page.text_content(f"xpath={borrowing_xp}"))

    print("borrowing  : " , borrowing)






    #  cash from operating activity : current and last quarter 
    page.locator("#cash-flow > div.flex-row.flex-space-between.flex-gap-16 > div:nth-child(1) > h2").scroll_into_view_if_needed()
    time.sleep(1)

    current_cash_xp = ""
    prev_cash_xp = ""
    for i in range(0,30):
        temp = f"/html/body/main/section[7]/div[2]/table/tbody/tr[1]/td[{i}]"
        tempo = f"/html/body/main/section[7]/div[2]/table/tbody/tr[1]/td[{i-1}]"
        check1 = page.query_selector(f"xpath={temp}")
        check2 = page.query_selector(f"xpath={tempo}")
        if(check1 and check2):
            current_cash_xp = temp 
            prev_cash_xp = tempo 
    
    current_cash=float(page.text_content(f"xpath={current_cash_xp}"))
    prev_cash = float(page.text_content(f"xpath = {prev_cash_xp}"))

    print("current_cash : " , current_cash)
    print("prev_cash : " , prev_cash)




    #  working capital days -->current and last quarter 
    page.locator("#shareholding > div.flex.flex-space-between.flex-wrap.margin-bottom-8.flex-align-center > div:nth-child(1) > h2").scroll_into_view_if_needed()
    time.sleep(3)
    working_capital_xp=""
    prev_wc_xp = ""
    for i in range(0,30):
        temp = f"/html/body/main/section[8]/div[2]/table/tbody/tr[5]/td[{i}]"
        tempo = f"/html/body/main/section[8]/div[2]/table/tbody/tr[5]/td[{i-1}]"
        check1 = page.query_selector(f"xpath={temp}")
        check2 = page.query_selector(f"xpath = {tempo}")
        if(check1 and check2):
            working_capital_xp = temp
            prev_wc_xp = tempo
    
    working_capital = page.text_content(f"xpath={working_capital_xp}")
    prev_wc= page.text_content(f"xpath = {prev_wc_xp}")

    print("working c : " , working_capital)
    print("prev wc : " , prev_wc )



   

    #  marketcap 
    #  stock PE , industry PE  {ADD LATER : MEDIAN PE IN CASE INDUSTRY PE IS NOT GIVEN}
    page.evaluate("window.scrollTo(0, 0)")




    marketcap = extract_float_2dp(page.locator("#top-ratios > li:nth-child(1)").text_content())
    print("this is da marketcap : " ,marketcap)


    stockPE  = extract_float_2dp(page.locator("#top-ratios > li:nth-child(4)").text_content())
    print("this is da stock PE ", stockPE )



    ####### add industry PE comparison later 

    print("charts-->PE ratio --> median PE ")
    page.locator("body > div > div.sub-nav-holder > div > div.sub-nav-tabs > a:nth-child(2)").click()
    page.locator("#company-chart-metrics > button.plausible-event-name\=Chart\+Metric.plausible-event-user\=free.plausible-event-metric\=PE").click()
    medianPE = page.locator("#chart-legend > label:nth-child(2) > span").text_content()
    mpe = extract_float_2dp(medianPE)
    print(mpe)

    # try:
     
    #     print("hi")
    # except Exception as e :
    #     print("Industry pE not found due to : " ,e )

    #     try :
    #         print("charts-->PE ratio --> median PE ")
    #         page.locator("body > div > div.sub-nav-holder > div > div.sub-nav-tabs > a:nth-child(2)").click()
    #         page.locator("#company-chart-metrics > button.plausible-event-name\=Chart\+Metric.plausible-event-user\=free.plausible-event-metric\=PE").click()
    #         medianPE = page.locator("#chart-legend > label:nth-child(2) > span").text_content()
    #         extract_float_2dp(medianPE)
            
    #     except Exception as e:
    #         print("unfixable error : " , e )



    ## perform ops , compile into final list 

    #spreadsheet_rows(final_list)


    ### scroll accordingly 
     

    time.sleep(3)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)


#def resultspage_scrape(page):