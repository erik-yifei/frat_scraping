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
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_alphaomicronpi_partial_{timestamp}.csv"
        
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

def get_page_chapters(driver):
    """Extract chapters from current page"""
    chapters = []
    
    # Wait for chapter list to load
    wait = WebDriverWait(driver, 10)
    chapter_list = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "li.chapter-group")
    ))
    
    for chapter in chapter_list:
        try:
            # Get chapter name
            name = chapter.find_element(By.CSS_SELECTOR, "h2.chap-title").text
            
            # Try to get email if available
            try:
                email_link = chapter.find_element(By.CSS_SELECTOR, "a.chap-em")
                email = email_link.get_attribute("href").replace("mailto:", "")
            except:
                email = None
                
            # Get chapter type
            try:
                type_elem = chapter.find_element(By.CSS_SELECTOR, "p.chap-type")
                chapter_type = type_elem.text.replace("Type: ", "")
            except:
                chapter_type = "Unknown"
                
            chapters.append({
                'Chapter Name': name,
                'Chapter Type': chapter_type,
                'Email': email
            })
            
            print(f"Found chapter: {name}")
            if email:
                print(f"✓ Email: {email}")
            else:
                print("✗ No email found")
                
        except Exception as e:
            print(f"Error processing chapter: {str(e)}")
            continue
            
    return chapters

def go_to_next_page(driver, current_page):
    """Navigate to next page if available"""
    try:
        # Find next page button
        next_button = driver.find_element(
            By.CSS_SELECTOR, 
            f"a.facetwp-page[data-page='{current_page + 1}']"
        )
        
        # Scroll to button and click
        driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
        time.sleep(1)
        next_button.click()
        
        # Wait for page to load
        time.sleep(3)
        return True
        
    except Exception as e:
        print(f"Error navigating to next page: {str(e)}")
        return False

def main():
    print("Starting Alpha Omicron Pi chapter email scraper...")
    global chapter_data, current_chapter, driver
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        driver.get("https://www.alphaomicronpi.org/for-members/chapter-locator/")
        
        current_page = 1
        total_pages = 12  # Known total pages
        
        while current_page <= total_pages:
            print(f"\nProcessing page {current_page}/{total_pages}")
            
            # Get chapters from current page
            page_chapters = get_page_chapters(driver)
            chapter_data.extend(page_chapters)
            
            if current_page < total_pages:
                if not go_to_next_page(driver, current_page):
                    print("Failed to load next page")
                    break
                    
            current_page += 1
            time.sleep(random.uniform(1, 2))
        
        # Save final results
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_alphaomicronpi.csv"
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
