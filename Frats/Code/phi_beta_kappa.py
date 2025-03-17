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
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_pbk_partial_{timestamp}.csv"
        
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

def extract_chapter_info():
    """Main function to scrape chapter information"""
    print("Starting Phi Beta Kappa chapter email scraper...")
    global chapter_data, current_chapter, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        
        # Process each page (30 pages total)
        for page in range(1, 31):
            print(f"\n=== Processing Page {page}/30 ===")
            
            # Visit the page directly using URL
            url = f"https://www.pbk.org/chapters-associations/chapter-directory?searchmode=anyword&fullsearchtext=&chapterfilter=&stateprovincefilter=&page={page}"
            driver.get(url)
            time.sleep(3)  # Short wait for page load
            
            # Find all chapter cards with the correct structure
            chapter_cards = driver.find_elements(By.CSS_SELECTOR, "div.search-result-card")
            print(f"Found {len(chapter_cards)} chapters on page {page}")
            
            # Process each chapter
            for idx, card in enumerate(chapter_cards, 1):
                try:
                    # Extract chapter name from h3
                    chapter_name = card.find_element(By.CSS_SELECTOR, "h3.capitalized-text").text.strip()
                    current_chapter = chapter_name
                    
                    # Extract contact name
                    contact_name = card.find_element(By.CSS_SELECTOR, "span.capitalized-text").text.strip()
                    
                    # Find email link (using the exact structure)
                    email_element = card.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
                    email = email_element.text.strip()
                    
                    print(f"Processing chapter {idx}/{len(chapter_cards)}: {chapter_name}")
                    
                    # Add to dataset
                    chapter_data.append({
                        "Chapter": chapter_name,
                        "Contact": contact_name,
                        "Email": email,
                        "Page": page
                    })
                    
                except Exception as e:
                    print(f"Error processing chapter {idx} on page {page}: {str(e)}")
                    continue
            
            # Save progress every 3 pages
            if page % 3 == 0:
                print(f"\nSaving progress... Found {len(chapter_data)} chapters so far")
                df = pd.DataFrame(chapter_data)
                df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_pbk_progress.csv", index=False)
        
        # Save final results
        if chapter_data:
            output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_pbk.csv"
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
            df.to_csv(output_path, index=False)
            
            print(f"\nScraping complete!")
            print(f"Found {len(df)} unique emails across {len(chapter_data)} chapters")
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
