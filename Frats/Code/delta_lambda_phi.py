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

# Global variables
chapter_data = []
current_section = None
driver = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = fr"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_dlp_partial_{timestamp}.csv"
        
        df = pd.DataFrame(chapter_data)
        df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
        df.to_csv(partial_output_path, index=False)
        
        print(f"\nPartial results saved!")
        print(f"Found {len(chapter_data)} unique chapters with emails")
        print(f"Last section processed: {current_section}")
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
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    # Add stealth script
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
    
    return driver

def find_state_sections(driver):
    """Find all state sections on the page"""
    try:
        print("Finding state sections...")
        
        # First, look for state headings (using the provided HTML structure)
        state_headings = driver.find_elements(By.CSS_SELECTOR, "h3.font_3[style*='font-size:30px;'] .backcolor_23")
        
        if not state_headings:
            # Fallback - try other selectors that might find state headings
            state_headings = driver.find_elements(By.CSS_SELECTOR, "h3.font_3, h3[class*='rich-text']")
        
        print(f"Found {len(state_headings)} state sections")
        
        # Extract state names
        state_sections = []
        for heading in state_headings:
            try:
                state_name = heading.text.strip()
                if state_name:
                    # Find parent container of the state section
                    container = heading
                    for _ in range(5):  # Try up to 5 levels up
                        try:
                            container = container.find_element(By.XPATH, "./..")
                            # Check if this container has chapter info
                            chapter_info = container.find_elements(By.CSS_SELECTOR, "p.font_7, p[class*='rich-text']")
                            if chapter_info:
                                state_sections.append({
                                    "state": state_name,
                                    "container": container
                                })
                                break
                        except:
                            continue
            except:
                continue
        
        print(f"Processed {len(state_sections)} state sections")
        return state_sections
    
    except Exception as e:
        print(f"Error finding state sections: {str(e)}")
        return []

def extract_chapter_info(state_section):
    """Extract all chapter information from a state section"""
    try:
        state_name = state_section["state"]
        container = state_section["container"]
        
        print(f"Processing {state_name} section...")
        
        # Find all chapter blocks within this state section
        chapter_blocks = container.find_elements(By.CSS_SELECTOR, "div[class*='SPY_vo']")
        
        if not chapter_blocks:
            # Try an alternative selector
            chapter_blocks = container.find_elements(By.CSS_SELECTOR, "div[data-mesh-id*='inlineContent']")
        
        chapters = []
        
        # If we found specific chapter blocks
        if chapter_blocks:
            for block in chapter_blocks:
                try:
                    # Extract university name
                    university_name = "Unknown University"
                    university_elements = block.find_elements(By.CSS_SELECTOR, "p.font_7 span[style*='font-weight:bold'], span.wixui-rich-text__text[style*='font-weight:bold']")
                    
                    if university_elements:
                        university_name = university_elements[0].text.strip()
                    
                    # Extract chapter name/designation
                    chapter_name = ""
                    chapter_elements = block.find_elements(By.CSS_SELECTOR, "p.font_7 span[style*='font-style:italic'], span.wixui-rich-text__text[style*='font-style:italic']")
                    
                    if chapter_elements:
                        chapter_name = chapter_elements[0].text.strip()
                    
                    # Extract email link
                    email = ""
                    email_elements = block.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
                    
                    if email_elements:
                        email = email_elements[0].get_attribute("href").replace("mailto:", "")
                    
                    if email:
                        chapters.append({
                            "State": state_name,
                            "University": university_name,
                            "Chapter": chapter_name,
                            "Email": email
                        })
                        print(f"Found chapter: {university_name} - {email}")
                except Exception as e:
                    print(f"Error extracting chapter info: {str(e)}")
                    continue
        else:
            # Try to find email links directly in the container
            email_links = container.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
            
            for link in email_links:
                try:
                    email = link.get_attribute("href").replace("mailto:", "")
                    
                    # Try to find associated university name
                    university_name = "Unknown University"
                    chapter_name = ""
                    
                    # Look for parent container with chapter info
                    parent = link
                    for _ in range(5):  # Try up to 5 levels up
                        try:
                            parent = parent.find_element(By.XPATH, "./..")
                            # Look for university name
                            uni_elements = parent.find_elements(By.CSS_SELECTOR, "span[style*='font-weight:bold']")
                            if uni_elements:
                                university_name = uni_elements[0].text.strip()
                                break
                        except:
                            continue
                    
                    # Look for chapter designation
                    try:
                        chapter_elements = parent.find_elements(By.CSS_SELECTOR, "span[style*='font-style:italic']")
                        if chapter_elements:
                            chapter_name = chapter_elements[0].text.strip()
                    except:
                        pass
                    
                    chapters.append({
                        "State": state_name,
                        "University": university_name,
                        "Chapter": chapter_name,
                        "Email": email
                    })
                    print(f"Found chapter: {university_name} - {email}")
                except:
                    continue
        
        return chapters
    
    except Exception as e:
        print(f"Error extracting chapters from {state_section['state']}: {str(e)}")
        return []

def find_all_emails_on_page(driver):
    """Fallback method to find all email links on the page"""
    try:
        print("Using fallback method to find all email links...")
        
        email_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
        chapters = []
        
        for link in email_links:
            try:
                email = link.get_attribute("href").replace("mailto:", "")
                
                # Skip non-chapter emails
                if not (email.endswith("@dlp.org") or "chapter" in email or "university" in email):
                    continue
                    
                # Try to find associated university and chapter
                university_name = "Unknown University"
                chapter_name = ""
                state_name = "Unknown State"
                
                # Look upward in DOM for containers with this information
                parent = link
                for _ in range(5):  # Try up to 5 levels up
                    try:
                        parent = parent.find_element(By.XPATH, "./..")
                        
                        # Try to find state name
                        state_elements = parent.find_elements(By.CSS_SELECTOR, "h3.font_3 .backcolor_23, h3[class*='rich-text']")
                        if state_elements:
                            state_name = state_elements[0].text.strip()
                        
                        # Try to find university name
                        uni_elements = parent.find_elements(By.CSS_SELECTOR, "span[style*='font-weight:bold'], span.wixui-rich-text__text[style*='font-weight:bold']")
                        if uni_elements:
                            university_name = uni_elements[0].text.strip()
                        
                        # Try to find chapter name
                        chapter_elements = parent.find_elements(By.CSS_SELECTOR, "span[style*='font-style:italic'], span.wixui-rich-text__text[style*='font-style:italic']")
                        if chapter_elements:
                            chapter_name = chapter_elements[0].text.strip()
                            
                        # If we found at least university name, break
                        if university_name != "Unknown University":
                            break
                    except:
                        continue
                
                # Extra check: If university name is still unknown, try using email
                if university_name == "Unknown University":
                    if "." in email and "@" in email:
                        parts = email.split("@")[0].split(".")
                        if len(parts) > 1:
                            if parts[0].lower() in ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
                                                   "iota", "kappa", "lambda", "mu", "nu", "xi", "omicron", "pi", "rho",
                                                   "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega"]:
                                chapter_name = parts[0].capitalize()
                            if parts[1].lower() == "chapter":
                                university_name = f"{chapter_name} Chapter"
                
                chapters.append({
                    "State": state_name,
                    "University": university_name,
                    "Chapter": chapter_name,
                    "Email": email
                })
                print(f"Found chapter: {university_name} - {email}")
            except:
                continue
                
        return chapters
    
    except Exception as e:
        print(f"Error in fallback email finder: {str(e)}")
        return []

def main():
    print("Starting Delta Lambda Phi fraternity email scraper...")
    global chapter_data, current_section, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        
        # Visit the chapters page
        driver.get("https://www.dlp.org/chapters")
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Find all state sections
        state_sections = find_state_sections(driver)
        
        if state_sections:
            print(f"\nProcessing {len(state_sections)} state sections...")
            
            # Process each state section
            for idx, section in enumerate(state_sections, 1):
                try:
                    current_section = section["state"]
                    print(f"\nProcessing state section {idx}/{len(state_sections)}: {current_section}")
                    
                    # Extract chapter info from the section
                    chapters = extract_chapter_info(section)
                    chapter_data.extend(chapters)
                    
                    print(f"Found {len(chapters)} chapters in {current_section}")
                    
                    # Save progress periodically
                    if idx % 5 == 0 and chapter_data:
                        print(f"Progress: {idx}/{len(state_sections)} sections processed")
                        df = pd.DataFrame(chapter_data)
                        df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_dlp_progress.csv", index=False)
                except Exception as e:
                    print(f"Error processing section {current_section}: {str(e)}")
                    continue
        else:
            print("No state sections found. Trying fallback method...")
            
            # If no state sections found, try to find all email links on the page
            chapters = find_all_emails_on_page(driver)
            chapter_data.extend(chapters)
        
        # Save final results
        if chapter_data:
            output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_dlp.csv"
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
            df.to_csv(output_path, index=False)
            
            print(f"\nScraping complete!")
            print(f"Found {len(df)} unique chapters with emails:")
            for _, row in df.iterrows():
                print(f"- {row['University']} ({row['Chapter']}): {row['Email']}")
            print(f"Results saved to: {output_path}")
        else:
            print("No chapter emails found!")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        signal_handler(None, None)
    
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
