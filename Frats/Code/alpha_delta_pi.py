import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import signal
import sys
import re

# Global variables
chapter_data = []
current_page = 1
driver = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_adpi_partial_{timestamp}.csv"
        
        df = pd.DataFrame(chapter_data)
        df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
        df.to_csv(partial_output_path, index=False)
        
        print(f"\nPartial results saved!")
        print(f"Processed {len(chapter_data)} unique chapters")
        print(f"Last page processed: {current_page}")
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

def extract_chapter_info(html_content):
    """Extract chapter information from HTML content using regex"""
    try:
        # Extract chapter name and university
        name_match = re.search(r'<h2>(.*?)</h2>', html_content)
        chapter_name = name_match.group(1) if name_match else "Unknown"
        
        # Extract email using regex
        email_match = re.search(r'mailto:(.*?)"', html_content)
        email = email_match.group(1) if email_match else None
        
        if email and chapter_name != "Unknown":
            return {
                'Chapter Name': chapter_name.strip(),
                'Email': email.strip()
            }
        return None
        
    except Exception as e:
        print(f"Error extracting chapter info: {str(e)}")
        return None

def get_page_chapters(driver):
    """Get all chapters from current page"""
    try:
        # Wait for the first chapter to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".frm_grid_container"))
        )
        
        # Use JavaScript to get exactly 5 chapter divs
        chapters_html = driver.execute_script("""
            return Array.from(document.querySelectorAll('.frm_grid_container'))
                .slice(0, 5)  // Take exactly 5 chapters
                .map(div => div.outerHTML);
        """)
        
        # Process chapters
        chapter_infos = []
        for html in chapters_html:
            info = extract_chapter_info(html)
            if info:
                chapter_infos.append(info)
        
        return chapter_infos
        
    except Exception as e:
        print(f"Error getting page chapters: {str(e)}")
        return []

def goto_page(driver, page_num):
    """Navigate to specific page"""
    try:
        url = f"https://www.alphadeltapi.org/collegians/chapterlocator/?frm-page-393254={page_num}"
        driver.get(url)
        time.sleep(1.5)  # Small wait for page load
        return True
    except Exception as e:
        print(f"Error navigating to page {page_num}: {str(e)}")
        return False

def main():
    print("Starting Alpha Delta Pi chapter email scraper...")
    global chapter_data, current_page, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        driver.get("https://www.alphadeltapi.org/collegians/chapterlocator/")
        time.sleep(2)
        
        # Process all 31 pages
        total_pages = 31
        for page in range(1, total_pages + 1):
            current_page = page
            print(f"\nProcessing page {page}/{total_pages}")
            
            if page > 1:
                if not goto_page(driver, page):
                    continue
            
            # Get chapters from current page
            page_chapters = get_page_chapters(driver)
            chapter_data.extend(page_chapters)
            
            # Save progress after each page
            if chapter_data:
                df = pd.DataFrame(chapter_data)
                df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
                df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_adpi_progress.csv", index=False)
            
            print(f"Found {len(page_chapters)} chapters with emails on page {page}")
        
        # Save final results
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_adpi.csv"
        if chapter_data:
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
            df.to_csv(output_path, index=False)
        
        print(f"\nScraping complete!")
        print(f"Found {len(df)} unique chapters with emails")
        print(f"Results saved to: {output_path}")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        signal_handler(None, None)
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
