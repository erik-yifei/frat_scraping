import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
import time
import signal
import sys

# Global variables
chapter_data = []
current_state = None
driver = None
processed_emails = set()  # Track emails we've already found

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = fr"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_byx_partial_{timestamp}.csv"
        
        df = pd.DataFrame(chapter_data)
        df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
        df.to_csv(partial_output_path, index=False)
        
        print(f"\nPartial results saved!")
        print(f"Found {len(chapter_data)} unique chapters")
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

def find_state_elements(driver):
    """Find all clickable state elements on the map"""
    try:
        print("Looking for clickable state elements on the map...")
        
        # Find the SVG map element
        svg_selectors = [
            "svg",
            ".imapper-content-wrapper svg",
            "[id*='map'] svg",
            ".elementor-widget-container svg"
        ]
        
        svg_element = None
        for selector in svg_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.size['height'] > 100:
                        svg_element = element
                        break
                if svg_element:
                    break
            except:
                continue
        
        if not svg_element:
            print("Could not find SVG map element")
            return []
        
        # Find clickable state elements
        state_elements = []
        
        # Option 1: Find path elements with state-specific attributes
        path_selectors = [
            "path[id*='US-']",  # Paths with state ID
            "path[data-id*='US-']",
            "path[class*='state']",
            "path[fill='#4f2d7f']",  # Purple states
            "path[stroke-width='0.40']"  # Common attribute for state paths
        ]
        
        for selector in path_selectors:
            try:
                paths = svg_element.find_elements(By.CSS_SELECTOR, selector)
                for path in paths:
                    if path.is_displayed():
                        state_elements.append(path)
            except:
                continue
        
        # Option 2: If no paths found, try any clickable elements inside SVG
        if not state_elements:
            try:
                all_elements = svg_element.find_elements(By.CSS_SELECTOR, "*")
                for elem in all_elements:
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            # Check if it has a cursor pointer style
                            style = elem.get_attribute("style")
                            if style and "cursor: pointer" in style:
                                state_elements.append(elem)
                    except:
                        continue
            except:
                pass
        
        print(f"Found {len(state_elements)} potential state elements on the map")
        return state_elements
    
    except Exception as e:
        print(f"Error finding state elements: {str(e)}")
        return []

def get_state_buttons(driver):
    """Find state buttons in the map"""
    try:
        print("Looking for state buttons...")
        
        # Try multiple selectors for state buttons
        button_selectors = [
            "[data-original-id^='US-']",  # Elements with state ID
            "[id^='us-'][role='button']",
            ".imapper-pin-wrapper",
            "[class*='state-button']",
            "[id*='state']",
            "[class*='map-region']"
        ]
        
        all_buttons = []
        for selector in button_selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                visible_buttons = [b for b in buttons if b.is_displayed()]
                all_buttons.extend(visible_buttons)
                if visible_buttons:
                    print(f"Found {len(visible_buttons)} buttons with selector '{selector}'")
            except:
                continue
        
        # If no buttons found, look for clickable regions in the SVG map
        if not all_buttons:
            svg_elements = driver.find_elements(By.CSS_SELECTOR, "svg path, svg g")
            for elem in svg_elements:
                try:
                    if elem.is_displayed() and "pointer" in elem.value_of_css_property("cursor"):
                        all_buttons.append(elem)
                except:
                    continue
        
        if all_buttons:
            print(f"Found total of {len(all_buttons)} potential state buttons")
            return all_buttons
        else:
            print("No state buttons found, will try direct coordinate clicking")
            return []
            
    except Exception as e:
        print(f"Error finding state buttons: {str(e)}")
        return []

def click_on_state(driver, state_element, state_name="Unknown State"):
    """Click on a state element"""
    try:
        print(f"Clicking on {state_name}...")
        
        # Scroll to element
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", state_element)
        time.sleep(1)
        
        # Try multiple click methods
        try:
            # Method 1: Regular click
            state_element.click()
        except:
            try:
                # Method 2: JavaScript click
                driver.execute_script("arguments[0].click();", state_element)
            except:
                try:
                    # Method 3: ActionChains click
                    actions = ActionChains(driver)
                    actions.move_to_element(state_element).click().perform()
                except:
                    print(f"All click methods failed for {state_name}")
                    return False
        
        # Wait for content to appear
        time.sleep(2)
        return True
        
    except Exception as e:
        print(f"Error clicking on {state_name}: {str(e)}")
        return False

def extract_chapters_from_panel(driver):
    """Extract chapter information from the state panel"""
    chapters = []
    
    try:
        # Wait for the panel to be visible
        wait = WebDriverWait(driver, 3)
        
        # Look for the content panel that appears after clicking a state
        panel_selectors = [
            ".igm-map-content[style*='display: block']",
            "div[data-content-type='regions'][style*='display: block']",
            "div[data-original-id^='US-'][style*='display: block']",
            ".elementor-widget-loop-grid",
            ".elementor-grid",
            ".elementor-element-populated",
            ".elementor-icon-list-items li"
        ]
        
        panel_found = False
        for selector in panel_selectors:
            try:
                panel = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                if panel.is_displayed():
                    panel_found = True
                    print(f"Found content panel using selector: {selector}")
                    break
            except:
                continue
        
        if not panel_found:
            # Try the exact XPath provided by the user as a backup
            try:
                xpath = "/html/body/div[2]/section[2]/div/div/div/div[4]/div/div/div[2]/div"
                panel = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                if panel.is_displayed():
                    panel_found = True
                    print("Found content panel using provided XPath")
            except:
                print("No content panel found after clicking state")
                return []
        
        # Find all email links
        email_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
        
        if not email_links:
            # Try using a more specific selector based on the HTML structure
            email_links = driver.find_elements(By.CSS_SELECTOR, 
                ".elementor-icon-list-item a[href^='mailto:']")
        
        print(f"Found {len(email_links)} email links in the panel")
        
        for link in email_links:
            try:
                href = link.get_attribute("href")
                if href and href.startswith("mailto:"):
                    email = href.replace("mailto:", "")
                    
                    # Skip admin email
                    if email == "admin@byx.org":
                        continue
                    
                    # Find university name by looking up to the heading
                    university_name = "Unknown University"
                    
                    try:
                        # Navigate up to find the chapter container
                        container = link.find_element(By.XPATH, 
                            "./ancestor::div[contains(@class, 'e-loop-item') or contains(@class, 'elementor-section')][1]")
                        
                        # Look for the heading inside the container
                        heading = container.find_element(By.CSS_SELECTOR, 
                            "h1.elementor-heading-title, h2.elementor-heading-title, h3.elementor-heading-title")
                        
                        university_name = heading.text.strip()
                        
                        # If still empty, get the heading text directly
                        if not university_name:
                            university_name = heading.find_element(By.CSS_SELECTOR, "a").text.strip()
                    except:
                        # Try a more direct approach if the above fails
                        try:
                            # Look for any heading with "University" or "College" in the text
                            headings = driver.find_elements(By.XPATH, 
                                ".//h1[contains(text(), 'University') or contains(text(), 'College')] | " +
                                ".//h2[contains(text(), 'University') or contains(text(), 'College')] | " +
                                ".//h3[contains(text(), 'University') or contains(text(), 'College')]")
                            
                            if headings:
                                university_name = headings[0].text.strip()
                        except:
                            pass
                    
                    # Only add if it's a new email
                    if email not in processed_emails:
                        processed_emails.add(email)
                        chapters.append({
                            'Chapter Name': university_name,
                            'Email': email
                        })
                        print(f"Found chapter: {university_name} - {email}")
            except Exception as e:
                print(f"Error extracting email: {str(e)}")
                continue
                
        return chapters
    
    except Exception as e:
        print(f"Error extracting chapters from panel: {str(e)}")
        return []

def try_coordinate_clicks(driver):
    """Try clicking at specific coordinates on the map"""
    chapters_found = []
    
    # Define regions of interest on the map (approximate state locations)
    regions = [
        # Format: (x, y, state_name)
        (570, 360, "Texas"),
        (650, 300, "Florida"),
        (640, 280, "Georgia"),
        (590, 250, "Tennessee"),
        (550, 230, "Missouri"),
        (500, 240, "Kansas"),
        (570, 220, "Illinois"),
        (620, 210, "Ohio"),
        (680, 200, "Pennsylvania"),
        (720, 220, "North Carolina"),
        (690, 270, "Alabama"),
        (650, 350, "Louisiana"),
        (450, 200, "Nebraska"),
        (350, 280, "Colorado"),
        (250, 290, "Utah"),
        (150, 240, "California"),
        (200, 150, "Washington"),
        (520, 160, "Wisconsin"),
        (580, 170, "Michigan"),
        (710, 170, "New York"),
        (740, 230, "Virginia")
    ]
    
    print("\nTrying coordinate-based clicks...")
    
    for x, y, state_name in regions:
        try:
            print(f"Attempting to click at coordinates ({x}, {y}) for {state_name}")
            
            # Get element at coordinates
            element = driver.execute_script(f"return document.elementFromPoint({x}, {y});")
            
            if element:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(1)
                
                # Try clicking the element
                try:
                    element.click()
                except:
                    try:
                        driver.execute_script("arguments[0].click();", element)
                    except:
                        continue
                
                time.sleep(2)
                
                # Extract chapters
                new_chapters = extract_chapters_from_panel(driver)
                if new_chapters:
                    chapters_found.extend(new_chapters)
                    print(f"Found {len(new_chapters)} chapters from {state_name}")
                
                # Clear any modals that might be open
                try:
                    close_buttons = driver.find_elements(By.CSS_SELECTOR, 
                        "button.close, .close-button, button.modal-close, [aria-label='Close']")
                    for button in close_buttons:
                        if button.is_displayed():
                            button.click()
                            break
                except:
                    pass
                    
                time.sleep(1)
        except:
            continue
    
    return chapters_found

def main():
    print("Starting Beta Upsilon Chi chapter email scraper (STATE-FOCUSED VERSION)...")
    global chapter_data, current_state, driver, processed_emails
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        driver.get("https://byx.org/join-a-chapter/")
        print("Waiting for page to load...")
        time.sleep(5)
        
        # APPROACH 1: Look for state buttons
        state_buttons = get_state_buttons(driver)
        
        if state_buttons:
            print(f"\nProcessing {len(state_buttons)} state buttons...")
            
            for idx, button in enumerate(state_buttons, 1):
                try:
                    # Try to get state name from button
                    state_name = "Unknown"
                    try:
                        state_id = button.get_attribute("id") or button.get_attribute("data-original-id")
                        if state_id and "us-" in state_id.lower():
                            state_name = state_id.split("-")[-1].upper()
                        else:
                            state_name = f"State {idx}"
                    except:
                        state_name = f"State {idx}"
                    
                    current_state = state_name
                    
                    # Click the state
                    if click_on_state(driver, button, state_name):
                        # Extract chapters from panel
                        new_chapters = extract_chapters_from_panel(driver)
                        chapter_data.extend(new_chapters)
                        
                        if new_chapters:
                            print(f"Found {len(new_chapters)} chapters in {state_name}")
                        else:
                            print(f"No chapters found in {state_name}")
                    
                    # Save progress periodically
                    if idx % 5 == 0 and chapter_data:
                        print(f"Progress: {idx}/{len(state_buttons)} states, found {len(chapter_data)} chapters")
                        df = pd.DataFrame(chapter_data)
                        df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
                        df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_byx_progress.csv", index=False)
                        
                except Exception as e:
                    print(f"Error processing state {idx}: {str(e)}")
                    continue
        
        # APPROACH 2: Find SVG state elements
        if not state_buttons or len(chapter_data) < 5:
            print("\nLooking for SVG state elements...")
            state_elements = find_state_elements(driver)
            
            if state_elements:
                print(f"\nProcessing {len(state_elements)} SVG state elements...")
                
                for idx, state_elem in enumerate(state_elements, 1):
                    try:
                        state_name = f"SVG State {idx}"
                        current_state = state_name
                        
                        # Click the state
                        if click_on_state(driver, state_elem, state_name):
                            # Extract chapters from panel
                            new_chapters = extract_chapters_from_panel(driver)
                            chapter_data.extend(new_chapters)
                            
                            if new_chapters:
                                print(f"Found {len(new_chapters)} chapters in {state_name}")
                            else:
                                print(f"No chapters found in {state_name}")
                        
                        # Save progress periodically
                        if idx % 5 == 0 and chapter_data:
                            print(f"Progress: {idx}/{len(state_elements)} SVG states, found {len(chapter_data)} chapters")
                            df = pd.DataFrame(chapter_data)
                            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
                            df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_byx_progress.csv", index=False)
                            
                    except Exception as e:
                        print(f"Error processing SVG state {idx}: {str(e)}")
                        continue
        
        # APPROACH 3: Try clicking at coordinates (if few results so far)
        if len(chapter_data) < 10:
            new_chapters = try_coordinate_clicks(driver)
            chapter_data.extend(new_chapters)
            
            # Save progress
            if chapter_data:
                df = pd.DataFrame(chapter_data)
                df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
                df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_byx_progress.csv", index=False)
        
        # APPROACH 4: Try clicking on elements with state names
        print("\nTrying to find elements with state names...")
        
        # List of states to try
        states_to_try = [
            "Alabama", "Arizona", "Arkansas", "California", "Colorado", 
            "Florida", "Georgia", "Indiana", "Kansas", "Kentucky", 
            "Louisiana", "Minnesota", "Mississippi", "Missouri", "Montana", 
            "Nebraska", "North Carolina", "Oklahoma", "Oregon", "South Carolina", 
            "Tennessee", "Texas", "Virginia", "Washington", "Wisconsin"
        ]
        
        for state_name in states_to_try:
            try:
                current_state = state_name
                print(f"\nLooking for elements containing '{state_name}'")
                
                # Find elements containing the state name
                elements = driver.find_elements(By.XPATH, 
                    f"//*[contains(text(), '{state_name}')]")
                
                # Filter for visible elements
                visible_elements = []
                for elem in elements:
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            visible_elements.append(elem)
                    except:
                        continue
                
                if visible_elements:
                    print(f"Found {len(visible_elements)} elements containing '{state_name}'")
                    
                    # Try clicking on each element
                    for idx, elem in enumerate(visible_elements[:3]):  # Limit to first 3
                        try:
                            # Scroll to element
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", elem)
                            time.sleep(1)
                            
                            # Try to click
                            try:
                                elem.click()
                            except:
                                try:
                                    driver.execute_script("arguments[0].click();", elem)
                                except:
                                    continue
                            
                            time.sleep(2)
                            
                            # Extract chapters
                            new_chapters = extract_chapters_from_panel(driver)
                            chapter_data.extend(new_chapters)
                            
                            if new_chapters:
                                print(f"Found {len(new_chapters)} chapters from {state_name}")
                            
                            # Try to close any popups
                            try:
                                close_buttons = driver.find_elements(By.CSS_SELECTOR, 
                                    "button.close, .close-button, button.modal-close, [aria-label='Close']")
                                for button in close_buttons:
                                    if button.is_displayed():
                                        button.click()
                                        break
                            except:
                                pass
                                
                            time.sleep(1)
                        except:
                            continue
                
                # Save progress after each state
                if chapter_data:
                    df = pd.DataFrame(chapter_data)
                    df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
                    df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_byx_progress.csv", index=False)
                    
            except Exception as e:
                print(f"Error with state {state_name}: {str(e)}")
                continue
        
        # Save final results
        output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_byx.csv"
        
        if chapter_data:
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
            df.to_csv(output_path, index=False)
            
            print(f"\nScraping complete!")
            print(f"Found {len(df)} unique chapters with emails:")
            for _, row in df.iterrows():
                print(f"- {row['Chapter Name']}: {row['Email']}")
            print(f"Results saved to: {output_path}")
        else:
            print("No chapters found!")
            
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        signal_handler(None, None)
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
