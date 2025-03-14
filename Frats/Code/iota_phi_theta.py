import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
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
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_ipt_partial_{timestamp}.csv"
        
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

def find_and_click_dropdowns(driver):
    """Find and click all dropdown arrows to reveal chapter lists"""
    print("Looking for dropdown arrows...")
    
    # List of selectors for dropdown arrows
    dropdown_selectors = [
        "div.uVccjd[role='checkbox']",  # Main selector from example
        "div.HzV7m-pbTTYe-KoToPc-ornU0b-hFsbo[role='checkbox']",  # Full class name
        "div[jscontroller='EcW08c'][role='checkbox']",  # Using jscontroller
        "div.uVccjd.HzV7m-pbTTYe-KoToPc-ornU0b-hFsbo"  # Combined classes
    ]
    
    dropdowns_clicked = 0
    for selector in dropdown_selectors:
        try:
            dropdowns = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"Found {len(dropdowns)} potential dropdowns using selector: {selector}")
            
            for dropdown in dropdowns:
                try:
                    if dropdown.is_displayed():
                        # Check if not already expanded
                        if dropdown.get_attribute("aria-checked") != "true":
                            # Scroll into view
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", dropdown)
                            time.sleep(1)
                            
                            # Click the dropdown
                            dropdown.click()
                            print("Clicked dropdown arrow")
                            dropdowns_clicked += 1
                            time.sleep(1)  # Wait for animation
                except Exception as e:
                    print(f"Error clicking dropdown: {str(e)}")
                    continue
        except Exception as e:
            print(f"Error with dropdown selector {selector}: {str(e)}")
            continue
    
    print(f"Clicked {dropdowns_clicked} dropdown arrows")
    return dropdowns_clicked > 0

def find_chapter_links(driver):
    """Find all chapter links after expanding dropdowns"""
    print("Looking for chapter links...")
    
    # Exact selector for chapter names
    chapter_selector = "div.HzV7m-pbTTYe-ibnC6b-V67aGc div.suEOdc"
    
    try:
        chapters = driver.find_elements(By.CSS_SELECTOR, chapter_selector)
        print(f"Found {len(chapters)} chapters")
        return chapters
    except Exception as e:
        print(f"Error finding chapters: {str(e)}")
        return []

def extract_email_from_popup(driver):
    """Extract email from popup content"""
    try:
        # Wait for popup to appear and look for email link using exact selector
        wait = WebDriverWait(driver, 3)
        email_container = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "div.qqvbed-p83tee div.qqvbed-p83tee-lTBxed a[href^='mailto:']"
        )))
        
        # Extract email from href attribute
        email = email_container.get_attribute("href").replace("mailto:", "")
        return email
            
    except TimeoutException:
        print("No email found in popup")
        return None
    except Exception as e:
        print(f"Error extracting email: {str(e)}")
        return None

def click_back_arrow(driver):
    """Click the back arrow to return to chapter list"""
    try:
        # Use exact selector for back button
        back_button = driver.find_element(By.CSS_SELECTOR, 
            "div.U26fgb.mUbCce.p9Nwte.HzV7m-tJHJj-LgbsSe.qqvbed-a4fUwd-LgbsSe[aria-label='Back']")
        
        if back_button.is_displayed():
            back_button.click()
            print("Clicked back arrow")
            time.sleep(0.3)  # Short wait after clicking back
            return True
            
    except Exception as e:
        print(f"Error clicking back button: {str(e)}")
        return False
    
    return False

def scrape_chapter_info():
    """Main function to scrape chapter information"""
    print("Starting Iota Phi Theta fraternity email scraper...")
    global chapter_data, current_chapter, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        
        # Visit the Google Maps viewer page
        url = "https://www.google.com/maps/d/u/0/viewer?mid=1ZWdF8D3QxpTDnxXZILM7GxY8lGWL8oY"
        print(f"Visiting {url}")
        driver.get(url)
        
        # Wait for page to load
        print("Waiting for page to load...")
        time.sleep(3)
        
        # Click all dropdown arrows
        if not find_and_click_dropdowns(driver):
            print("No dropdown arrows found or clicked!")
            return
        
        # Wait for chapter lists to expand
        time.sleep(1)
        
        # Find all chapter links
        chapters = find_chapter_links(driver)
        
        if chapters:
            print(f"\nProcessing {len(chapters)} chapters...")
            
            # Process each chapter
            for idx, chapter in enumerate(chapters, 1):
                try:
                    chapter_name = chapter.text.strip()
                    current_chapter = chapter_name
                    print(f"\nProcessing chapter {idx}/{len(chapters)}: {chapter_name}")
                    
                    # Try to scroll chapter into view
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", chapter)
                        time.sleep(0.3)
                    except:
                        pass
                    
                    # Try to click the chapter name
                    try:
                        chapter.click()
                        print(f"Clicked chapter: {chapter_name}")
                        time.sleep(0.3)  # Short wait for popup
                    except Exception as e:
                        print(f"Error clicking chapter: {str(e)}")
                        continue
                    
                    # Extract email from popup
                    email = extract_email_from_popup(driver)
                    
                    if email:
                        print(f"Found email for {chapter_name}: {email}")
                        
                        # Add to our data
                        chapter_data.append({
                            "Chapter": chapter_name,
                            "Email": email
                        })
                    
                    # Click back arrow to return to chapter list
                    if not click_back_arrow(driver):
                        print(f"Warning: Could not return to chapter list after {chapter_name}")
                        continue
                    
                    # Save progress every 10 chapters
                    if idx % 10 == 0:
                        print(f"Progress: {idx}/{len(chapters)} chapters processed")
                        df = pd.DataFrame(chapter_data)
                        df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_ipt_progress.csv", index=False)
                    
                    # Small delay before next chapter
                    time.sleep(0.3)
                
                except Exception as e:
                    print(f"Error processing chapter {current_chapter}: {str(e)}")
                    continue
        else:
            print("No chapter links found!")
        
        # Save final results
        if chapter_data:
            output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_ipt.csv"
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
            df.to_csv(output_path, index=False)
            
            print(f"\nScraping complete!")
            print(f"Found {len(df)} unique chapters with emails")
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
    scrape_chapter_info()
