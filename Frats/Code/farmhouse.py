import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import time
import signal
import sys
import re
import getpass

# Global variables
chapter_data = []
current_chapter = None
driver = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = fr"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_farmhouse_partial_{timestamp}.csv"
        
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

def facebook_login(driver, email, password):
    """Login to Facebook with provided credentials"""
    try:
        print("Attempting to log in to Facebook...")
        
        # Navigate to Facebook login page
        driver.get("https://www.facebook.com/")
        time.sleep(3)
        
        # Accept cookies if prompted
        try:
            cookie_buttons = driver.find_elements(By.CSS_SELECTOR, 
                "button[data-testid='cookie-policy-dialog-accept-button'], " +
                "button[data-testid='cookie-policy-manage-dialog-accept-button'], " +
                "button[aria-label='Allow all cookies']")
            
            for button in cookie_buttons:
                if button.is_displayed():
                    button.click()
                    print("Clicked cookie consent button")
                    time.sleep(2)
                    break
        except:
            pass
        
        # Find and fill email field
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_field = driver.find_element(By.ID, "email")
            email_field.clear()
            email_field.send_keys(email)
            
            # Find and fill password field
            password_field = driver.find_element(By.ID, "pass")
            password_field.clear()
            password_field.send_keys(password)
            
            # Click login button
            login_button = driver.find_element(By.CSS_SELECTOR, "button[name='login']")
            login_button.click()
            
            print("Login submitted, waiting for redirect...")
            time.sleep(5)
            
            # Check if login was successful
            if "checkpoint" in driver.current_url or "login" in driver.current_url:
                print("Login may require additional verification. Please complete it in the browser.")
                input("Press Enter after completing verification in the browser window...")
            
            # Wait a bit more to ensure full login
            time.sleep(5)
            
            # Check if we're on the Facebook homepage
            if "facebook.com" in driver.current_url and not "login" in driver.current_url:
                print("Login successful!")
                return True
            else:
                print("Login not fully successful. Current URL:", driver.current_url)
                # Let's continue anyway
                return True
        except Exception as e:
            print(f"Error during login: {str(e)}")
            return False
    
    except Exception as e:
        print(f"Login failed: {str(e)}")
        return False

def collect_chapter_links(driver):
    """Collect all chapter Facebook links directly from the page"""
    try:
        print("Collecting all chapter Facebook links directly...")
        
        # Scroll down the page gradually to load all content
        scroll_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(0, scroll_height, 300):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(0.1)
        
        # Scroll back to top
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        # Find all social icon link containers
        social_containers = driver.find_elements(By.CSS_SELECTOR, ".elementor-social-icons-wrapper, .elementor-grid, .elementor-widget-social-icons")
        
        # List to store all found Facebook links
        all_facebook_links = []
        
        # Extract Facebook links from social containers
        for container in social_containers:
            try:
                fb_links = container.find_elements(By.CSS_SELECTOR, "a[href*='facebook.com']")
                for link in fb_links:
                    href = link.get_attribute("href")
                    if href and "facebook.com" in href:
                        all_facebook_links.append(href)
            except:
                continue
        
        # If that didn't work, look more broadly
        if not all_facebook_links:
            all_facebook_links = [link.get_attribute("href") for link in 
                                driver.find_elements(By.CSS_SELECTOR, "a[href*='facebook.com']") 
                                if link.get_attribute("href")]
        
        # Find all heading elements that might contain chapter names
        headings = driver.find_elements(By.CSS_SELECTOR, "h4.elementor-heading-title, h3.elementor-heading-title, h5.elementor-heading-title")
        
        # Extract chapter names and associated sections
        chapters = {}
        processed_fb_links = set()
        
        # First approach: Associate headings with Facebook links
        for heading in headings:
            try:
                chapter_name = heading.text.strip()
                if chapter_name and len(chapter_name) < 50 and chapter_name != "Current Chapters":  # Reasonable length for chapter name
                    # Find parent or surrounding elements that might contain Facebook links
                    parent = heading
                    fb_link = None
                    
                    # Look up in DOM tree for social icons
                    for _ in range(5):  # Look up to 5 levels up
                        try:
                            parent = parent.find_element(By.XPATH, "./..")
                            fb_links = parent.find_elements(By.CSS_SELECTOR, "a[href*='facebook.com']")
                            if fb_links:
                                fb_link = fb_links[0].get_attribute("href")
                                break
                        except:
                            continue
                    
                    # If not found going up, try siblings and nearby elements
                    if not fb_link:
                        try:
                            # Try to find a nearby container with social links
                            siblings = driver.find_elements(By.XPATH, f"//h4[contains(text(), '{chapter_name}')]/following-sibling::div[position() <= 3]")
                            for sibling in siblings:
                                fb_links = sibling.find_elements(By.CSS_SELECTOR, "a[href*='facebook.com']")
                                if fb_links:
                                    fb_link = fb_links[0].get_attribute("href")
                                    break
                        except:
                            pass
                    
                    # If still not found, try looking for social icons near the heading
                    if not fb_link:
                        try:
                            # Get heading position
                            heading_rect = heading.rect
                            heading_y = heading_rect['y']
                            
                            # Find social links that are close vertically
                            all_fb_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='facebook.com']")
                            for fb_elem in all_fb_elements:
                                try:
                                    fb_rect = fb_elem.rect
                                    # If the link is within reasonable vertical distance of the heading (within 150px)
                                    if abs(fb_rect['y'] - heading_y) < 150:
                                        fb_link = fb_elem.get_attribute("href")
                                        break
                                except:
                                    continue
                        except:
                            pass
                    
                    # If we found a Facebook link
                    if fb_link and fb_link not in processed_fb_links:
                        processed_fb_links.add(fb_link)
                        
                        # Try to find university name
                        university_name = ""
                        try:
                            # Try parent element first
                            text_elems = parent.find_elements(By.CSS_SELECTOR, "p, div.elementor-text-editor")
                            for elem in text_elems:
                                text = elem.text.strip()
                                if "University" in text or "State" in text:
                                    lines = text.split('\n')
                                    for line in lines:
                                        if "University" in line or "State" in line:
                                            university_name = line.strip()
                                            break
                                    if university_name:
                                        break
                            
                            # If university name not found, it might be in the chapter name
                            if not university_name and chapter_name:
                                if "University" in chapter_name or "State" in chapter_name:
                                    university_name = chapter_name
                        except:
                            pass
                        
                        chapters[fb_link] = {
                            "Chapter": chapter_name,
                            "University": university_name,
                            "Facebook": fb_link
                        }
                        print(f"Found chapter: {chapter_name} - {fb_link}")
            except:
                continue
        
        # Second approach: If we have Facebook links without chapters, try to find nearby headings
        for fb_link in all_facebook_links:
            if fb_link not in processed_fb_links:
                try:
                    # Find the element with this href
                    fb_elements = driver.find_elements(By.CSS_SELECTOR, f"a[href='{fb_link}']")
                    if not fb_elements:
                        continue
                    
                    fb_element = fb_elements[0]
                    # Get the position of this element
                    fb_rect = fb_element.rect
                    fb_y = fb_rect['y']
                    
                    # Find the closest heading
                    closest_heading = None
                    min_distance = float('inf')
                    
                    for heading in headings:
                        try:
                            heading_rect = heading.rect
                            distance = abs(heading_rect['y'] - fb_y)
                            
                            if distance < min_distance and distance < 150:  # Within 150 pixels
                                min_distance = distance
                                closest_heading = heading
                        except:
                            continue
                    
                    if closest_heading:
                        chapter_name = closest_heading.text.strip()
                        
                        # Try to find university name
                        university_name = ""
                        # Check if the chapter name contains university info
                        if "University" in chapter_name or "State" in chapter_name:
                            university_name = chapter_name
                        
                        chapters[fb_link] = {
                            "Chapter": chapter_name,
                            "University": university_name,
                            "Facebook": fb_link
                        }
                        processed_fb_links.add(fb_link)
                        print(f"Found chapter via proximity: {chapter_name} - {fb_link}")
                    else:
                        # Use fallback name based on URL
                        fb_parts = fb_link.split('/')
                        page_name = fb_parts[-1] if fb_parts[-1] else fb_parts[-2]
                        chapter_name = page_name.replace('FH', '').replace('farmhouse', '').title()
                        
                        chapters[fb_link] = {
                            "Chapter": chapter_name,
                            "University": "",
                            "Facebook": fb_link
                        }
                        processed_fb_links.add(fb_link)
                        print(f"Found chapter via URL parsing: {chapter_name} - {fb_link}")
                except:
                    continue
        
        print(f"Collected {len(chapters)} unique chapters with Facebook links")
        return list(chapters.values())
    
    except Exception as e:
        print(f"Error collecting chapter links: {str(e)}")
        return []

def find_facebook_emails(driver, facebook_url, chapter_info):
    """Visit Facebook page and try to find email address"""
    try:
        print(f"Visiting Facebook page: {facebook_url}")
        driver.get(facebook_url)
        time.sleep(5)  # Increased wait time for page load
        
        # First check if we're on a "this content isn't available" page
        if "This content isn't available right now" in driver.page_source:
            print("Facebook page not available")
            return None
        
        # Check for cookies or popup dialogs and try to close them
        try:
            cookie_buttons = driver.find_elements(By.CSS_SELECTOR, 
                "button[data-testid='cookie-policy-dialog-accept-button'], " +
                "button[data-testid='cookie-policy-manage-dialog-accept-button'], " +
                "button[aria-label='Allow all cookies']")
            
            for button in cookie_buttons:
                if button.is_displayed():
                    button.click()
                    print("Clicked cookie consent button")
                    time.sleep(1)
                    break
        except:
            pass
        
        # Look for email on the page
        email = ""
        
        # Method 1: Look for email text spans with improved selectors
        try:
            # More comprehensive selectors for finding email spans
            email_selectors = [
                "span[dir='auto']", 
                "[data-testid='m_page_about_content'] span",
                "div.x193iq5w span", 
                "a[href^='mailto:']", 
                "span:contains('@')",
                "span.xt0psk2",  # Facebook email spans
                "div.xu06os2 span",  # Contact info spans
                "[data-testid='profile_email'] span"  # Profile email spans
            ]
            
            for selector in email_selectors:
                spans = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for span in spans:
                    try:
                        span_text = span.text.strip().lower()
                        # Check if it looks like an email
                        if "@" in span_text and "." in span_text and " " not in span_text:
                            if span_text.endswith("@farmhouse.org") or "farmhouse" in span_text:
                                email = span_text
                                print(f"Found email directly: {email}")
                                break
                    except:
                        continue
                
                if email:
                    break
            
            # If no farmhouse email found, try more general pattern
            if not email:
                for selector in email_selectors:
                    spans = driver.find_elements(By.CSS_SELECTOR, selector)
                    for span in spans:
                        try:
                            span_text = span.text.strip().lower()
                            if re.match(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", span_text):
                                email = span_text
                                print(f"Found general email: {email}")
                                break
                        except:
                            continue
                    if email:
                        break
        except:
            pass
        
        # Method A: Try to find elements that are links and contain mailto:
        if not email:
            try:
                email_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
                for link in email_links:
                    try:
                        href = link.get_attribute("href")
                        if href and href.startswith("mailto:"):
                            email = href.replace("mailto:", "")
                            print(f"Found email in mailto link: {email}")
                            break
                    except:
                        continue
            except:
                pass
        
        # Method 2: Check About tab if no email found
        if not email:
            try:
                # Look for About link with better selector
                about_links = driver.find_elements(By.CSS_SELECTOR, 
                    "a[href*='/about'], " +
                    "a[role='link']:contains('About'), " +
                    "div[role='tab']:contains('About'), " +
                    "a:contains('About')")
                
                about_clicked = False
                for link in about_links:
                    try:
                        if (link.is_displayed() and 
                            (link.get_attribute("href") and "about" in link.get_attribute("href").lower() or 
                             "about" in link.text.lower())):
                            # Scroll to the link
                            driver.execute_script("arguments[0].scrollIntoView();", link)
                            time.sleep(1)
                            
                            link.click()
                            about_clicked = True
                            print("Clicked About tab")
                            time.sleep(5)  # Increased wait time
                            break
                    except:
                        continue
                
                if about_clicked:
                    # Now look in the About section
                    # 2a: Try to find Contact info section
                    try:
                        # Find the Contact Info section - various selectors
                        contact_info_selectors = [
                            "div:contains('Contact Info')",
                            "div[role='button']:has(span:contains('Contact Info'))",
                            "div:contains('Email')",
                            "div:contains('Contact')",
                            "div[role='heading']:contains('Contact')"
                        ]
                        
                        for selector in contact_info_selectors:
                            contact_sections = driver.find_elements(By.CSS_SELECTOR, selector)
                            for section in contact_sections:
                                if section.is_displayed():
                                    # Try to click it to expand
                                    try:
                                        section.click()
                                        print("Clicked Contact Info section")
                                        time.sleep(2)
                                    except:
                                        pass
                                    
                                    # Now look for email in this section
                                    try:
                                        section_text = section.text.lower()
                                        if "@" in section_text and "." in section_text:
                                            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', section_text)
                                            if emails:
                                                email = emails[0]
                                                print(f"Found email in Contact section: {email}")
                                                break
                                    except:
                                        continue
                            
                            if email:
                                break
                    except:
                        pass
                    
                    # 2b: If still no email, look through all content on About page
                    if not email:
                        try:
                            # Try looking at all visible text on page
                            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                            if "@" in page_text and "." in page_text:
                                emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', page_text)
                                farmhouse_emails = [e for e in emails if "farmhouse" in e or e.endswith(".edu")]
                                
                                if farmhouse_emails:
                                    email = farmhouse_emails[0]
                                    print(f"Found farmhouse email in About page text: {email}")
                                elif emails:
                                    filtered_emails = [e for e in emails if not any(exclude in e for exclude in 
                                                     ['example.com', 'yourdomain', 'domain.com', 'email.com', '@facebook'])]
                                    if filtered_emails:
                                        email = filtered_emails[0]
                                        print(f"Found general email in About page text: {email}")
                        except:
                            pass
            except Exception as e:
                print(f"Error navigating to About: {str(e)}")
                pass
        
        # Method 3: Try to extract email from page source
        if not email:
            try:
                page_source = driver.page_source.lower()
                
                # More comprehensive regex for finding emails in HTML
                email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
                
                # Extract all matches
                emails = re.findall(email_pattern, page_source)
                
                # Filter for farmhouse.org or .edu emails first
                farmhouse_emails = [e for e in emails if "farmhouse" in e or e.endswith(".edu")]
                
                # Filter out common false positives
                filtered_emails = [e for e in farmhouse_emails if not any(exclude in e for exclude in 
                                  ['example.com', 'yourdomain', 'domain.com', 'email.com', '@facebook'])]
                
                if filtered_emails:
                    email = filtered_emails[0]
                    print(f"Found farmhouse/edu email in page source: {email}")
                elif emails:
                    # Filter general emails
                    filtered_general = [e for e in emails if not any(exclude in e for exclude in 
                                      ['example.com', 'yourdomain', 'domain.com', 'email.com', '@facebook'])]
                    if filtered_general:
                        email = filtered_general[0]
                        print(f"Found general email in page source: {email}")
            except Exception as e:
                print(f"Error extracting email from source: {str(e)}")
                pass
        
        # Method 4: Check Page Transparency section
        if not email:
            try:
                # Look for Page Transparency section or "About" section
                transparency_selectors = [
                    "div:contains('Page Transparency')",
                    "div[role='button']:contains('Page Transparency')",
                    "div:contains('Page info')"
                ]
                
                for selector in transparency_selectors:
                    transparency_sections = driver.find_elements(By.CSS_SELECTOR, selector)
                    for section in transparency_sections:
                        if section.is_displayed():
                            # Try to click it to expand
                            try:
                                section.click()
                                print("Clicked Page Transparency section")
                                time.sleep(2)
                                
                                # Now look for "See All" button
                                see_all_buttons = driver.find_elements(By.CSS_SELECTOR, 
                                    "div[role='button']:contains('See All'), " +
                                    "span:contains('See All')")
                                
                                for button in see_all_buttons:
                                    if button.is_displayed():
                                        button.click()
                                        print("Clicked See All button")
                                        time.sleep(2)
                                        break
                                
                                # Now look for contact info
                                page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                                if "@" in page_text and "." in page_text:
                                    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', page_text)
                                    if emails:
                                        email = emails[0]
                                        print(f"Found email in Page Transparency: {email}")
                                        break
                            except:
                                continue
                    
                    if email:
                        break
            except:
                pass
        
        # Method 5: Try to find any link with "contact" in it and follow it
        if not email:
            try:
                contact_links = driver.find_elements(By.CSS_SELECTOR, 
                    "a[href*='contact'], a:contains('Contact'), a:contains('contact')")
                
                for link in contact_links:
                    try:
                        if link.is_displayed() and ((link.get_attribute("href") and "contact" in link.get_attribute("href").lower()) or 
                                                  "contact" in link.text.lower()):
                            # Scroll to the link
                            driver.execute_script("arguments[0].scrollIntoView();", link)
                            time.sleep(1)
                            
                            link.click()
                            print("Clicked Contact link")
                            time.sleep(3)
                            
                            # Now look for emails on this page
                            contact_page_source = driver.page_source.lower()
                            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', contact_page_source)
                            
                            # Filter emails
                            farmhouse_emails = [e for e in emails if "farmhouse" in e or e.endswith(".edu")]
                            filtered_emails = [e for e in farmhouse_emails if not any(exclude in e for exclude in 
                                             ['example.com', 'yourdomain', 'domain.com', 'email.com', '@facebook'])]
                            
                            if filtered_emails:
                                email = filtered_emails[0]
                                print(f"Found email in contact page: {email}")
                                break
                            elif emails:
                                filtered_general = [e for e in emails if not any(exclude in e for exclude in 
                                                 ['example.com', 'yourdomain', 'domain.com', 'email.com', '@facebook'])]
                                if filtered_general:
                                    email = filtered_general[0]
                                    print(f"Found general email in contact page: {email}")
                                    break
                            
                            # Go back after checking
                            driver.back()
                            time.sleep(2)
                    except:
                        continue
            except:
                pass
        
        # Method 6: Look for "More" or "See More" buttons that might reveal emails
        if not email:
            try:
                more_buttons = driver.find_elements(By.CSS_SELECTOR, 
                    "div[role='button']:contains('See More'), " +
                    "div[role='button']:contains('More'), " +
                    "span:contains('See More')")
                
                for button in more_buttons:
                    try:
                        if button.is_displayed():
                            # Scroll to the button
                            driver.execute_script("arguments[0].scrollIntoView();", button)
                            time.sleep(1)
                            
                            button.click()
                            print("Clicked See More button")
                            time.sleep(2)
                            
                            # Check if this revealed an email
                            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                            if "@" in page_text and "." in page_text:
                                emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', page_text)
                                if emails:
                                    filtered_emails = [e for e in emails if not any(exclude in e for exclude in 
                                                     ['example.com', 'yourdomain', 'domain.com', 'email.com', '@facebook'])]
                                    if filtered_emails:
                                        email = filtered_emails[0]
                                        print(f"Found email after clicking More: {email}")
                                        break
                    except:
                        continue
            except:
                pass
        
        # Method 7: Check meta tags in HTML source
        if not email:
            try:
                meta_tags = driver.find_elements(By.CSS_SELECTOR, "meta[property='og:email'], meta[name='email']")
                for tag in meta_tags:
                    content = tag.get_attribute("content")
                    if content and "@" in content and "." in content:
                        email = content
                        print(f"Found email in meta tag: {email}")
                        break
            except:
                pass
        
        if email:
            # Clean the email (remove spaces, etc.)
            email = email.strip().lower()
            email = re.sub(r'\s+', '', email)
            
            print(f"Success! Email found for {chapter_info['Chapter']}: {email}")
            return email
        else:
            print(f"No email found for {chapter_info['Chapter']} on Facebook")
            return None
    
    except Exception as e:
        print(f"Error processing Facebook page: {str(e)}")
        return None

def get_credentials():
    """Get Facebook login credentials from user"""
    print("\nTo improve scraping results, we need your Facebook login credentials.")
    print("These credentials are used only for this script and are not stored anywhere.\n")
    
    email = input("Enter your Facebook email: ")
    password = getpass.getpass("Enter your Facebook password: ")
    
    return email, password

def scrape_all_chapter_info():
    """Main function to scrape all chapter information"""
    print("Starting FarmHouse fraternity email scraper...")
    global chapter_data, current_chapter, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        
        # Get Facebook credentials and log in first
        fb_email, fb_password = get_credentials()
        login_success = facebook_login(driver, fb_email, fb_password)
        
        if not login_success:
            print("Login failed. Proceeding without authentication (results may be limited).")
        else:
            print("Successfully logged into Facebook. Proceeding with authenticated session.")
        
        # Visit the chapters page
        driver.get("https://farmhouse.org/join/current-chapters/")
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Collect chapter links directly
        chapters = collect_chapter_links(driver)
        
        if chapters:
            print(f"\nProcessing {len(chapters)} unique chapters...")
            
            # Visit each Facebook page and extract email
            for idx, chapter in enumerate(chapters, 1):
                try:
                    current_chapter = chapter['Chapter']
                    print(f"\nProcessing chapter {idx}/{len(chapters)}: {current_chapter}")
                    
                    # Visit Facebook page
                    email = find_facebook_emails(driver, chapter['Facebook'], chapter)
                    
                    # Add to our data
                    chapter_data.append({
                        "Chapter": chapter['Chapter'],
                        "University": chapter['University'],
                        "Facebook": chapter['Facebook'],
                        "Email": email if email else ""
                    })
                    
                    # Save progress periodically
                    if idx % 3 == 0:  # Save more frequently
                        print(f"Progress: {idx}/{len(chapters)} chapters processed")
                        df = pd.DataFrame(chapter_data)
                        df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_farmhouse_progress.csv", index=False)
                    
                    # Small delay between chapters to avoid rate limiting
                    time.sleep(2)
                
                except Exception as e:
                    print(f"Error processing chapter {current_chapter}: {str(e)}")
                    continue
        else:
            print("No chapters found!")
        
        # Save final results
        if chapter_data:
            output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_farmhouse.csv"
            df = pd.DataFrame(chapter_data)
            df.drop_duplicates(subset=['Facebook'], keep='first', inplace=True)  # Ensure no duplicates
            df.to_csv(output_path, index=False)
            
            # Count how many emails we found
            emails_found = sum(1 for chapter in chapter_data if chapter.get('Email'))
            
            print(f"\nScraping complete!")
            print(f"Found {len(df)} unique chapters")
            print(f"Found emails for {emails_found} chapters")
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
    scrape_all_chapter_info()
