import requests
from bs4 import BeautifulSoup
import re
import time
import urllib.parse
from typing import List, Set
import trafilatura

class EmailScraper:
    def __init__(self, delay: int = 2, max_pages: int = 5):
        """
        Initialize the email scraper with rate limiting and page limits.
        
        Args:
            delay: Delay between requests in seconds
            max_pages: Maximum number of pages to scrape per website
        """
        self.delay = delay
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Email regex pattern (RFC 5322 compliant)
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        
        # Common contact page patterns
        self.contact_patterns = [
            '/contact', '/contact-us', '/about', '/about-us', '/team',
            '/staff', '/directory', '/people', '/leadership'
        ]
    
    def extract_emails_from_text(self, text: str) -> Set[str]:
        """Extract email addresses from text using regex."""
        if not text:
            return set()
        
        emails = set(self.email_pattern.findall(text))
        
        # Filter out common false positives
        filtered_emails = set()
        for email in emails:
            email_lower = email.lower()
            # Skip common placeholder emails
            if not any(placeholder in email_lower for placeholder in [
                'example.com', 'test.com', 'domain.com', 'yoursite.com',
                'yourdomain.com', 'email.com', 'mail.com', 'noreply@',
                'no-reply@', 'admin@localhost', '.png', '.jpg', '.gif'
            ]):
                filtered_emails.add(email)
        
        return filtered_emails
    
    def get_page_content(self, url: str) -> tuple:
        """
        Fetch page content and return both raw HTML and extracted text.
        
        Returns:
            tuple: (html_content, text_content)
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Get raw HTML
            html_content = response.text
            
            # Extract clean text using trafilatura
            text_content = trafilatura.extract(html_content) or ""
            
            return html_content, text_content
            
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return "", ""
    
    def find_contact_pages(self, base_url: str, html_content: str) -> List[str]:
        """Find potential contact pages from the main page."""
        contact_urls = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all links
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                
                # Convert relative URLs to absolute
                full_url = urllib.parse.urljoin(base_url, href)
                
                # Check if link text or URL contains contact-related keywords
                link_text = link.get_text().lower().strip()
                href_lower = href.lower()
                
                contact_keywords = [
                    'contact', 'about', 'team', 'staff', 'directory',
                    'people', 'leadership', 'management', 'support'
                ]
                
                if any(keyword in link_text for keyword in contact_keywords) or \
                   any(pattern in href_lower for pattern in self.contact_patterns):
                    if full_url not in contact_urls and full_url != base_url:
                        contact_urls.append(full_url)
                        
        except Exception as e:
            print(f"Error finding contact pages: {str(e)}")
        
        return contact_urls[:self.max_pages - 1]  # Limit contact pages
    
    def extract_social_links(self, html_content: str) -> List[str]:
        """Extract social media profile links."""
        social_urls = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Social media domains
            social_domains = [
                'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
                'youtube.com', 'tiktok.com', 'pinterest.com'
            ]
            
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                if any(domain in href for domain in social_domains):
                    social_urls.append(href)
                    
        except Exception as e:
            print(f"Error extracting social links: {str(e)}")
        
        return social_urls
    
    def scrape_website(self, url: str, scrape_options: List[str]) -> List[str]:
        """
        Main scraping function that extracts emails from a website.
        
        Args:
            url: Website URL to scrape
            scrape_options: List of scraping sources to include
            
        Returns:
            List of unique email addresses found
        """
        all_emails = set()
        processed_urls = set()
        
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Start with main page
            if "Main content" in scrape_options:
                print(f"Scraping main page: {url}")
                html_content, text_content = self.get_page_content(url)
                
                if html_content:
                    # Extract emails from both HTML and text content
                    emails_from_html = self.extract_emails_from_text(html_content)
                    emails_from_text = self.extract_emails_from_text(text_content)
                    all_emails.update(emails_from_html)
                    all_emails.update(emails_from_text)
                    
                    processed_urls.add(url)
                    
                    # Find contact pages if requested
                    if any(option in scrape_options for option in ["Contact pages", "About pages"]):
                        contact_urls = self.find_contact_pages(url, html_content)
                        
                        for contact_url in contact_urls:
                            if contact_url not in processed_urls:
                                print(f"Scraping contact page: {contact_url}")
                                time.sleep(self.delay)  # Rate limiting
                                
                                contact_html, contact_text = self.get_page_content(contact_url)
                                if contact_html:
                                    contact_emails_html = self.extract_emails_from_text(contact_html)
                                    contact_emails_text = self.extract_emails_from_text(contact_text)
                                    all_emails.update(contact_emails_html)
                                    all_emails.update(contact_emails_text)
                                    
                                processed_urls.add(contact_url)
                    
                    # Extract social media links if requested
                    if "Social media links" in scrape_options:
                        social_urls = self.extract_social_links(html_content)
                        
                        for social_url in social_urls[:3]:  # Limit social media scraping
                            if social_url not in processed_urls:
                                print(f"Checking social media: {social_url}")
                                time.sleep(self.delay)
                                
                                social_html, social_text = self.get_page_content(social_url)
                                if social_html:
                                    social_emails_html = self.extract_emails_from_text(social_html)
                                    social_emails_text = self.extract_emails_from_text(social_text)
                                    all_emails.update(social_emails_html)
                                    all_emails.update(social_emails_text)
                                
                                processed_urls.add(social_url)
                    
                    # Special focus on footer content if requested
                    if "Footer" in scrape_options:
                        soup = BeautifulSoup(html_content, 'html.parser')
                        footer_elements = soup.find_all(['footer', 'div'], 
                                                      class_=re.compile(r'footer|contact|info', re.I))
                        
                        for element in footer_elements:
                            footer_text = element.get_text() if element else ""
                            footer_emails = self.extract_emails_from_text(footer_text)
                            all_emails.update(footer_emails)
            
        except Exception as e:
            print(f"Error scraping website {url}: {str(e)}")
            raise e
        
        return list(all_emails)
    
    def extract_from_contact_form(self, url: str) -> List[str]:
        """
        Extract emails from contact forms (from form action URLs, hidden fields, etc.)
        """
        emails = set()
        
        try:
            html_content, _ = self.get_page_content(url)
            if not html_content:
                return list(emails)
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for contact forms
            forms = soup.find_all('form')
            
            for form in forms:
                # Check form action URL
                action = form.get('action', '')
                if action:
                    form_emails = self.extract_emails_from_text(action)
                    emails.update(form_emails)
                
                # Check hidden input fields
                hidden_inputs = form.find_all('input', type='hidden')
                for inp in hidden_inputs:
                    value = inp.get('value', '')
                    if value:
                        hidden_emails = self.extract_emails_from_text(value)
                        emails.update(hidden_emails)
                
                # Check form labels and text
                form_text = form.get_text()
                form_emails = self.extract_emails_from_text(form_text)
                emails.update(form_emails)
                
        except Exception as e:
            print(f"Error extracting from contact form: {str(e)}")
        
        return list(emails)
