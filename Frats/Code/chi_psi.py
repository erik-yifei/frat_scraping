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
import re
import signal
import sys

# Global variables
chapter_data = []
current_chapter = None
driver = None

def signal_handler(signum, frame):
    """Handle interrupt signal and save partial results"""
    print("\n\nInterrupt received! Saving partial results...")
    
    if chapter_data:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        partial_output_path = fr"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_chipsi_partial_{timestamp}.csv"
        
        df = pd.DataFrame(chapter_data)
        df.drop_duplicates(subset=['Email'], keep='first', inplace=True)
        df.to_csv(partial_output_path, index=False)
        
        print(f"\nPartial results saved!")
        print(f"Found {len(chapter_data)} unique chapters with emails")
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
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    # Add stealth script
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
    
    return driver

def get_chapter_links(driver):
    """Extract links to all chapter pages from the main alphas and colleges page"""
    chapter_links = []
    
    try:
        print("Finding chapter links...")
        
        # Look for all links in table cells that could be chapter links
        links = driver.find_elements(By.CSS_SELECTOR, "td a[href*='chipsi.org']")
        
        for link in links:
            href = link.get_attribute("href")
            chapter_name = link.text.strip()
            
            # Skip if either is empty
            if not href or not chapter_name:
                continue
                
            # Only include links to chapter pages
            if "chipsi.org" in href and not href.endswith("alphas-and-colleges/"):
                chapter_links.append({
                    "name": chapter_name,
                    "url": href
                })
        
        # Also look for all Alpha links with specific format (Alpha name followed by link to university)
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
        for row in rows:
            try:
                # Find cells with Alpha names and links
                cells = row.find_elements(By.CSS_SELECTOR, "td")
                if len(cells) >= 3:  # Ensure we have enough cells
                    alpha_cell = cells[0]
                    alpha_links = alpha_cell.find_elements(By.TAG_NAME, "a")
                    
                    if alpha_links:
                        href = alpha_links[0].get_attribute("href")
                        chapter_name = alpha_links[0].text.strip()
                        
                        if href and chapter_name and "chipsi.org" in href:
                            # Check if we already have this link
                            if not any(chapter["url"] == href for chapter in chapter_links):
                                chapter_links.append({
                                    "name": chapter_name,
                                    "url": href
                                })
            except:
                continue
        
        print(f"Found {len(chapter_links)} chapter links")
        return chapter_links
    
    except Exception as e:
        print(f"Error finding chapter links: {str(e)}")
        return []

def extract_contact_info(driver, chapter_name):
    """Extract contact information from chapter page"""
    try:
        print(f"Extracting contact info for {chapter_name}...")
        
        # Method 1: Try finding through the XPath provided
        try:
            contact_section = driver.find_element(By.XPATH, 
                "/html/body/div[1]/div/div/div/div/article/div/div/div[2]/div/div/div/div[3]")
            
            # Check if it's found and has contact info
            if "CONTACT INFO" in contact_section.text:
                print("Found contact section through XPath")
            else:
                contact_section = None
        except:
            contact_section = None
        
        # Method 2: Try finding through CSS selectors if XPath failed
        if not contact_section:
            try:
                contact_section = driver.find_element(By.CSS_SELECTOR, 
                    "div.pp-infobox-title-wrapper:contains('CONTACT INFO') ~ div.pp-infobox-description, " +
                    "h4:contains('CONTACT INFO'), " +
                    "h4.pp-infobox-title:contains('CONTACT INFO')")
                print("Found contact section through CSS selector")
            except:
                pass
        
        # Method 3: Try finding any div with contact info text
        if not contact_section:
            try:
                elements = driver.find_elements(By.XPATH, 
                    "//*[contains(text(), 'CONTACT INFO') or contains(text(), 'Contact Info')]")
                
                # Find closest element containing contact info
                for elem in elements:
                    # Look for email in parent or siblings
                    contact_section = elem
                    if "Email" in elem.text or "@" in elem.text:
                        print("Found contact section through text matching")
                        break
                    
                    # Try parent
                    try:
                        parent = elem.find_element(By.XPATH, "./..")
                        if "Email" in parent.text or "@" in parent.text:
                            contact_section = parent
                            print("Found contact section in parent element")
                            break
                    except:
                        pass
                        
                    # Try next siblings
                    try:
                        siblings = driver.find_elements(By.XPATH, 
                            "./following-sibling::*")
                        for sibling in siblings[:3]:  # Check next 3 siblings
                            if "Email" in sibling.text or "@" in sibling.text:
                                contact_section = sibling
                                print("Found contact section in sibling element")
                                break
                    except:
                        pass
            except:
                pass
        
        # Method 4: Look for email links anywhere on the page
        if not contact_section:
            try:
                email_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
                if email_links:
                    for email_link in email_links:
                        mail_text = email_link.get_attribute("href").replace("mailto:", "")
                        
                        # Look for parent or container with name
                        try:
                            parent = email_link.find_element(By.XPATH, "./ancestor::div[contains(@class, 'contact') or contains(@class, 'info')][1]")
                            contact_section = parent
                            print("Found email link in contact section")
                            break
                        except:
                            # If no specific container, use the email link itself
                            contact_section = email_link
                            print("Found standalone email link")
                            break
            except:
                pass
        
        # If we found a contact section, extract the email
        emails = []
        university_name = chapter_name
        
        if contact_section:
            # Extract text from section
            section_text = contact_section.text
            
            # Look for email links in the section
            email_elements = contact_section.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
            
            if email_elements:
                for email_elem in email_elements:
                    email = email_elem.get_attribute("href").replace("mailto:", "")
                    if email and "@" in email:
                        emails.append(email)
                        print(f"Found email: {email}")
            
            # If no email links found, try extracting email from text
            if not emails:
                # Use regex to find emails in text
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                found_emails = re.findall(email_pattern, section_text)
                
                if found_emails:
                    emails.extend(found_emails)
                    print(f"Found {len(found_emails)} emails in text")
            
            # Try to find the university name if not already set
            try:
                # Look for page title or heading
                title_elements = driver.find_elements(By.CSS_SELECTOR, 
                    "h1, h2.fl-heading, div.fl-heading-text, h1.entry-title")
                
                for title in title_elements:
                    title_text = title.text.strip()
                    if "University" in title_text or "College" in title_text:
                        university_name = title_text
                        break
            except:
                pass
        
        # If still no emails found, make one last attempt to find any mailto links
        if not emails:
            try:
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for link in all_links:
                    href = link.get_attribute("href")
                    if href and href.startswith("mailto:"):
                        email = href.replace("mailto:", "")
                        if email and "@" in email:
                            emails.append(email)
                            print(f"Found email in link: {email}")
            except:
                pass
        
        if emails:
            return {
                "Alpha": chapter_name,
                "University": university_name,
                "Emails": emails
            }
        else:
            print(f"No emails found for {chapter_name}")
            return None
    
    except Exception as e:
        print(f"Error extracting contact info for {chapter_name}: {str(e)}")
        return None

def main():
    print("Starting Chi Psi fraternity email scraper...")
    global chapter_data, current_chapter, driver
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        driver = setup_driver()
        
        # Visit the alphas and colleges page
        driver.get("https://www.chipsi.org/college-life/where-we-are/alphas-and-colleges/")
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Get chapter links
        chapter_links = get_chapter_links(driver)
        
        if not chapter_links:
            print("No chapter links found, exiting.")
            return
        
        print(f"\nProcessing {len(chapter_links)} chapters...")
        
        # Visit each chapter page and extract contact info
        for idx, chapter in enumerate(chapter_links, 1):
            try:
                current_chapter = chapter["name"]
                print(f"\nProcessing chapter {idx}/{len(chapter_links)}: {chapter['name']}")
                
                # Visit chapter page
                driver.get(chapter["url"])
                
                # Wait for page to load
                time.sleep(3)
                
                # Extract contact info
                info = extract_contact_info(driver, chapter["name"])
                
                if info and info["Emails"]:
                    # Add each email as a separate entry
                    for email in info["Emails"]:
                        chapter_data.append({
                            "Chapter Name": info["Alpha"],
                            "University": info["University"],
                            "Email": email
                        })
                    
                    print(f"Added {len(info['Emails'])} emails for {chapter['name']}")
                
                # Save progress periodically
                if idx % 5 == 0:
                    print(f"Progress: {idx}/{len(chapter_links)} chapters processed")
                    if chapter_data:
                        df = pd.DataFrame(chapter_data)
                        df.to_csv(r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_chipsi_progress.csv", index=False)
            
            except Exception as e:
                print(f"Error processing chapter {chapter['name']}: {str(e)}")
                continue
        
        # Save final results
        if chapter_data:
            output_path = r"C:\Users\ErikWang\Documents\Python_Email_Scraping\Frats\Output\frat_chipsi.csv"
            df = pd.DataFrame(chapter_data)
            df.to_csv(output_path, index=False)
            
            print(f"\nScraping complete!")
            print(f"Found {len(chapter_data)} emails from {len(set(entry['Chapter Name'] for entry in chapter_data))} chapters")
            print(f"Results saved to: {output_path}")
        else:
            print("No emails found!")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        signal_handler(None, None)
    
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
