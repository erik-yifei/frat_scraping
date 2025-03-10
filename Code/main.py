import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Regular expression pattern for extracting emails
email_pattern = r'[a-zA-Z0-9_.+-]+(?:@|\s*\[at\]\s*)[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

# Keywords to identify relevant clubs
keywords = [
    "finance", "trading", "quant", "investment",
    "traders", "undergrad", "portfolio management",
    "equity trading"
]

# Domains to exclude
excluded_domains = ['google.com', 'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com']

# List of User-Agents to rotate through
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
]

print("Starting the scraping process...")

try:
    # Initialize Chrome driver with webdriver manager
    chrome_options = Options()
    # Remove headless mode temporarily for debugging
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    # Mask webdriver
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Read the list of universities from CSV
    input_file = "/Users/erikwang/Documents/Dub/Email_Scraper/Input/Target_Universiteis.csv"
    try:
        # Read all universities and start from row 114
        universities_df = pd.read_csv(input_file)
        # Skip first 113 rows (start from 114th)
        universities_df = universities_df.iloc[113:]
        universities_df = universities_df.reset_index(drop=True)  # Reset index for clean numbering
        
        # Ensure we have both University and Abbreviation columns
        required_columns = ['University', 'Abbreviation']
        if not all(col in universities_df.columns for col in required_columns):
            raise ValueError(f"CSV must contain columns: {required_columns}")
        
        print(f"\nResuming processing from row 114")
        print(f"Remaining universities to process: {len(universities_df)}")
        print(f"Starting with: {universities_df.iloc[0]['University']}")
    except FileNotFoundError:
        print(f"\nERROR: Could not find the CSV file at: {input_file}")
        raise
    except Exception as e:
        print(f"\nERROR reading CSV: {str(e)}")
        raise

    # Create a dictionary to store unique clubs and their emails
    unique_clubs = {}  # Format: {(university, club_name, url): set(emails)}

    def normalize_url(url):
        """Normalize URL to avoid duplicates with slight differences"""
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}".rstrip('/')

    # Create a set for seen URLs to quickly check duplicates
    seen_urls = set()

    def is_university_related(url, university_name, abbreviation):
        """Check if URL is likely related to the university"""
        university_domains = [
            '.edu',  # US universities
            university_name.lower().replace(' ', ''),  # Full name
            university_name.lower().split('--')[0],    # First part of name
            university_name.lower().split(',')[0],     # First part before comma
            abbreviation.lower(),                      # University abbreviation
        ]
        return any(domain in url.lower() for domain in university_domains)

    def is_club_email(email, university_name):
        """Check if email is likely from a university club"""
        # Less restrictive email filtering
        # Only exclude obviously non-club emails
        blacklist_domains = [
            'example.com', 'test.com', 'domain.com',
            'support@', 'noreply@', 'admin@', 'webmaster@'
        ]
        
        # Accept .edu emails automatically
        if '.edu' in email.lower():
            return True
        
        # Accept emails that contain university name
        if university_name.lower().replace(' ', '') in email.lower():
            return True
        
        # Reject obviously non-club emails
        if any(domain in email.lower() for domain in blacklist_domains):
            return False
        
        # Accept other emails that appear on valid university club pages
        return True

    def google_search(query, university_name, num_results=20):
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={encoded_query}&num={num_results}&filter=0"  # Added filter=0 for more diverse results
        
        print(f"    Making Google search request for: {query}")
        driver.get(url)
        
        # Check for CAPTCHA
        captcha_indicators = [
            "Our systems have detected unusual traffic",
            "unusual traffic from your computer network",
            "solve this puzzle",
            "Please try again later",
            "Type the text",
            "id=\"captcha\"",
            "recaptcha",
        ]
        
        page_source = driver.page_source.lower()
        if any(indicator.lower() in page_source for indicator in captcha_indicators):
            print("\n🚨 CAPTCHA detected! Please solve the CAPTCHA...")
            # Make a sound to notify user (works on Unix-like systems)
            print('\a')  # Terminal bell
            input("Press Enter after solving the CAPTCHA...")
            print("Continuing with search...")
            time.sleep(5)  # Added extra delay after CAPTCHA
        
        try:
            # Reduce wait time and use a more specific selector
            wait = WebDriverWait(driver, 3)  # Reduced from 5 to 3 seconds
            results = wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div.g div.yuRUbf > a, div.g a[href^='http']")
            ))
            
            # Process results in batches for speed
            search_results = []
            batch_size = 5  # Process 5 results at a time
            
            for i in range(0, len(results), batch_size):
                batch = results[i:i + batch_size]
                
                for result in batch:
                    try:
                        href = result.get_attribute('href')
                        if not href or not href.startswith('http'):
                            continue
                        
                        normalized_url = normalize_url(href)
                        if normalized_url in seen_urls:
                            continue
                        
                        if (not any(domain in href.lower() for domain in excluded_domains) and
                            is_university_related(href, university_name, abbreviation)):
                            
                            seen_urls.add(normalized_url)
                            search_results.append(href)
                            print(f"    Found new result: {href[:60]}...")
                            
                            if len(search_results) >= 8:  # Reduced from 10 to 8 for speed
                                return search_results
                                
                    except Exception:
                        continue
                
                # Shorter delay between batches
                time.sleep(0.5)
            
            return search_results
            
        except Exception as e:
            print(f"    Error during search: {str(e)}")
            return []

    def clean_email(email):
        """Clean email address by removing trailing punctuation and validating format"""
        # Remove trailing punctuation
        email = email.rstrip('.,;:!?')
        
        # Convert [at] format to standard @ format
        email = re.sub(r'\s*\[at\]\s*', '@', email)
        
        # Filter out emails with numbers after @
        if re.search(r'@.*\d', email):
            return None
        
        # Basic email validation
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            return None
        
        # Filter out Wixpress and similar automated emails
        blacklist_domains = [
            'wixpress.com',
            'sentry.io',
            'mailchimp.com',
            'sendgrid.net',
            'amazonses.com',
            '.png',
            '.jpg',
            '.jpeg',
            '.gif',
            '.webp',
            '.svg'
        ]
        
        # Check if email domain is blacklisted
        if any(domain in email.lower() for domain in blacklist_domains):
            return None
        
        # Filter out emails that look like hashes/automated
        if re.match(r'^[a-f0-9]{32}@', email.lower()):  # Matches 32-char hex strings
            return None
        
        return email

    def process_club_page(url, university, abbreviation, headers):
        """Process a single club page and return relevant information"""
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        club_name = soup.title.string.strip() if soup.title else "Unknown Club"
        
        # Skip if club name contains admission-related terms
        admission_terms = ['admission', 'admissions', 'apply', 'application']
        if any(term in club_name.lower() for term in admission_terms):
            return None, set()
        
        # Extract and clean emails
        raw_emails = set(re.findall(email_pattern, response.text))
        cleaned_emails = set()
        
        for email in raw_emails:
            cleaned = clean_email(email)
            if cleaned and is_club_email(cleaned, university):
                cleaned_emails.add(cleaned)
        
        return club_name, cleaned_emails

    def check_university_duplicates(results_for_university):
        """
        Check for and merge duplicate club entries within a university's results.
        Returns deduplicated results based on similar club names and URLs.
        """
        # Dictionary to store merged results: {normalized_name: (best_name, emails, urls)}
        merged_results = {}
        
        for univ, abbr, club_name, url, emails in results_for_university:
            # Normalize club name for comparison (lowercase, remove special chars)
            norm_name = re.sub(r'[^a-z0-9]', '', club_name.lower())
            
            # If very short normalized name, include part of URL to avoid over-merging
            if len(norm_name) < 10:
                domain = urlparse(url).netloc
                norm_name = f"{norm_name}_{domain}"
            
            if norm_name in merged_results:
                # Merge with existing entry
                existing_name, existing_emails, existing_urls = merged_results[norm_name]
                # Keep the longer/more complete club name
                best_name = existing_name if len(existing_name) > len(club_name) else club_name
                merged_results[norm_name] = (
                    best_name,
                    existing_emails.union(emails),
                    existing_urls + [url]
                )
            else:
                # Create new entry
                merged_results[norm_name] = (club_name, emails, [url])
        
        # Convert back to original format
        deduped_results = []
        for norm_name, (club_name, emails, urls) in merged_results.items():
            # Use the first URL as primary, but store others in the club name
            primary_url = urls[0]
            if len(urls) > 1:
                club_name = f"{club_name} (Additional URLs: {', '.join(urls[1:])}))"
            deduped_results.append((univ, abbr, club_name, primary_url, emails))
        
        return deduped_results

    def process_university(university, abbreviation, search_queries=None):
        """Process a single university"""
        local_results = []
        
        # Define search queries using both full name and abbreviation
        search_queries = [
            # Full name queries
            
            # Abbreviation-based queries
            f"{abbreviation} investment club",
            f"{abbreviation} trading club",
            f"{abbreviation} finance club",
            f"{abbreviation} traders",
            
            # Generic queries with abbreviation
            f"{abbreviation} value investing",
            f"{abbreviation} undergrad trading",
            f"{abbreviation} alternative investment",
            f"{abbreviation} sales and trading",
            f"traders at {abbreviation}"
        ]
        
        for query in search_queries:
            search_results = google_search(query, university, abbreviation)
            
            # Process URLs in parallel
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_url = {
                    executor.submit(process_club_page, url, university, abbreviation, {'User-Agent': random.choice(user_agents)}): url 
                    for url in search_results
                }
                
                for future in as_completed(future_to_url):
                    try:
                        club_name, relevant_emails = future.result()
                        if club_name and relevant_emails:
                            local_results.append((university, abbreviation, club_name, future_to_url[future], relevant_emails))
                    except Exception:
                        continue
            
            # Add longer delay between queries
            time.sleep(random.uniform(4, 6))  # Increased from 1
        
        # Add deduplication step before returning results
        deduped_results = check_university_duplicates(local_results)
        return deduped_results

    def check_all_duplicates(all_results):
        """
        Check for and merge duplicate club entries across all universities.
        Returns deduplicated results based on similar club names and URLs.
        """
        merged_results = {}
        
        for univ, abbr, club_name, url, emails in all_results:
            # Normalize club name for comparison (lowercase, remove special chars)
            norm_name = re.sub(r'[^a-z0-9]', '', club_name.lower())
            
            # If very short normalized name, include part of URL to avoid over-merging
            if len(norm_name) < 10:
                domain = urlparse(url).netloc
                norm_name = f"{norm_name}_{domain}"
            
            if norm_name in merged_results:
                # Merge with existing entry
                existing_univ, existing_abbr, existing_name, existing_emails, existing_urls = merged_results[norm_name]
                # Keep the longer/more complete club name
                best_name = existing_name if len(existing_name) > len(club_name) else club_name
                # Combine university names if different
                if univ != existing_univ:
                    combined_univ = f"{existing_univ} & {univ}"
                    combined_abbr = f"{existing_abbr}/{abbr}"
                else:
                    combined_univ = existing_univ
                    combined_abbr = existing_abbr
                    
                merged_results[norm_name] = (
                    combined_univ,
                    combined_abbr,
                    best_name,
                    existing_emails.union(emails),
                    existing_urls + [url]
                )
            else:
                # Create new entry
                merged_results[norm_name] = (univ, abbr, club_name, emails, [url])
        
        # Convert back to original format
        deduped_results = []
        for norm_name, (univ, abbr, club_name, emails, urls) in merged_results.items():
            # Use the first URL as primary, but store others in the club name
            primary_url = urls[0]
            if len(urls) > 1:
                club_name = f"{club_name} (Additional URLs: {', '.join(urls[1:])}))"
            deduped_results.append((univ, abbr, club_name, primary_url, emails))
        
        return deduped_results

    def write_to_csv(results, output_file):
        """Create a DataFrame from the results and write it to a CSV file"""
        result_df = pd.DataFrame(results)
        result_df.to_csv(output_file, index=False, sep=',', escapechar='\\')

    # Process each university
    total_universities = len(universities_df)
    for index, row in universities_df.iterrows():
        university = row['University']
        abbreviation = row['Abbreviation']
        print(f"\n[{index + 1}/{total_universities}] Processing {university} ({abbreviation})...")
        
        try:
            results_for_university = process_university(university, abbreviation)
            
            # Add results to unique_clubs
            for univ, abbr, club_name, url, emails in results_for_university:
                club_key = (univ, club_name, url)
                if club_key not in unique_clubs:
                    unique_clubs[club_key] = set()
                unique_clubs[club_key].update(emails)
                
                print(f"      ✓ Found club: {club_name}")
                print(f"      ✓ Found {len(emails)} new email(s)")
                
        except Exception as e:
            print(f"  ✗ Error processing {university}: {str(e)}")
            continue

    # Create rows for the DataFrame
    results = []
    for (university, club_name, url), emails in unique_clubs.items():
        # Create one row per email
        for email in emails:
            results.append({
                "University": university,
                "Club Name": club_name,
                "Website URL": url,
                "Email": email  # Changed from "Emails" to "Email" since it's one per row
            })

    print("\nCreating output file...")
    
    # Create a DataFrame from the results and write it to a CSV file
    output_file = "/Users/erikwang/Documents/Dub/Email_Scraper/Output/clubs_output_continued_final.csv"
    result_df = pd.DataFrame(results)
    result_df.to_csv(output_file, index=False, sep=',', escapechar='\\')
    
    print(f"\nProcessing complete!")
    print(f"Found information for {len(unique_clubs)} unique clubs")
    print(f"Found {len(results)} total email contacts")
    print(f"Results have been written to: {output_file}")

    # After all universities are processed, perform global deduplication
    all_results = []
    for results in unique_clubs.values():
        all_results.extend(results)
    
    final_results = check_all_duplicates(all_results)
    
    # Sort results by university name
    final_results.sort(key=lambda x: x[0])
    
    # Write the deduplicated results to the output file
    write_to_csv(final_results, output_file)

finally:
    # Close the browser
    driver.quit()
