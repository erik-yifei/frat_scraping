import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import signal
import sys

# Global variables to store state
chapter_data = []
current_chapter = None
driver = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\sigep_chapters_partial_{timestamp}.csv"
        
        df = pd.DataFrame(chapter_data)
        df.to_csv(partial_output_path, index=False)
        
        print(f"\nPartial results saved!")
        print(f"Processed {len(chapter_data)} chapters")
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
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def expand_all_rows(driver):
    """Expand all chapter rows on the current page"""
    try:
        # Wait for table to be fully loaded
        time.sleep(2)
        
        # Find all unexpanded rows
        unexpanded_rows = driver.execute_script("""
            return Array.from(document.querySelectorAll('tr:not([data-expanded="true"])'))
                .filter(row => row.querySelector('.footable-toggle'));
        """)
        
        print(f"Found {len(unexpanded_rows)} rows to expand")
        
        # Expand each row with increased delays
        for row in unexpanded_rows:
            try:
                # Scroll row into view before clicking
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", row)
                time.sleep(0.5)  # Wait for scroll
                
                driver.execute_script("""
                    arguments[0].setAttribute('data-expanded', 'true');
                    arguments[0].querySelector('.footable-toggle').click();
                """, row)
                time.sleep(0.5)  # Increased delay between expansions
            except Exception as e:
                print(f"Error expanding row: {str(e)}")
                continue
                
        time.sleep(2)  # Longer wait for all expansions to complete
        return True
    except Exception as e:
        print(f"Error in expand_all_rows: {str(e)}")
        return False

def get_chapter_emails(driver, row):
    """Extract emails from an expanded chapter row"""
    try:
        # Get chapter name
        chapter_name = row.find_element(By.CSS_SELECTOR, "td.ninja_clmn_nm_chapterdesignation b").text
        
        # Get school name
        school = row.find_element(By.CSS_SELECTOR, "td.ninja_clmn_nm_school").text
        
        # Find the detail row that follows this row
        detail_row = driver.execute_script("""
            return arguments[0].nextElementSibling;
        """, row)
        
        if not detail_row:
            print(f"No detail row found for {chapter_name}")
            return None
            
        # Wait for detail row to be fully loaded
        time.sleep(0.5)
        
        # Try multiple methods to get president email
        president_email = ''
        try:
            # Try first method
            president_element = detail_row.find_element(By.CSS_SELECTOR, 
                "tr:nth-child(1) td.ninja_clmn_nm_chapterpresident .softmerge-inner a[href^='mailto:']")
            president_email = president_element.get_attribute('href').replace('mailto:', '')
        except:
            try:
                # Try alternate method
                president_element = detail_row.find_element(By.CSS_SELECTOR, 
                    "tr:nth-child(1) td.ninja_clmn_nm_chapterpresident a[href^='mailto:']")
                president_email = president_element.get_attribute('href').replace('mailto:', '')
            except:
                print(f"Could not find president email for {chapter_name}")
        
        # Try multiple methods to get advisor email
        advisor_email = ''
        try:
            # Try first method
            advisor_element = detail_row.find_element(By.CSS_SELECTOR, 
                "tr:nth-child(2) td.ninja_clmn_nm_avcpresident .softmerge-inner a[href^='mailto:']")
            advisor_email = advisor_element.get_attribute('href').replace('mailto:', '')
        except:
            try:
                # Try alternate method
                advisor_element = detail_row.find_element(By.CSS_SELECTOR, 
                    "tr:nth-child(2) td.ninja_clmn_nm_avcpresident a[href^='mailto:']")
                advisor_email = advisor_element.get_attribute('href').replace('mailto:', '')
            except:
                print(f"Could not find advisor email for {chapter_name}")
        
        # Only return if we found at least one email
        if president_email or advisor_email:
            return {
                'Chapter Name': chapter_name,
                'School': school,
                'President Email': president_email,
                'Advisor Email': advisor_email
            }
        else:
            print(f"No emails found for {chapter_name}")
            return None
        
    except Exception as e:
        print(f"Error extracting emails for {chapter_name if 'chapter_name' in locals() else 'unknown chapter'}: {str(e)}")
        return None

def process_page(driver, page_num):
    """Process all chapters on a single page"""
    print(f"\nProcessing page {page_num}...")
    
    try:
        # Wait for table to load
        wait = WebDriverWait(driver, 10)
        table = wait.until(EC.presence_of_element_located((By.ID, "footable_18473")))
        time.sleep(2)  # Additional wait for table to fully load
        
        # First expand all rows
        if not expand_all_rows(driver):
            print("Failed to expand rows")
            return False
            
        # Get all main chapter rows
        rows = driver.execute_script("""
            return Array.from(document.querySelectorAll('#footable_18473 > tbody > tr:not(.footable-detail-row)'));
        """)
        
        for idx, row in enumerate(rows, 1):
            try:
                # Scroll to row before processing
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", row)
                time.sleep(0.5)
                
                chapter_info = get_chapter_emails(driver, row)
                if chapter_info:
                    chapter_data.append(chapter_info)
                    print(f"✓ Processed {chapter_info['Chapter Name']}")
                    print(f"  President: {chapter_info['President Email']}")
                    print(f"  Advisor: {chapter_info['Advisor Email']}")
                
                time.sleep(1)  # Delay between processing rows
                
            except Exception as e:
                print(f"Error processing row {idx}: {str(e)}")
                continue
        
        time.sleep(2)  # Wait before moving to next page
        return True
        
    except Exception as e:
        print(f"Error processing page {page_num}: {str(e)}")
        return False

def go_to_next_page(driver, current_page):
    """Navigate to the next page of chapters"""
    try:
        # Find the next page number
        next_page = current_page + 1
        
        # Try to find the next page button using JS path
        next_button = driver.execute_script(f"""
            return document.querySelector("#footable_18473 > tfoot > tr > td > div > ul > li.footable-page > a[aria-label='page {next_page}']")
        """)
        
        if next_button:
            driver.execute_script("arguments[0].click();", next_button)
            time.sleep(2)  # Wait for page load
            return True
        return False
        
    except Exception as e:
        print(f"Error navigating to next page: {str(e)}")
        return False

def main():
    print("Starting SigEp chapter email scraper...")
    global chapter_data, current_chapter, driver
    
    # Register the signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        driver.get("https://sigep.org/chapters/")
        
        # Wait for initial page load and table
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "footable_18473")))
        time.sleep(3)
        
        page_num = 1
        while True:
            if not process_page(driver, page_num):
                break
                
            if not go_to_next_page(driver, page_num):
                print("\nReached last page")
                break
                
            page_num += 1
            time.sleep(random.uniform(2, 3))
        
        # Save final results to CSV
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\sigep_chapters.csv"
        df = pd.DataFrame(chapter_data)
        df.to_csv(output_path, index=False)
        
        print(f"\nScraping complete!")
        print(f"Found {len(chapter_data)} chapters")
        print(f"Results saved to: {output_path}")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        signal_handler(None, None)
    
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
