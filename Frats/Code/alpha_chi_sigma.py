import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import time
import signal
import sys

# Global variables
chapter_data = []
current_marker = 0
driver = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_alphachisigma_partial_{timestamp}.csv"
        
        df = pd.DataFrame(chapter_data)
        df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
        df.to_csv(partial_output_path, index=False)
        
        print(f"\nPartial results saved!")
        print(f"Processed {len(chapter_data)} unique chapters")
        print(f"Last marker processed: {current_marker}")
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
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def wait_for_map_load(driver):
    """Wait for map and its elements to load"""
    try:
        # Wait for map to load and markers to appear
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='button'][title] img[src*='transparent.png']"))
        )
        time.sleep(5)  # Additional wait for all markers to populate
        return True
    except Exception as e:
        print(f"Error waiting for map load: {str(e)}")
        return False

def get_chapter_info(driver):
    """Extract chapter info from marker popup"""
    try:
        # Wait for feature card panel
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "featurecardPanel"))
        )
        
        # Wait for email using exact path
        email_elem = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR, 
                "#featurecardPanel > div > div > div.qqvbed-bN97Pc > div.qqvbed-UmHwN > div:nth-child(10) > div.qqvbed-p83tee-lTBxed > a"
            ))
        )
        
        # Get email
        email = email_elem.get_attribute("href").replace("mailto:", "")
        
        # Get chapter name
        chapter_name = driver.find_element(
            By.CSS_SELECTOR, 
            "#featurecardPanel > div > div > div.qqvbed-bN97Pc > div.qqvbed-UmHwN > div:nth-child(1)"
        ).text
        
        if email and chapter_name:
            return {
                'Chapter Name': chapter_name.strip(),
                'Email': email.strip()
            }
        return None
        
    except Exception as e:
        try:
            # Try alternative email location if first attempt fails
            email_elem = driver.find_element(
                By.XPATH,
                "//div[contains(@class, 'qqvbed-p83tee-lTBxed')]/a[contains(@href, 'mailto:')]"
            )
            email = email_elem.get_attribute("href").replace("mailto:", "")
            
            # Get chapter name
            chapter_name = driver.find_element(
                By.CSS_SELECTOR,
                ".qqvbed-bN97Pc div:first-child"
            ).text
            
            if email and chapter_name:
                return {
                    'Chapter Name': chapter_name.strip(),
                    'Email': email.strip()
                }
        except:
            print(f"Error extracting chapter info: {str(e)}")
        return None

def get_all_markers(driver):
    """Get all map markers"""
    try:
        # Find all marker elements that match the exact structure
        markers = driver.find_elements(
            By.CSS_SELECTOR, 
            "div[role='button'][title] img[src*='transparent.png']"
        )
        
        # Get parent elements (the actual clickable markers)
        visible_markers = []
        for marker in markers:
            try:
                parent = marker.find_element(By.XPATH, "./..")
                if parent.is_displayed():
                    visible_markers.append(parent)
            except:
                continue
        
        return visible_markers
    except Exception as e:
        print(f"Error getting markers: {str(e)}")
        return []

def click_marker(driver, marker):
    """Click on a map marker"""
    try:
        # Center marker in view
        driver.execute_script("""
            var rect = arguments[0].getBoundingClientRect();
            var windowHeight = window.innerHeight;
            var windowWidth = window.innerWidth;
            window.scrollTo(
                rect.left + window.pageXOffset - (windowWidth / 2),
                rect.top + window.pageYOffset - (windowHeight / 2)
            );
        """, marker)
        time.sleep(1)
        
        # Try multiple click methods
        try:
            # Try ActionChains click
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).move_to_element(marker).click().perform()
        except:
            try:
                # Try JavaScript click
                driver.execute_script("arguments[0].click();", marker)
            except:
                # Try direct click
                marker.click()
        
        time.sleep(2)  # Increased wait for popup
        return True
        
    except Exception as e:
        print(f"Error clicking marker: {str(e)}")
        return False

def main():
    print("Starting Alpha Chi Sigma chapter email scraper...")
    global chapter_data, current_marker, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        driver.get("https://www.google.com/maps/d/u/0/viewer?mid=1MRpnp4xgvON54czrTv-1n9gQvKg")
        
        # Wait for map to load
        if not wait_for_map_load(driver):
            print("Could not load map")
            return
        
        # Get all markers
        markers = get_all_markers(driver)
        total_markers = len(markers)
        print(f"Found {total_markers} chapter markers on map")
        
        # Process each marker
        for idx, marker in enumerate(markers, 1):
            current_marker = idx
            print(f"\nProcessing marker {idx}/{total_markers}")
            
            try:
                # Click marker
                if click_marker(driver, marker):
                    # Get chapter info
                    chapter_info = get_chapter_info(driver)
                    if chapter_info:
                        chapter_data.append(chapter_info)
                        print(f"✓ Found email for {chapter_info['Chapter Name']}: {chapter_info['Email']}")
                    else:
                        print("✗ No email found for this marker")
                    
                    time.sleep(1)
                
            except Exception as e:
                print(f"Error processing marker: {str(e)}")
                continue
        
        # Save final results
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_alphachisigma.csv"
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
