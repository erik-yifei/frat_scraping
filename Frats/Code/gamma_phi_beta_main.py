import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import signal
import sys

# Global variables to store state
chapter_data = []
current_state = None
driver = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_gammaphibeta_partial_{timestamp}.csv"
        
        df = pd.DataFrame(chapter_data)
        df.to_csv(partial_output_path, index=False)
        
        print(f"\nPartial results saved!")
        print(f"Processed {len(chapter_data)} chapters")
        print(f"Last state processed: {current_state}")
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
    chapters = []
    
    try:
        # Select the state
        state_select = Select(driver.find_element(By.ID, "GPBStates"))
        state_select.select_by_value(state_value)
        time.sleep(2)  # Wait for chapters to load
        
        # Find all chapter divs
        chapter_divs = driver.find_elements(By.CSS_SELECTOR, "div.Chapter")
        
        for chapter in chapter_divs:
            try:
                # Get chapter name
                name = chapter.find_element(By.TAG_NAME, "h2").text
                
                # Get chapter type (Collegiate or Alumnae)
                info = chapter.find_element(By.TAG_NAME, "p").text.split('\n')
                chapter_type = next((line for line in info if line in ['Collegiate', 'Alumnae']), 'Unknown')
                
                # Try to get email
                try:
                    email_link = chapter.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
                    email = email_link.get_attribute("href").replace("mailto:", "")
                except:
                    email = None
                
                chapters.append({
                    'Chapter Name': name,
                    'State': state_name,
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
                
    except Exception as e:
        print(f"Error processing state {state_name}: {str(e)}")
    
    return chapters

def main():
    print("Starting Gamma Phi Beta chapter email scraper...")
    global chapter_data, current_state, driver
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        driver.get("https://www.gammaphibeta.org/ChapterLocator/Chapter-Locator")
        time.sleep(3)  # Wait for page load
        
        # Get all state options
        state_select = Select(driver.find_element(By.ID, "GPBStates"))
        state_options = [(option.get_attribute("value"), option.text) 
                        for option in state_select.options 
                        if option.get_attribute("value")]  # Skip empty value
        
        total_states = len(state_options)
        print(f"Found {total_states} states/provinces to process")
        
        # Process each state
        for idx, (state_value, state_name) in enumerate(state_options, 1):
            current_state = state_name
            print(f"\nProcessing {state_name} ({idx}/{total_states})")
            
            state_chapters = get_state_chapters(driver, state_value, state_name)
            chapter_data.extend(state_chapters)
            
            time.sleep(random.uniform(1, 2))
        
        # Save final results
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\soro_gammaphibeta.csv"
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
