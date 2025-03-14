import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import signal
import sys
from datetime import datetime

# Global variables
chapter_data = []
current_chapter = None
driver = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_opp_partial_{timestamp}.csv"
        
        df = pd.DataFrame(chapter_data)
        df.to_csv(partial_output_path, index=False)
        
        print(f"\nPartial results saved!")
        print(f"Found {len(chapter_data)} chapters with information")
        print(f"Last chapter processed: {current_chapter}")
        print(f"Results saved to: {partial_output_path}")
    
    if driver:
        driver.quit()
    
    sys.exit(0)

def setup_driver():
    """Initialize and configure Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Add user agent
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    # Add stealth script
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def wait_for_element(driver, by, selector, timeout=15):
    """Wait for element to be present and visible"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return element
    except TimeoutException:
        print(f"Timeout waiting for element: {selector}")
        return None

def click_find_button(driver):
    """Click the Find button to initiate search"""
    try:
        print("Clicking Find button...")
        find_button = wait_for_element(driver, By.XPATH, 
            "//input[@type='submit' and @value='Find']")
        
        if find_button:
            find_button.click()
            print("Clicked Find button")
            time.sleep(5)  # Wait for results to load
            return True
        return False
    except Exception as e:
        print(f"Error clicking Find button: {str(e)}")
        return False

def click_show_all(driver):
    """Click the 'Show all 500' link"""
    try:
        print("Looking for 'Show all 500' link...")
        show_all = wait_for_element(driver, By.XPATH, 
            "//a[contains(text(), 'Show all 500')]")
        
        if show_all:
            show_all.click()
            print("Clicked 'Show all 500'")
            time.sleep(8)  # Wait for all results to load
            return True
        return False
    except Exception as e:
        print(f"Error clicking Show all: {str(e)}")
        return False

def extract_chapter_info():
    """Main function to scrape chapter information"""
    print("Starting Omega Psi Phi fraternity email scraper...")
    global chapter_data, current_chapter, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        
        # Visit the directory page
        url = "https://members.oppf.org/OPPMembers/ChapterSearch/ChapterSearch.aspx"
        print(f"Visiting {url}")
        driver.get(url)
        time.sleep(5)
        
        # Click Find button
        if not click_find_button(driver):
            print("Failed to click Find button!")
            return
            
        # Click Show all 500
        if not click_show_all(driver):
            print("Failed to show all results!")
            return
            
        # Wait for the table to load with new structure
        time.sleep(5)
        
        # Find all rows in the table with new structure
        rows = driver.find_elements(By.CSS_SELECTOR, "tr.rgRow, tr.rgAltRow")
        print(f"Found {len(rows)} chapter rows")
        
        # Process each row
        for idx, row in enumerate(rows, 1):
            try:
                # Extract chapter name from first column
                chapter_name = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)").text.strip()
                current_chapter = chapter_name
                
                # Extract both email addresses using the new structure
                email1 = row.find_element(By.CSS_SELECTOR, "td:nth-child(5) a").text.strip()
                email2 = row.find_element(By.CSS_SELECTOR, "td:nth-child(6) a").text.strip()
                
                print(f"Processing chapter {idx}/{len(rows)}: {chapter_name}")
                
                # Add both emails to the dataset
                chapter_data.append({
                    "Chapter": chapter_name,
                    "Email_Type": "Basileus",  # Updated email type to match role
                    "Email": email1
                })
                
                chapter_data.append({
                    "Chapter": chapter_name,
                    "Email_Type": "KRS",  # Updated email type to match role
                    "Email": email2
                })
                
                # Save progress every 25 chapters
                if idx % 25 == 0:
                    print(f"\nSaving progress... Found {len(chapter_data)} emails so far")
                    df = pd.DataFrame(chapter_data)
                    df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_opp_progress.csv", index=False)
                
            except Exception as e:
                print(f"Error processing row {idx}: {str(e)}")
                continue
        
        # Save final results
        if chapter_data:
            output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_opp.csv"
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
            df.to_csv(output_path, index=False)
            
            print(f"\nScraping complete!")
            print(f"Found {len(df)} unique emails across {len(rows)} chapters")
            print(f"Results saved to: {output_path}")
        else:
            print("No chapter data collected!")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        signal_handler(None, None)
    
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    extract_chapter_info()
