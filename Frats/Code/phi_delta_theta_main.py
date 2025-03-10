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
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_phideltatheta_partial_{timestamp}.csv"
        
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

def get_chapter_links(driver):
    """Get all chapter links from the main page"""
    print("Fetching chapter links...")
    driver.get("https://phideltatheta.org/join/locate-phi-delt/?tags=chapter")
    
    # Wait for the container to load
    wait = WebDriverWait(driver, 10)
    container = wait.until(EC.presence_of_element_located((By.ID, "storepoint-results-container")))
    time.sleep(3)  # Additional wait for dynamic content
    
    # Get all chapter elements
    chapters = driver.find_elements(By.CSS_SELECTOR, "div.storepoint-location")
    
    chapter_links = []
    for chapter in chapters:
        try:
            name = chapter.find_element(By.CLASS_NAME, "storepoint-name").text
            link = chapter.find_element(By.CSS_SELECTOR, "div.storepoint-btn a").get_attribute("href")
            if link and "phideltatheta.org" in link:
                chapter_links.append((name, link))
                print(f"Found chapter: {name}")
        except Exception as e:
            print(f"Error getting chapter info: {str(e)}")
            continue
    
    print(f"\nFound {len(chapter_links)} chapter links")
    return chapter_links

def get_chapter_email(driver, chapter_url):
    """Extract email from chapter website"""
    try:
        driver.get(chapter_url)
        time.sleep(2)  # Wait for page load
        
        # Try to find email in footer
        email_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "footer a[href^='mailto:']"))
        )
        
        email = email_element.get_attribute("href").replace("mailto:", "")
        return email.strip()
        
    except Exception as e:
        print(f"Error getting email: {str(e)}")
        return None

def main():
    print("Starting Phi Delta Theta chapter email scraper...")
    global chapter_data, current_chapter, driver
    
    # Register the signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        chapter_links = get_chapter_links(driver)
        
        # Process each chapter
        for idx, (chapter_name, chapter_url) in enumerate(chapter_links, 1):
            current_chapter = chapter_name
            print(f"\nProcessing {idx}/{len(chapter_links)}: {chapter_name}")
            
            try:
                email = get_chapter_email(driver, chapter_url)
                if email:
                    chapter_data.append({
                        'Chapter Name': chapter_name,
                        'Chapter URL': chapter_url,
                        'Email': email
                    })
                    print(f"✓ Found email: {email}")
                else:
                    print("✗ No email found")
                
                # Random delay between requests
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"Error processing chapter: {str(e)}")
                continue
        
        # Save final results to CSV
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_phideltatheta.csv"
        df = pd.DataFrame(chapter_data)
        df.to_csv(output_path, index=False)
        
        print(f"\nScraping complete!")
        print(f"Found {len(chapter_data)} emails")
        print(f"Results saved to: {output_path}")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        # Save partial results on fatal error
        signal_handler(None, None)
    
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
