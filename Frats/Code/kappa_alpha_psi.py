import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import time
import signal
import sys
import re
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
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_kap_partial_{timestamp}.csv"
        
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

def wait_for_element(driver, by, selector, timeout=10):
    """Wait for element to be present and visible"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return element
    except TimeoutException:
        print(f"Timeout waiting for element: {selector}")
        return None

def filter_chapters(driver):
    """Apply CHAP-UG filter and click search"""
    try:
        print("Applying chapter filter...")
        
        # Wait for filter dropdown to be present
        select_element = wait_for_element(driver, By.CSS_SELECTOR, "select option[value='6']")
        if not select_element:
            return False
        
        # Find parent select element
        select = Select(select_element.find_element(By.XPATH, ".."))
        
        # Select CHAP-UG option
        select.select_by_value("6")
        print("Selected CHAP-UG filter")
        
        # Wait for a moment after selecting filter
        time.sleep(2)
        
        # Click search button
        search_button = wait_for_element(driver, By.CSS_SELECTOR, 
            "button.slds-button.slds-button--brand[data-name='searchBtn']")
        if search_button:
            search_button.click()
            print("Clicked search button")
            # Wait for search results to load
            time.sleep(10)  # Increased wait time for search results
            return True
        else:
            print("Could not find search button")
            return False
        
    except Exception as e:
        print(f"Error applying filter: {str(e)}")
        return False

def extract_chapter_info(text):
    """Extract email and other info from chapter details text"""
    emails = []
    chapter_name = ""
    
    # Extract chapter name
    chapter_match = re.search(r"Chapter Name: (.+?)(?:\n|$)", text)
    if chapter_match:
        chapter_name = chapter_match.group(1).strip()
    
    # Extract email from main info section
    email_match = re.search(r"Email Address: (.+?)(?:\n|$)", text)
    if email_match:
        emails.append(email_match.group(1).strip())
    
    # Extract additional emails from text
    additional_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    emails.extend([email for email in additional_emails if email not in emails])
    
    return chapter_name, emails

def wait_for_loading_complete(driver, timeout=30):
    """Wait for loading spinner to disappear"""
    try:
        # Wait for loading spinner to appear and disappear
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.slds-spinner_container"))
        )
        return True
    except TimeoutException:
        print("Timeout waiting for page to load")
        return False

def click_back_to_results(driver):
    """Click back to results button"""
    try:
        # Look for back button with exact selector
        back_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, 
                "//button[contains(@class, 'slds-button') and .//lightning-primitive-icon and contains(., 'Back to Results')]"))
        )
        
        if back_button:
            print("Found back button, attempting to click...")
            back_button.click()
            time.sleep(8)  # Wait for results page to load
            print("Returned to results page")
            return True
            
        return False
    except Exception as e:
        print(f"Error clicking back button: {str(e)}")
        return False

def process_chapter_page(driver):
    """Process individual chapter page and extract information"""
    try:
        # Wait for page content to load
        time.sleep(5)
        
        # Find both info sections
        info_sections = driver.find_elements(By.CSS_SELECTOR, "div.slds-p-vertical--xx-small.slds-cell-wrap")
        
        combined_text = ""
        for section in info_sections:
            combined_text += section.text + "\n"
        
        # Extract chapter info
        chapter_name, emails = extract_chapter_info(combined_text)
        
        if emails:
            print(f"Found {len(emails)} email(s) for {chapter_name}")
            return chapter_name, emails
        else:
            print(f"No emails found for {chapter_name}")
            return chapter_name, []
            
    except Exception as e:
        print(f"Error processing chapter page: {str(e)}")
        return None, []

def has_next_page(driver):
    """Check if there's a next page and click it if available"""
    try:
        print("\nAttempting to move to next page...")
        
        # First check if the next button exists and is enabled
        next_buttons = driver.find_elements(By.CSS_SELECTOR, 
            "button.slds-button_icon[title='Next Page']")
        
        if not next_buttons:
            print("No next page button found")
            return False
            
        next_button = next_buttons[0]
        if not next_button.is_enabled():
            print("Next page button is disabled")
            return False
            
        print("Found next page button, clicking...")
        next_button.click()
        
        # Wait a long time for the page transition
        print("Waiting for page transition...")
        time.sleep(10)
        
        # Verify we're on a new page by checking if tiles are present
        tiles = driver.find_elements(By.CSS_SELECTOR, 
            "div.slds-size--1-of-1.slds-medium-size--1-of-3")
        
        if len(tiles) > 0:
            print("Page transition successful - found new chapter tiles")
            time.sleep(5)  # Additional wait to ensure everything is loaded
            return True
        else:
            print("Page transition may have failed - no chapter tiles found")
            return False
            
    except Exception as e:
        print(f"Error during page transition: {str(e)}")
        return False

def navigate_to_page(driver, target_page):
    """Navigate to a specific page number"""
    print(f"\nNavigating to page {target_page}...")
    current_page = 1
    
    while current_page < target_page:
        print(f"Currently on page {current_page}, clicking next...")
        if not has_next_page(driver):
            print(f"Failed to reach page {target_page}!")
            return False
        current_page += 1
        time.sleep(10)  # Extra wait between page transitions
    
    print(f"Successfully reached page {target_page}")
    return True

def test_page_turner():
    """Test function that only handles page navigation"""
    print("Testing page navigation...")
    global driver
    
    try:
        driver = setup_driver()
        
        # Visit the directory page
        url = "https://members.kappaalphapsi1911.com/s/public-directory?id=a2nVT000000DOJ4"
        print(f"Visiting {url}")
        driver.get(url)
        time.sleep(10)
        
        # Apply filter and search
        if not filter_chapters(driver):
            print("Failed to apply chapter filter!")
            return
            
        page = 1
        while True:
            print(f"\n=== Current Page: {page} ===")
            
            # Count chapters on current page
            tiles = driver.find_elements(By.CSS_SELECTOR, 
                "div.slds-size--1-of-1.slds-medium-size--1-of-3")
            print(f"Found {len(tiles)} chapters on this page")
            
            # Try to go to next page
            if has_next_page(driver):
                print("Successfully moved to next page")
                page += 1
                time.sleep(5)  # Wait for new page to settle
            else:
                print("No more pages available")
                break
            
            if page > 4:
                print("Reached maximum page limit")
                break
                
    except Exception as e:
        print(f"Error during page navigation test: {str(e)}")
    finally:
        if driver:
            driver.quit()

def scrape_chapter_info():
    """Main function to scrape chapter information"""
    print("Starting Kappa Alpha Psi fraternity email scraper (starting from page 2)...")
    global chapter_data, current_chapter, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        
        # Visit the directory page
        url = "https://members.kappaalphapsi1911.com/s/public-directory?id=a2nVT000000DOJ4"
        print(f"Visiting {url}")
        driver.get(url)
        time.sleep(10)
        
        # Apply filter and search
        if not filter_chapters(driver):
            print("Failed to apply chapter filter!")
            return
            
        # Skip page 1 and go directly to page 2
        print("\nSkipping page 1...")
        if not has_next_page(driver):
            print("Could not navigate to page 2!")
            return
            
        # Start from page 2
        page = 2
        while True:
            print(f"\n=== Processing Page {page} ===")
            time.sleep(5)  # Wait for page content to load
            
            # Find all chapter tiles on current page
            tiles = driver.find_elements(By.CSS_SELECTOR, 
                "div.slds-size--1-of-1.slds-medium-size--1-of-3")
            
            print(f"Found {len(tiles)} chapters on page {page}")
            
            # Process each chapter tile
            for idx, tile in enumerate(tiles, 1):
                try:
                    print(f"\nProcessing chapter {idx} of {len(tiles)} on page {page}")
                    
                    # Re-find the tile to avoid stale element
                    tiles = driver.find_elements(By.CSS_SELECTOR, 
                        "div.slds-size--1-of-1.slds-medium-size--1-of-3")
                    if idx <= len(tiles):
                        tile = tiles[idx - 1]
                    else:
                        print(f"Could not find tile {idx}")
                        continue
                    
                    # Scroll tile into view
                    driver.execute_script("arguments[0].scrollIntoView(true);", tile)
                    time.sleep(2)
                    
                    # Click chapter tile
                    try:
                        tile.click()
                    except:
                        # If click fails, try to re-find and click the element
                        tiles = driver.find_elements(By.CSS_SELECTOR, 
                            "div.slds-size--1-of-1.slds-medium-size--1-of-3")
                        if idx <= len(tiles):
                            tiles[idx - 1].click()
                        else:
                            continue
                    
                    time.sleep(5)  # Wait for chapter page to load
                    
                    # Process chapter page
                    chapter_name, emails = process_chapter_page(driver)
                    current_chapter = chapter_name
                    
                    if chapter_name and emails:
                        # Add each email as a separate entry
                        for email in emails:
                            chapter_data.append({
                                "Chapter": chapter_name,
                                "Email": email,
                                "Page": page
                            })
                            print(f"Added email for {chapter_name}: {email}")
                    
                    # Click back to results with retry
                    retries = 3
                    success = False
                    while retries > 0 and not success:
                        success = click_back_to_results(driver)
                        if not success:
                            print(f"Retry {4-retries}/3 returning to results page...")
                            retries -= 1
                            time.sleep(3)
                    
                    if not success:
                        print("Failed to return to results page after multiple attempts!")
                        # Try to navigate back to the main page and reapply filter
                        driver.get(url)
                        time.sleep(10)
                        if not filter_chapters(driver):
                            print("Could not recover! Saving progress and exiting.")
                            break
                        if not navigate_to_page(driver, page):
                            print("Could not recover! Saving progress and exiting.")
                            break
                        continue
                    
                    # After returning to results, we need to navigate back to the current page
                    print("Returned to results (page 1), navigating back to current page...")
                    if not navigate_to_page(driver, page):
                        print("Failed to return to correct page! Saving progress and exiting.")
                        break
                    
                    # Save progress every 5 chapters
                    if len(chapter_data) % 5 == 0:
                        print(f"\nSaving progress... Found {len(chapter_data)} emails so far")
                        df = pd.DataFrame(chapter_data)
                        df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_kap_progress.csv", index=False)
                    
                    time.sleep(3)  # Wait between chapters
                    
                except Exception as e:
                    print(f"Error processing chapter tile {idx}: {str(e)}")
                    continue
            
            print("\nFinished processing all chapters on current page")
            print("Attempting to move to next page...")
            
            # Try to go to next page with verification
            if has_next_page(driver):
                print(f"Successfully moved to page {page + 1}")
                page += 1
            else:
                print("No more pages available")
                break
            
            if page > 4:
                print("Reached maximum page limit")
                break
        
        # Save final results
        if chapter_data:
            output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_kap.csv"
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
            df.to_csv(output_path, index=False)
            
            print(f"\nScraping complete!")
            print(f"Found {len(df)} unique emails across {page} pages")
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
    # Run the full scraper instead of the test
    scrape_chapter_info()
