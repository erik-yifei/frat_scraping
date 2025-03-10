import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
import time
import random
import signal
import sys

# Global variables to store state
chapter_data = []
current_chapter = None
driver = None
main_window = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_deltazeta_partial_{timestamp}.csv"
        
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

def get_state_chapters(driver, state_value, state_name):
    """Get all chapters for a given state"""
    try:
        # Select state using JavaScript
        driver.execute_script(
            f'document.querySelector("#ctl01_TemplateBody_WebPartManager1_gwpciSearch_ciSearch_ResultsGrid_Sheet0_Input0_DropDown1").value = "{state_value}";'
        )
        
        # Click search button using JavaScript
        driver.execute_script(
            'document.querySelector("#ctl01_TemplateBody_WebPartManager1_gwpciSearch_ciSearch_ResultsGrid_Sheet0_SubmitButton").click();'
        )
        
        # Short wait for results
        time.sleep(1)
        
        return get_chapters(driver)
        
    except Exception as e:
        print(f"Error processing state {state_name}: {str(e)}")
        return []

def get_chapter_email(driver, chapter_url):
    """Get email directly using JavaScript"""
    try:
        # Execute JavaScript to fetch email from chapter URL
        email_script = """
        var xhr = new XMLHttpRequest();
        xhr.open('GET', arguments[0], false);
        xhr.send(null);
        var parser = new DOMParser();
        var doc = parser.parseFromString(xhr.responseText, 'text/html');
        var emailElem = doc.querySelector('#ctl01_TemplateBody_WebPartManager1_gwpciNewSummaryDisplayCommon_ciNewSummaryDisplayCommon_ChapterEmail');
        return emailElem ? emailElem.textContent.trim() : null;
        """
        email = driver.execute_script(email_script, chapter_url)
        return email if email else None
            
    except Exception as e:
        return None

def get_chapters(driver):
    """Get all chapters from search results"""
    chapters = []
    
    try:
        # Wait for results table with shorter timeout
        wait = WebDriverWait(driver, 5)
        rows = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "tr.rgRow, tr.rgAltRow")
        ))
        
        for row in rows:
            try:
                # Get chapter info using JavaScript
                chapter_info = driver.execute_script("""
                    var row = arguments[0];
                    return {
                        name: row.querySelector('td:nth-child(2)').textContent,
                        type: row.querySelector('td:nth-child(3)').textContent,
                        url: row.querySelector('a').href
                    }
                """, row)
                
                # Get email directly
                email = get_chapter_email(driver, chapter_info['url'])
                
                if email:
                    chapters.append({
                        'Chapter Name': chapter_info['name'],
                        'Chapter Type': chapter_info['type'],
                        'Email': email
                    })
                    print(f"✓ Found email for {chapter_info['name']}: {email}")
                else:
                    print(f"✗ No email found for {chapter_info['name']}")
                
            except Exception as e:
                print(f"Error processing chapter row: {str(e)}")
                continue
                
    except Exception as e:
        print(f"Error getting chapters: {str(e)}")
        
    return chapters

def main():
    print("Starting Delta Zeta chapter email scraper...")
    global chapter_data, current_chapter, driver, main_window
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        driver.get("https://dzsorority.deltazeta.org/DZSMEMBERS/Chapter_Search/DZSMEMBERS/Chapter_Search/ChapterSearch.aspx")
        main_window = driver.current_window_handle
        time.sleep(2)
        
        # Get all state options using JavaScript
        state_options = driver.execute_script("""
            var select = document.querySelector("#ctl01_TemplateBody_WebPartManager1_gwpciSearch_ciSearch_ResultsGrid_Sheet0_Input0_DropDown1");
            return Array.from(select.options)
                .filter(opt => opt.value)
                .map(opt => ({value: opt.value, text: opt.text}));
        """)
        
        total_states = len(state_options)
        print(f"Found {total_states} states/provinces to process")
        
        # Process each state
        for idx, state in enumerate(state_options, 1):
            state_value = state['value']
            state_name = state['text']
            current_chapter = state_name
            print(f"\nProcessing {state_name} ({idx}/{total_states})")
            
            state_chapters = get_state_chapters(driver, state_value, state_name)
            chapter_data.extend(state_chapters)
            
            # Save progress after each state
            if chapter_data:
                df = pd.DataFrame(chapter_data)
                df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_deltazeta_progress.csv", index=False)
        
        # Save final results
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_deltazeta.csv"
        if chapter_data:
            df = pd.DataFrame(chapter_data)
            df.to_csv(output_path, index=False)
        
        print(f"\nScraping complete!")
        print(f"Found {len(chapter_data)} chapters with emails")
        print(f"Results saved to: {output_path}")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        signal_handler(None, None)
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main() 