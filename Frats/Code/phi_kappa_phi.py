import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait, Select
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

# List of US state codes
STATE_CODES = [
    'AL', 'AK', 'AS', 'AZ', 'AR', 'AA', 'AE', 'AP', 'CA', 'CO', 'CT', 'DE', 'DC', 
    'FM', 'FL', 'GA', 'GU', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 
    'MH', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 
    'NY', 'NC', 'ND', 'MP', 'OH', 'OK', 'OR', 'PW', 'PA', 'PR', 'RI', 'SC', 'SD', 
    'TN', 'TX', 'UM', 'VI', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
]

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_pkp_partial_{timestamp}.csv"
        
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

def select_state(driver, state_code):
    """Select a state from the dropdown and click search"""
    try:
        # Sometimes the page needs a refresh to work properly
        driver.refresh()
        time.sleep(5)
        
        # Wait for and find the state dropdown with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Find the dropdown using a more reliable selector
                select_element = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, 
                    "//select[contains(@class, 'form-control') and contains(@id, 'SearchState')]"))
                )
                
                # Create select object and choose state
                select = Select(select_element)
                
                # Select the state
                select.select_by_value(state_code)
                print(f"Selected state: {state_code}")
                time.sleep(3)  # Wait for dropdown selection to register
                
                # Find and click the search button using a more reliable selector
                search_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, 
                    "//input[@type='submit' and @value='Search' and contains(@class, 'btn-primary')]"))
                )
                
                if search_button:
                    # Scroll the button into view
                    driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
                    time.sleep(1)
                    
                    # Click with JavaScript to ensure the click happens
                    driver.execute_script("arguments[0].click();", search_button)
                    print("Clicked search button")
                    time.sleep(8)  # Increased wait for search results
                    
                    # Verify the results loaded by checking for chapter links
                    chapter_links = WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                        "a.btn.btn-lg.btn-secondary.btn.btn-sm.btn-secondary[href*='chapter-view-search']"))
                    )
                    
                    if chapter_links:
                        print(f"Successfully loaded results for {state_code}")
                        return True
                    else:
                        print("No chapter links found after search")
                        if attempt < max_retries - 1:
                            print("Retrying...")
                            continue
                
                return False
                
            except Exception as retry_e:
                print(f"Attempt {attempt + 1} failed: {str(retry_e)}")
                if attempt < max_retries - 1:
                    print("Retrying after refresh...")
                    driver.refresh()
                    time.sleep(5)
                    continue
                else:
                    return False
        
    except Exception as e:
        print(f"Error selecting state {state_code}: {str(e)}")
        return False
    
    return False

def extract_email_from_chapter(driver, chapter_url, state):
    """Extract email from a chapter page"""
    try:
        # Open chapter URL in new tab
        driver.execute_script(f"window.open('{chapter_url}', '_blank')")
        time.sleep(3)  # Increased wait time
        
        # Switch to the new tab
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(5)  # Increased wait for page load
        
        try:
            # Wait for any loading spinners to disappear (if they exist)
            WebDriverWait(driver, 10).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".loading-spinner"))
            )
        except:
            pass  # If no spinner found, continue
            
        # Find the form element first (this should always be present)
        try:
            form = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
            )
            
            # Get chapter name from the URL if page title not found
            chapter_name = chapter_url.split('id=')[-1]
            try:
                # Try to get a better chapter name from the page
                title_elem = form.find_element(By.CSS_SELECTOR, ".page-title, h1, h2")
                if title_elem:
                    chapter_name = title_elem.text.strip()
            except:
                pass
            
            current_chapter = chapter_name
            
            # Wait for the content to load and find email elements
            time.sleep(2)  # Additional wait
            
            # Try multiple selectors for finding emails
            email_elements = []
            
            # Method 1: Look for Person Email label
            try:
                email_elements = driver.find_elements(By.XPATH, 
                    "//label[contains(text(), 'Person Email')]/following-sibling::span//a[contains(@href, 'mailto:')]")
            except:
                pass
                
            # Method 2: Try finding all mailto links if method 1 failed
            if not email_elements:
                try:
                    email_elements = driver.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
                except:
                    pass
            
            emails_found = []
            for email_elem in email_elements:
                try:
                    email = email_elem.text.strip()
                    # Skip empty or national office emails
                    if email and email != "chapters@phikappaphi.org":
                        emails_found.append(email)
                except:
                    continue
            
            if emails_found:
                for email in emails_found:
                    chapter_data.append({
                        "Chapter": chapter_name,
                        "State": state,
                        "Email": email,
                        "URL": chapter_url  # Added URL for debugging
                    })
                print(f"Found {len(emails_found)} email(s) for {chapter_name}")
            else:
                print(f"No emails found for {chapter_name}")
            
        except Exception as inner_e:
            print(f"Error processing chapter content: {str(inner_e)}")
            
    except Exception as e:
        print(f"Error with tab management: {str(e)}")
    
    finally:
        # Always make sure we close the tab and return to main window
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except:
            # If something goes wrong with closing tabs, refresh the main page
            driver.switch_to.window(driver.window_handles[0])
            driver.refresh()
            time.sleep(5)

def extract_chapter_info():
    """Main function to scrape chapter information"""
    print("Starting Phi Kappa Phi chapter email scraper...")
    global chapter_data, current_chapter, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        
        # Visit the directory page
        url = "https://portal.phikappaphi.org/ChapterListing"
        print(f"Visiting {url}")
        driver.get(url)
        time.sleep(5)
        
        # Process each state
        for state_code in STATE_CODES:
            print(f"\n=== Processing State: {state_code} ===")
            
            # Select state in dropdown
            if not select_state(driver, state_code):
                print(f"Failed to select state {state_code}, skipping...")
                continue
            
            # Find all chapter links
            chapter_links = driver.find_elements(By.CSS_SELECTOR, 
                "a.btn.btn-lg.btn-secondary.btn.btn-sm.btn-secondary[href*='chapter-view-search']")
            
            print(f"Found {len(chapter_links)} chapters in {state_code}")
            
            # Extract URLs before processing (to avoid stale elements)
            chapter_urls = [link.get_attribute('href') for link in chapter_links]
            
            # Process each chapter
            for idx, chapter_url in enumerate(chapter_urls, 1):
                print(f"\nProcessing chapter {idx}/{len(chapter_urls)} in {state_code}")
                extract_email_from_chapter(driver, chapter_url, state_code)
                
            # Save progress after each state
            print(f"\nSaving progress... Found {len(chapter_data)} chapters so far")
            df = pd.DataFrame(chapter_data)
            df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_pkp_progress.csv", index=False)
        
        # Save final results
        if chapter_data:
            output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_pkp.csv"
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
            df.to_csv(output_path, index=False)
            
            print(f"\nScraping complete!")
            print(f"Found {len(df)} unique emails")
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
