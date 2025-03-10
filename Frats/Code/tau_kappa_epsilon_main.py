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
        # Create partial results filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = rf"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\tke_chapters_partial_{timestamp}.csv"
        
        # Save partial results
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
    # Mask webdriver
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def get_chapter_links(driver):
    """Get all chapter links from the main page"""
    print("Fetching chapter links...")
    driver.get("https://www.tke.org/chapter-rankings")
    
    # Wait for the table to load
    wait = WebDriverWait(driver, 10)
    chapters = wait.until(EC.presence_of_all_elements_located(
        (By.XPATH, "//table//a[contains(@href, '/chapter/')]")
    ))
    
    # Extract href attributes
    chapter_links = []
    for chapter in chapters:
        link = chapter.get_attribute('href')
        name = chapter.text
        chapter_links.append((name, link))
        
    print(f"Found {len(chapter_links)} chapters")
    return chapter_links

def get_chapter_email(driver, chapter_url):
    """Get email from chapter page"""
    driver.get(chapter_url)
    
    try:
        wait = WebDriverWait(driver, 5)
        
        # Try multiple selectors in order of specificity
        selectors = [
            # Try CSS selector first
            (By.CSS_SELECTOR, "#ContentPlaceHolder1_ContentPlaceHolder1_pnlActive > div > div > div.row > div.col-md-3 > div:nth-child(1) > table > tbody > tr:nth-child(10) > td:nth-child(2) > a"),
            
            # Try full XPath
            (By.XPATH, "/html/body/form/div[4]/div[2]/div/div/div[2]/div[1]/div[1]/table/tbody/tr[10]/td[2]/a"),
            
            # Try more flexible XPath looking for envelope icon
            (By.XPATH, "//a[contains(@href, 'mailto:')]//span[contains(@class, 'glyphicon-envelope')]/.."),
            
            # Try finding any mailto link in the contact table
            (By.XPATH, "//div[contains(@class, 'col-md-3')]//table//a[contains(@href, 'mailto:')]")
        ]
        
        email_element = None
        for selector_type, selector in selectors:
            try:
                email_element = wait.until(EC.presence_of_element_located((selector_type, selector)))
                if email_element:
                    break
            except:
                continue
        
        if not email_element:
            print("Could not find email element with any selector")
            return None
            
        # Extract email from mailto: link
        email = email_element.get_attribute('href').replace('mailto:', '')
        
        # Verify this isn't the headquarters email
        if email.lower() == 'tkeogc@tke.org':
            print("⚠️ Found headquarters email instead of chapter email")
            return None
            
        # Verify email format
        if '@' not in email or '.' not in email:
            print(f"⚠️ Invalid email format: {email}")
            return None
            
        return email
        
    except Exception as e:
        print(f"Could not find chapter email: {str(e)}")
        # For debugging, print the page source when email is not found
        try:
            print("\nPage source snippet:")
            source = driver.page_source
            print(source[:500] + "..." if len(source) > 500 else source)
        except:
            pass
        return None

def main():
    print("Starting TKE chapter email scraper...")
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
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\tke_chapters.csv"
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
