import streamlit as st
import pandas as pd
import re
import time
from email_scraper import EmailScraper
from email_validator import EmailValidator
from utils import export_to_csv, rate_limiter
from database import db_manager, ValidationResult, ScrapingSession, ValidationSession
import os
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="Email Scraper & Validator",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
@st.cache_resource
def init_database():
    """Initialize database connection and create tables"""
    try:
        db_manager.create_tables()
        return True
    except Exception as e:
        st.error(f"Database initialization failed: {str(e)}")
        return False

# Initialize session state
if 'scraped_emails' not in st.session_state:
    st.session_state.scraped_emails = []
if 'validated_emails' not in st.session_state:
    st.session_state.validated_emails = []
if 'scraping_in_progress' not in st.session_state:
    st.session_state.scraping_in_progress = False
if 'validation_in_progress' not in st.session_state:
    st.session_state.validation_in_progress = False
if 'current_scraping_session' not in st.session_state:
    st.session_state.current_scraping_session = None
if 'current_validation_session' not in st.session_state:
    st.session_state.current_validation_session = None
if 'use_database' not in st.session_state:
    st.session_state.use_database = True

def main():
    # Initialize database
    if st.session_state.use_database:
        db_ready = init_database()
        if not db_ready:
            st.error("Database connection failed. Running in session-only mode.")
            st.session_state.use_database = False
    
    st.title("📧 Email Scraper & Validator")
    st.write("Extract and validate email addresses from websites with comprehensive verification.")
    
    # Database status indicator
    if st.session_state.use_database:
        st.success("🗄️ Database connected - Data will be saved persistently")
    else:
        st.warning("⚠️ Session-only mode - Data will be lost when you refresh")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Rate limiting settings
        st.subheader("Rate Limiting")
        delay_between_requests = st.slider("Delay between requests (seconds)", 1, 10, 2)
        max_pages = st.number_input("Maximum pages to scrape", min_value=1, max_value=50, value=5)
        
        # Validation settings
        st.subheader("Validation Settings")
        enable_smtp_check = st.checkbox("Enable SMTP verification", value=True)
        timeout_seconds = st.slider("Request timeout (seconds)", 5, 30, 10)
        
        # Database settings
        st.subheader("Database Settings")
        st.session_state.use_database = st.checkbox("Use database storage", value=st.session_state.use_database)
        
        if st.session_state.use_database:
            st.write("📊 **Database Stats**")
            try:
                stats = db_manager.get_validation_stats()
                st.metric("Total Emails", stats['total_emails'])
                st.metric("Valid Emails", f"{stats['valid_emails']} ({stats['valid_percentage']:.1f}%)")
            except Exception as e:
                st.write("Database stats unavailable")
        
        # Load from database
        if st.session_state.use_database and st.button("📥 Load Recent Data"):
            try:
                recent_results = db_manager.get_validation_results(limit=1000)
                if recent_results:
                    # Convert to format expected by session state
                    loaded_results = []
                    loaded_emails = []
                    
                    for result in recent_results:
                        result_dict = {
                            'email': result.email,
                            'is_valid': result.is_valid,
                            'format_valid': result.format_valid,
                            'blacklist_check': result.blacklist_check,
                            'dns_valid': result.dns_valid,
                            'smtp_valid': result.smtp_valid,
                            'error_message': result.error_message,
                            'validation_details': result.validation_details or {}
                        }
                        loaded_results.append(result_dict)
                        loaded_emails.append(result.email)
                    
                    st.session_state.validated_emails = loaded_results
                    st.session_state.scraped_emails = loaded_emails
                    st.success(f"Loaded {len(loaded_results)} validation results from database")
                    st.rerun()
                else:
                    st.info("No data found in database")
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
    
    # Main interface tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🕷️ Email Scraping", "📦 Bulk Operations", "✅ Email Validation", "📊 Results & Export", "🗄️ Database"])
    
    # Email Scraping Tab
    with tab1:
        st.header("Extract Emails from Websites")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            url_input = st.text_input(
                "Enter website URL:",
                placeholder="https://example.com",
                help="Enter the URL of the website to scrape for email addresses"
            )
            
            scrape_options = st.multiselect(
                "Scraping Sources:",
                ["Main content", "Contact pages", "About pages", "Footer", "Social media links"],
                default=["Main content", "Contact pages", "Footer"]
            )
        
        with col2:
            st.write("**Scraping Statistics**")
            if st.session_state.scraped_emails:
                st.metric("Total Emails Found", len(st.session_state.scraped_emails))
                unique_domains = len(set([email.split('@')[1] for email in st.session_state.scraped_emails if '@' in email]))
                st.metric("Unique Domains", unique_domains)
        
        if st.button("🚀 Start Scraping", disabled=st.session_state.scraping_in_progress):
            if url_input:
                st.session_state.scraping_in_progress = True
                
                with st.spinner("Scraping emails from website..."):
                    try:
                        scraper = EmailScraper(delay=delay_between_requests, max_pages=max_pages)
                        emails = scraper.scrape_website(url_input, scrape_options)
                        
                        if emails:
                            st.session_state.scraped_emails = list(set(emails))  # Remove duplicates
                            
                            # Save to database if enabled
                            if st.session_state.use_database:
                                try:
                                    # Create scraping session
                                    scraping_session = db_manager.create_scraping_session(
                                        urls=[url_input],
                                        options=scrape_options
                                    )
                                    
                                    # Add emails to database
                                    db_manager.bulk_add_emails(st.session_state.scraped_emails)
                                    
                                    # Update session
                                    domains = set([email.split('@')[1] for email in st.session_state.scraped_emails if '@' in email])
                                    db_manager.update_scraping_session(
                                        scraping_session.id,
                                        emails_found=len(st.session_state.scraped_emails),
                                        unique_domains=len(domains),
                                        status="completed"
                                    )
                                    
                                    st.session_state.current_scraping_session = scraping_session.id
                                except Exception as e:
                                    st.warning(f"Database save failed: {str(e)}")
                            
                            st.success(f"✅ Found {len(st.session_state.scraped_emails)} unique email addresses!")
                            
                            # Display preview
                            st.subheader("Found Emails Preview:")
                            preview_df = pd.DataFrame({
                                'Email': st.session_state.scraped_emails[:10],
                                'Domain': [email.split('@')[1] if '@' in email else 'Invalid' 
                                          for email in st.session_state.scraped_emails[:10]]
                            })
                            st.dataframe(preview_df, use_container_width=True)
                            
                            if len(st.session_state.scraped_emails) > 10:
                                st.info(f"Showing first 10 results. Total found: {len(st.session_state.scraped_emails)}")
                        else:
                            st.warning("No email addresses found on this website.")
                            
                    except Exception as e:
                        st.error(f"Error during scraping: {str(e)}")
                    
                    finally:
                        st.session_state.scraping_in_progress = False
                        st.rerun()
            else:
                st.error("Please enter a valid URL.")
    
    # Bulk Operations Tab
    with tab2:
        st.header("Bulk Email Operations")
        
        # Bulk Scraping Section
        st.subheader("📋 Bulk Website Scraping")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # URL input methods
            url_input_method = st.radio(
                "Choose input method:",
                ["Text area", "Upload file"],
                horizontal=True
            )
            
            if url_input_method == "Text area":
                bulk_urls = st.text_area(
                    "Enter website URLs (one per line):",
                    placeholder="https://example1.com\nhttps://example2.com\nhttps://example3.com",
                    height=150,
                    help="Enter up to 50 URLs, one per line"
                )
                url_list = [url.strip() for url in bulk_urls.split('\n') if url.strip()]
            else:
                uploaded_urls_file = st.file_uploader(
                    "Upload CSV file with URLs:",
                    type=['csv', 'txt'],
                    help="CSV file should have a 'url' column, or text file with one URL per line"
                )
                url_list = []
                
                if uploaded_urls_file is not None:
                    try:
                        if uploaded_urls_file.name.endswith('.csv'):
                            df_urls = pd.read_csv(uploaded_urls_file)
                            if 'url' in df_urls.columns:
                                url_list = df_urls['url'].dropna().astype(str).tolist()
                            else:
                                st.error("CSV file must contain a 'url' column.")
                        else:
                            # Text file
                            content = uploaded_urls_file.read().decode('utf-8')
                            url_list = [url.strip() for url in content.split('\n') if url.strip()]
                        
                        if url_list:
                            st.success(f"Loaded {len(url_list)} URLs from file!")
                    except Exception as e:
                        st.error(f"Error reading file: {str(e)}")
        
        with col2:
            st.write("**Bulk Scraping Info**")
            if url_list:
                st.metric("URLs to Process", len(url_list))
                if len(url_list) > 50:
                    st.warning("⚠️ Limiting to first 50 URLs for performance")
                    url_list = url_list[:50]
                
                # Estimate processing time
                estimated_time = len(url_list) * (delay_between_requests + 2)  # 2 seconds base time per URL
                if estimated_time < 60:
                    st.metric("Estimated Time", f"{estimated_time:.0f} seconds")
                else:
                    st.metric("Estimated Time", f"{estimated_time/60:.1f} minutes")
        
        # Bulk scraping controls
        if url_list:
            bulk_scrape_options = st.multiselect(
                "Scraping Sources for All URLs:",
                ["Main content", "Contact pages", "About pages", "Footer"],
                default=["Main content", "Contact pages"]
            )
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🚀 Start Bulk Scraping", disabled=st.session_state.scraping_in_progress):
                    st.session_state.scraping_in_progress = True
                    
                    # Progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_container = st.empty()
                    
                    all_bulk_emails = []
                    processed_count = 0
                    
                    try:
                        scraper = EmailScraper(delay=delay_between_requests, max_pages=3)  # Limit pages for bulk
                        
                        for i, url in enumerate(url_list):
                            status_text.text(f"Processing {i+1}/{len(url_list)}: {url}")
                            
                            try:
                                emails = scraper.scrape_website(url, bulk_scrape_options)
                                all_bulk_emails.extend(emails)
                                processed_count += 1
                                
                                # Update progress
                                progress_bar.progress((i + 1) / len(url_list))
                                
                                # Show interim results
                                with results_container.container():
                                    st.write(f"**Progress:** {processed_count}/{len(url_list)} URLs processed")
                                    st.write(f"**Total Emails Found:** {len(set(all_bulk_emails))}")
                                    
                            except Exception as e:
                                st.warning(f"Failed to scrape {url}: {str(e)}")
                            
                            # Rate limiting between URLs
                            if i < len(url_list) - 1:
                                time.sleep(delay_between_requests)
                        
                        # Remove duplicates and update session
                        unique_emails = list(set(all_bulk_emails))
                        st.session_state.scraped_emails = unique_emails
                        
                        # Save to database if enabled
                        if st.session_state.use_database and unique_emails:
                            try:
                                # Create bulk scraping session
                                scraping_session = db_manager.create_scraping_session(
                                    session_name=f"Bulk_Scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                    urls=url_list,
                                    options=bulk_scrape_options
                                )
                                
                                # Add emails to database
                                db_manager.bulk_add_emails(unique_emails)
                                
                                # Update session
                                domains = set([email.split('@')[1] for email in unique_emails if '@' in email])
                                db_manager.update_scraping_session(
                                    scraping_session.id,
                                    emails_found=len(unique_emails),
                                    unique_domains=len(domains),
                                    status="completed"
                                )
                                
                                st.session_state.current_scraping_session = scraping_session.id
                            except Exception as e:
                                st.warning(f"Database save failed: {str(e)}")
                        
                        st.success(f"✅ Bulk scraping completed! Found {len(unique_emails)} unique emails from {processed_count} websites.")
                        
                        # Show summary
                        if unique_emails:
                            domains = set([email.split('@')[1] for email in unique_emails if '@' in email])
                            st.info(f"📊 Summary: {len(unique_emails)} emails from {len(domains)} different domains")
                            
                    except Exception as e:
                        st.error(f"Bulk scraping error: {str(e)}")
                    
                    finally:
                        st.session_state.scraping_in_progress = False
                        progress_bar.empty()
                        status_text.empty()
                        st.rerun()
            
            with col2:
                if st.button("📋 Preview URLs"):
                    with st.expander("URLs to be processed:", expanded=True):
                        for i, url in enumerate(url_list[:10], 1):
                            st.write(f"{i}. {url}")
                        if len(url_list) > 10:
                            st.write(f"... and {len(url_list) - 10} more URLs")
            
            with col3:
                if st.button("🔄 Clear URLs"):
                    st.rerun()
        
        st.divider()
        
        # Bulk Email Import Section
        st.subheader("📥 Bulk Email Import")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Email input methods
            email_input_method = st.radio(
                "Choose email input method:",
                ["Text area", "Upload CSV file"],
                horizontal=True,
                key="email_input_method"
            )
            
            if email_input_method == "Text area":
                bulk_emails_text = st.text_area(
                    "Enter email addresses (one per line):",
                    placeholder="user1@example.com\nuser2@company.com\ncontact@business.org",
                    height=150,
                    help="Enter up to 1000 email addresses, one per line"
                )
                email_list = [email.strip() for email in bulk_emails_text.split('\n') if email.strip() and '@' in email]
            else:
                uploaded_emails_file = st.file_uploader(
                    "Upload CSV file with email addresses:",
                    type=['csv'],
                    help="CSV file should have an 'email' column",
                    key="bulk_email_upload"
                )
                email_list = []
                
                if uploaded_emails_file is not None:
                    try:
                        df_emails = pd.read_csv(uploaded_emails_file)
                        if 'email' in df_emails.columns:
                            email_list = df_emails['email'].dropna().astype(str).tolist()
                            email_list = [email.strip() for email in email_list if '@' in email]
                        else:
                            st.error("CSV file must contain an 'email' column.")
                        
                        if email_list:
                            st.success(f"Loaded {len(email_list)} emails from file!")
                    except Exception as e:
                        st.error(f"Error reading file: {str(e)}")
        
        with col2:
            st.write("**Bulk Import Info**")
            if email_list:
                st.metric("Emails to Import", len(email_list))
                if len(email_list) > 1000:
                    st.warning("⚠️ Limiting to first 1000 emails")
                    email_list = email_list[:1000]
                
                unique_emails = len(set(email_list))
                if unique_emails != len(email_list):
                    st.metric("Unique Emails", unique_emails)
        
        # Bulk import controls
        if email_list:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📥 Import Emails"):
                    # Clean and deduplicate emails
                    from utils import clean_email_list
                    cleaned_emails = clean_email_list(email_list)
                    
                    # Add to session or replace
                    import_mode = st.radio(
                        "Import mode:",
                        ["Add to existing", "Replace existing"],
                        key="import_mode"
                    )
                    
                    if import_mode == "Add to existing":
                        existing_emails = set(st.session_state.scraped_emails)
                        new_emails = [email for email in cleaned_emails if email not in existing_emails]
                        st.session_state.scraped_emails.extend(new_emails)
                        st.success(f"✅ Added {len(new_emails)} new emails! Total: {len(st.session_state.scraped_emails)}")
                    else:
                        st.session_state.scraped_emails = cleaned_emails
                        st.success(f"✅ Imported {len(cleaned_emails)} emails!")
                    
                    st.rerun()
            
            with col2:
                if st.button("👀 Preview Emails"):
                    with st.expander("Email addresses to be imported:", expanded=True):
                        for i, email in enumerate(email_list[:20], 1):
                            st.write(f"{i}. {email}")
                        if len(email_list) > 20:
                            st.write(f"... and {len(email_list) - 20} more emails")
            
            with col3:
                if st.button("🧹 Clean & Deduplicate"):
                    from utils import clean_email_list
                    cleaned = clean_email_list(email_list)
                    st.info(f"Original: {len(email_list)} emails")
                    st.info(f"After cleaning: {len(cleaned)} emails")
                    st.info(f"Removed: {len(email_list) - len(cleaned)} duplicates/invalid")
    
    # Email Validation Tab
    with tab3:
        st.header("Validate Email Addresses")
        
        if not st.session_state.scraped_emails:
            st.info("No emails to validate. Please scrape some emails first or upload a file.")
            
            # File upload option
            uploaded_file = st.file_uploader(
                "Or upload a CSV file with email addresses:",
                type=['csv'],
                help="CSV file should have an 'email' column"
            )
            
            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file)
                    if 'email' in df.columns:
                        st.session_state.scraped_emails = df['email'].dropna().tolist()
                        st.success(f"Loaded {len(st.session_state.scraped_emails)} emails from file!")
                    else:
                        st.error("CSV file must contain an 'email' column.")
                except Exception as e:
                    st.error(f"Error reading file: {str(e)}")
        
        if st.session_state.scraped_emails:
            email_count = len(st.session_state.scraped_emails)
            st.write(f"**{email_count} emails ready for validation**")
            
            # Show processing time estimate
            from utils import estimate_processing_time
            est_time = estimate_processing_time(email_count, enable_smtp_check)
            st.info(f"⏱️ Estimated processing time: {est_time}")
            
            # Validation stages info
            with st.expander("📋 Validation Process Details"):
                st.write("""
                **Stage 1: Format Validation**
                - Checks if email follows RFC 5322 compliance
                - Validates basic structure and syntax
                
                **Stage 2: Blacklist Check**
                - Searches against known spam databases
                - Checks for disposable email providers
                
                **Stage 3: DNS Validation**
                - Verifies domain has valid MX records
                - Checks if domain can receive emails
                
                **Stage 4: SMTP Verification**
                - Connects to mail server
                - Verifies if email address exists
                """)
            
            # Bulk validation controls
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Batch size for large datasets
                if email_count > 100:
                    batch_size = st.selectbox(
                        "Batch size:",
                        [50, 100, 200, 500],
                        value=100,
                        help="Process emails in smaller batches to prevent timeouts"
                    )
                else:
                    batch_size = email_count
                
                # Validation mode
                validation_mode = st.selectbox(
                    "Validation mode:",
                    ["Complete (all 4 stages)", "Quick (format + DNS only)", "Format only"],
                    help="Choose validation depth vs speed"
                )
            
            with col2:
                # Continue from interruption option
                if st.session_state.validated_emails:
                    validated_count = len(st.session_state.validated_emails)
                    st.metric("Already Validated", f"{validated_count}/{email_count}")
                    
                    if validated_count < email_count:
                        continue_validation = st.checkbox(
                            "Continue from where left off",
                            value=True,
                            help="Resume validation from previously validated emails"
                        )
                    else:
                        continue_validation = False
                        st.success("All emails already validated!")
                else:
                    continue_validation = False
            
            with col3:
                if st.session_state.validated_emails:
                    valid_count = len([r for r in st.session_state.validated_emails if r['is_valid']])
                    st.metric("Valid Emails", f"{valid_count}/{len(st.session_state.validated_emails)}")
            
            # Main validation button
            if st.button("🔍 Start Bulk Validation", disabled=st.session_state.validation_in_progress):
                st.session_state.validation_in_progress = True
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_container = st.empty()
                
                try:
                    # Configure validator based on mode
                    if validation_mode == "Format only":
                        validator = EmailValidator(enable_smtp=False, timeout=timeout_seconds)
                    elif validation_mode == "Quick (format + DNS only)":
                        validator = EmailValidator(enable_smtp=False, timeout=timeout_seconds)
                    else:
                        validator = EmailValidator(enable_smtp=enable_smtp_check, timeout=timeout_seconds)
                    
                    # Determine which emails to validate
                    if continue_validation and st.session_state.validated_emails:
                        validated_emails_set = set([r['email'] for r in st.session_state.validated_emails])
                        emails_to_validate = [email for email in st.session_state.scraped_emails 
                                            if email not in validated_emails_set]
                        validated_results = st.session_state.validated_emails.copy()
                    else:
                        emails_to_validate = st.session_state.scraped_emails.copy()
                        validated_results = []
                    
                    total_emails = len(emails_to_validate)
                    processed_count = 0
                    
                    # Process in batches
                    for batch_start in range(0, total_emails, batch_size):
                        batch_end = min(batch_start + batch_size, total_emails)
                        batch_emails = emails_to_validate[batch_start:batch_end]
                        
                        status_text.text(f"Processing batch {batch_start//batch_size + 1}: emails {batch_start + 1}-{batch_end}")
                        
                        for i, email in enumerate(batch_emails):
                            global_index = batch_start + i
                            status_text.text(f"Validating {global_index + 1}/{total_emails}: {email}")
                            
                            # Quick validation for format-only mode
                            if validation_mode == "Format only":
                                result = {
                                    'email': email,
                                    'is_valid': validator.validate_format(email),
                                    'format_valid': validator.validate_format(email),
                                    'blacklist_check': True,
                                    'dns_valid': None,
                                    'smtp_valid': None,
                                    'error_message': None if validator.validate_format(email) else 'Invalid format'
                                }
                            else:
                                result = validator.validate_email(email)
                            
                            validated_results.append(result)
                            processed_count += 1
                            
                            # Update progress
                            progress_bar.progress(processed_count / total_emails)
                            
                            # Show interim results every 10 emails
                            if processed_count % 10 == 0 or processed_count == total_emails:
                                with results_container.container():
                                    valid_so_far = len([r for r in validated_results if r['is_valid']])
                                    st.write(f"**Progress:** {processed_count}/{total_emails} validated")
                                    st.write(f"**Valid emails so far:** {valid_so_far}")
                                    st.write(f"**Success rate:** {(valid_so_far/len(validated_results)*100):.1f}%")
                            
                            # Rate limiting
                            if validation_mode != "Format only" and i < len(batch_emails) - 1:
                                time.sleep(max(0.1, delay_between_requests / 10))  # Faster for bulk
                        
                        # Batch completed message
                        st.info(f"Batch {batch_start//batch_size + 1} completed")
                    
                    # Save results to database if enabled
                    if st.session_state.use_database:
                        try:
                            # Create validation session if not exists
                            if not st.session_state.current_validation_session:
                                validation_session = db_manager.create_validation_session(
                                    session_name=f"Validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                    total_emails=len(emails_to_validate),
                                    validation_mode=validation_mode.lower().replace(' ', '_'),
                                    batch_size=batch_size
                                )
                                st.session_state.current_validation_session = validation_session.id
                            
                            # Save validation results in bulk
                            db_manager.bulk_save_validation_results(validated_results)
                            
                            # Update validation session
                            valid_count = len([r for r in validated_results if r['is_valid']])
                            db_manager.update_validation_session(
                                st.session_state.current_validation_session,
                                processed_emails=len(validated_results),
                                valid_emails=valid_count,
                                status="completed"
                            )
                        except Exception as e:
                            st.warning(f"Database save failed: {str(e)}")
                    
                    # Update session state
                    st.session_state.validated_emails = validated_results
                    
                    # Final summary
                    valid_count = len([r for r in validated_results if r['is_valid']])
                    success_rate = (valid_count / len(validated_results)) * 100 if validated_results else 0
                    
                    st.success(f"✅ Bulk validation completed!")
                    st.balloons()
                    
                    # Show detailed summary
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Processed", len(validated_results))
                    with col2:
                        st.metric("Valid Emails", valid_count)
                    with col3:
                        st.metric("Success Rate", f"{success_rate:.1f}%")
                    
                except Exception as e:
                    st.error(f"Validation error: {str(e)}")
                
                finally:
                    st.session_state.validation_in_progress = False
                    progress_bar.empty()
                    status_text.empty()
                    st.rerun()
    
    # Results & Export Tab
    with tab4:
        st.header("Validation Results & Export")
        
        if st.session_state.validated_emails:
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            
            total_emails = len(st.session_state.validated_emails)
            valid_emails = len([r for r in st.session_state.validated_emails if r['is_valid']])
            format_valid = len([r for r in st.session_state.validated_emails if r['format_valid']])
            dns_valid = len([r for r in st.session_state.validated_emails if r['dns_valid']])
            
            col1.metric("Total Emails", total_emails)
            col2.metric("Valid Emails", valid_emails, f"{(valid_emails/total_emails)*100:.1f}%")
            col3.metric("Format Valid", format_valid)
            col4.metric("DNS Valid", dns_valid)
            
            # Results table
            st.subheader("Detailed Results")
            
            # Convert results to DataFrame
            df_results = pd.DataFrame(st.session_state.validated_emails)
            
            # Add status indicators
            df_results['Status'] = df_results.apply(
                lambda row: "✅ Valid" if row['is_valid'] else "❌ Invalid", axis=1
            )
            
            # Reorder columns for better display
            display_columns = ['email', 'Status', 'format_valid', 'blacklist_check', 'dns_valid', 'smtp_valid', 'error_message']
            df_display = df_results[display_columns].copy()
            
            # Rename columns for better readability
            df_display.columns = ['Email', 'Status', 'Format', 'Blacklist', 'DNS', 'SMTP', 'Error']
            
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                status_filter = st.selectbox("Filter by status:", ["All", "Valid only", "Invalid only"])
            with col2:
                domain_filter = st.selectbox(
                    "Filter by domain:", 
                    ["All"] + sorted(list(set([email.split('@')[1] for email in df_results['email'] if '@' in email])))
                )
            
            # Apply filters
            filtered_df = df_display.copy()
            if status_filter == "Valid only":
                filtered_df = filtered_df[filtered_df['Status'] == "✅ Valid"]
            elif status_filter == "Invalid only":
                filtered_df = filtered_df[filtered_df['Status'] == "❌ Invalid"]
            
            if domain_filter != "All":
                filtered_df = filtered_df[filtered_df['Email'].astype(str).str.contains(f"@{domain_filter}")]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Advanced Analysis
            st.subheader("📈 Advanced Analysis")
            
            # Generate analysis
            from utils import format_validation_summary, group_emails_by_domain
            analysis = format_validation_summary(st.session_state.validated_emails)
            
            if analysis:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Validation Summary**")
                    st.metric("Success Rate", f"{analysis['valid_percentage']:.1f}%")
                    st.metric("Format Valid", f"{analysis['format_valid']}/{analysis['total_emails']}")
                    st.metric("DNS Valid", f"{analysis['dns_valid']}/{analysis['total_emails']}")
                    st.metric("SMTP Valid", f"{analysis['smtp_valid']}/{analysis['total_emails']}")
                
                with col2:
                    st.write("**Top Domains**")
                    domain_df = pd.DataFrame(analysis['top_domains'][:5], columns=['Domain', 'Count'])
                    st.dataframe(domain_df, hide_index=True)
                    
                    st.metric("Unique Domains", analysis['unique_domains'])
                
                # Error analysis
                if analysis['error_types']:
                    st.write("**Common Error Types**")
                    error_df = pd.DataFrame(list(analysis['error_types'].items()), columns=['Error Type', 'Count'])
                    error_df = error_df.sort_values('Count', ascending=False)
                    st.dataframe(error_df, hide_index=True)
            
            st.divider()
            
            # Bulk Export Options
            st.subheader("📦 Bulk Export Options")
            
            # Export format selection
            col1, col2 = st.columns(2)
            
            with col1:
                export_format = st.selectbox(
                    "Export format:",
                    ["CSV", "Excel (XLSX)", "JSON"],
                    help="Choose the format for your exported data"
                )
                
                export_scope = st.selectbox(
                    "Export scope:",
                    ["All results", "Valid emails only", "Invalid emails only", "By domain"],
                    help="Choose which emails to include in export"
                )
            
            with col2:
                if export_scope == "By domain":
                    available_domains = sorted(list(set([email.split('@')[1] for email in df_results['email'] if '@' in email])))
                    selected_domains = st.multiselect(
                        "Select domains to export:",
                        available_domains,
                        help="Choose specific domains to export"
                    )
                
                include_details = st.checkbox(
                    "Include validation details",
                    value=True,
                    help="Include detailed validation information in export"
                )
            
            # Export buttons
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("📥 Export Results"):
                    # Filter data based on scope
                    if export_scope == "All results":
                        export_data = st.session_state.validated_emails
                    elif export_scope == "Valid emails only":
                        export_data = [r for r in st.session_state.validated_emails if r['is_valid']]
                    elif export_scope == "Invalid emails only":
                        export_data = [r for r in st.session_state.validated_emails if not r['is_valid']]
                    elif export_scope == "By domain" and 'selected_domains' in locals():
                        export_data = [r for r in st.session_state.validated_emails 
                                     if any(domain in r['email'] for domain in selected_domains)]
                    else:
                        export_data = st.session_state.validated_emails
                    
                    if export_data:
                        timestamp = int(time.time())
                        
                        if export_format == "CSV":
                            csv_data = export_to_csv(export_data)
                            st.download_button(
                                label="Download CSV",
                                data=csv_data,
                                file_name=f"email_validation_{export_scope.lower().replace(' ', '_')}_{timestamp}.csv",
                                mime="text/csv"
                            )
                        
                        elif export_format == "Excel (XLSX)":
                            # Create Excel file
                            import io
                            output = io.BytesIO()
                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                export_df = pd.DataFrame(export_data)
                                export_df.to_excel(writer, sheet_name='Validation Results', index=False)
                                
                                # Add summary sheet
                                if analysis:
                                    summary_data = {
                                        'Metric': ['Total Emails', 'Valid Emails', 'Success Rate', 'Unique Domains'],
                                        'Value': [analysis['total_emails'], analysis['valid_emails'], 
                                                f"{analysis['valid_percentage']:.1f}%", analysis['unique_domains']]
                                    }
                                    summary_df = pd.DataFrame(summary_data)
                                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                            
                            st.download_button(
                                label="Download Excel",
                                data=output.getvalue(),
                                file_name=f"email_validation_{export_scope.lower().replace(' ', '_')}_{timestamp}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        
                        elif export_format == "JSON":
                            import json
                            json_data = json.dumps(export_data, indent=2)
                            st.download_button(
                                label="Download JSON",
                                data=json_data,
                                file_name=f"email_validation_{export_scope.lower().replace(' ', '_')}_{timestamp}.json",
                                mime="application/json"
                            )
                    else:
                        st.warning("No data to export with current filters.")
            
            with col2:
                if st.button("📧 Export Email List"):
                    # Simple email list export
                    if export_scope == "Valid emails only":
                        email_list = [r['email'] for r in st.session_state.validated_emails if r['is_valid']]
                    elif export_scope == "Invalid emails only":
                        email_list = [r['email'] for r in st.session_state.validated_emails if not r['is_valid']]
                    else:
                        email_list = [r['email'] for r in st.session_state.validated_emails]
                    
                    if email_list:
                        email_text = '\n'.join(email_list)
                        st.download_button(
                            label="Download Email List (TXT)",
                            data=email_text,
                            file_name=f"email_list_{export_scope.lower().replace(' ', '_')}_{int(time.time())}.txt",
                            mime="text/plain"
                        )
                    else:
                        st.warning("No emails to export.")
            
            with col3:
                if st.button("📊 Export Analytics"):
                    if analysis:
                        # Create analytics CSV
                        analytics_data = []
                        analytics_data.append(['Metric', 'Value'])
                        analytics_data.append(['Total Emails', analysis['total_emails']])
                        analytics_data.append(['Valid Emails', analysis['valid_emails']])
                        analytics_data.append(['Success Rate (%)', f"{analysis['valid_percentage']:.1f}"])
                        analytics_data.append(['Format Valid', analysis['format_valid']])
                        analytics_data.append(['DNS Valid', analysis['dns_valid']])
                        analytics_data.append(['SMTP Valid', analysis['smtp_valid']])
                        analytics_data.append(['Unique Domains', analysis['unique_domains']])
                        analytics_data.append(['', ''])
                        analytics_data.append(['Top Domains', 'Count'])
                        
                        for domain, count in analysis['top_domains'][:10]:
                            analytics_data.append([domain, count])
                        
                        analytics_csv = '\n'.join([','.join(map(str, row)) for row in analytics_data])
                        
                        st.download_button(
                            label="Download Analytics CSV",
                            data=analytics_csv,
                            file_name=f"email_analytics_{int(time.time())}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("No analytics data available.")
            
            with col4:
                if st.button("🔄 Clear All Data"):
                    st.session_state.scraped_emails = []
                    st.session_state.validated_emails = []
                    st.success("All data cleared!")
                    st.rerun()
        
        else:
            st.info("No validation results available. Please validate some emails first.")
            
            # If database is enabled, try to load recent results
            if st.session_state.use_database:
                st.write("---")
                st.subheader("📥 Load from Database")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Load Recent Results"):
                        try:
                            recent_results = db_manager.get_validation_results(limit=500)
                            if recent_results:
                                # Convert to session format
                                loaded_results = []
                                for result in recent_results:
                                    loaded_results.append({
                                        'email': result.email,
                                        'is_valid': result.is_valid,
                                        'format_valid': result.format_valid,
                                        'blacklist_check': result.blacklist_check,
                                        'dns_valid': result.dns_valid,
                                        'smtp_valid': result.smtp_valid,
                                        'error_message': result.error_message,
                                        'validation_details': result.validation_details or {}
                                    })
                                
                                st.session_state.validated_emails = loaded_results
                                st.success(f"Loaded {len(loaded_results)} results from database")
                                st.rerun()
                            else:
                                st.info("No results found in database")
                        except Exception as e:
                            st.error(f"Error loading from database: {str(e)}")
                
                with col2:
                    search_query = st.text_input("Search emails:", placeholder="domain.com or user@domain.com")
                    if search_query and st.button("Search Database"):
                        try:
                            search_results = db_manager.search_emails(search_query, limit=100)
                            if search_results:
                                # Convert to session format
                                loaded_results = []
                                for result in search_results:
                                    loaded_results.append({
                                        'email': result.email,
                                        'is_valid': result.is_valid,
                                        'format_valid': result.format_valid,
                                        'blacklist_check': result.blacklist_check,
                                        'dns_valid': result.dns_valid,
                                        'smtp_valid': result.smtp_valid,
                                        'error_message': result.error_message,
                                        'validation_details': result.validation_details or {}
                                    })
                                
                                st.session_state.validated_emails = loaded_results
                                st.success(f"Found {len(loaded_results)} results for '{search_query}'")
                                st.rerun()
                            else:
                                st.info(f"No results found for '{search_query}'")
                        except Exception as e:
                            st.error(f"Search error: {str(e)}")
    
    # Database Management Tab
    with tab5:
        st.header("🗄️ Database Management")
        
        if not st.session_state.use_database:
            st.warning("Database storage is disabled. Enable it in the sidebar to use this tab.")
            return
        
        # Database Statistics
        st.subheader("📊 Database Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        try:
            stats = db_manager.get_validation_stats()
            
            with col1:
                st.metric("Total Emails", stats['total_emails'])
                st.metric("Valid Emails", stats['valid_emails'])
                st.metric("Success Rate", f"{stats['valid_percentage']:.1f}%")
            
            with col2:
                st.metric("Format Valid", stats['format_valid'])
                st.metric("DNS Valid", stats['dns_valid'])
                st.metric("SMTP Valid", stats['smtp_valid'])
            
            with col3:
                # Get recent sessions
                recent_sessions = db_manager.get_recent_sessions(limit=5)
                
                if recent_sessions.get('scraping'):
                    st.write("**Recent Scraping Sessions**")
                    for session in recent_sessions['scraping'][:3]:
                        st.write(f"• {session.session_name}: {session.emails_found} emails")
                
                if recent_sessions.get('validation'):
                    st.write("**Recent Validation Sessions**")
                    for session in recent_sessions['validation'][:3]:
                        st.write(f"• {session.session_name}: {session.valid_emails}/{session.total_emails} valid")
        
        except Exception as e:
            st.error(f"Error loading database statistics: {str(e)}")
        
        st.divider()
        
        # Search and Browse
        st.subheader("🔍 Search & Browse")
        
        col1, col2 = st.columns(2)
        
        with col1:
            search_term = st.text_input("Search emails by domain or address:", 
                                      placeholder="Enter domain.com or specific email")
            search_limit = st.selectbox("Results limit:", [50, 100, 500, 1000], index=1)
            
            if st.button("Search Emails") and search_term:
                try:
                    search_results = db_manager.search_emails(search_term, limit=search_limit)
                    
                    if search_results:
                        st.success(f"Found {len(search_results)} results")
                        
                        # Convert to DataFrame for display
                        search_df = pd.DataFrame([{
                            'Email': result.email,
                            'Valid': '✅' if result.is_valid else '❌',
                            'Format': '✅' if result.format_valid else '❌',
                            'DNS': '✅' if result.dns_valid else '❌',
                            'SMTP': '✅' if result.smtp_valid else ('❌' if result.smtp_valid is False else '⚠️'),
                            'Date': result.created_at.strftime('%Y-%m-%d %H:%M')
                        } for result in search_results])
                        
                        st.dataframe(search_df, use_container_width=True)
                        
                        # Option to load into session
                        if st.button("Load Results into Session"):
                            loaded_results = []
                            for result in search_results:
                                loaded_results.append({
                                    'email': result.email,
                                    'is_valid': result.is_valid,
                                    'format_valid': result.format_valid,
                                    'blacklist_check': result.blacklist_check,
                                    'dns_valid': result.dns_valid,
                                    'smtp_valid': result.smtp_valid,
                                    'error_message': result.error_message,
                                    'validation_details': result.validation_details or {}
                                })
                            
                            st.session_state.validated_emails = loaded_results
                            st.session_state.scraped_emails = [r['email'] for r in loaded_results]
                            st.success("Results loaded into current session!")
                            st.rerun()
                    else:
                        st.info("No results found")
                        
                except Exception as e:
                    st.error(f"Search error: {str(e)}")
        
        with col2:
            st.write("**Filter Options**")
            filter_valid = st.selectbox("Validation Status:", ["All", "Valid only", "Invalid only"])
            filter_days = st.selectbox("Time Range:", ["All time", "Last 7 days", "Last 30 days", "Last 90 days"])
            
            if st.button("Apply Filters"):
                try:
                    # Calculate date filter
                    date_filter = None
                    if filter_days != "All time":
                        days_map = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
                        days = days_map[filter_days]
                        date_filter = datetime.now() - timedelta(days=days)
                    
                    # Apply validation filter
                    valid_only = None
                    if filter_valid == "Valid only":
                        valid_only = True
                    elif filter_valid == "Invalid only":
                        valid_only = False
                    
                    # Get filtered results
                    filtered_results = db_manager.get_validation_results(limit=500, valid_only=valid_only)
                    
                    # Apply date filter if needed
                    if date_filter:
                        filtered_results = [r for r in filtered_results if r.created_at >= date_filter]
                    
                    if filtered_results:
                        st.success(f"Found {len(filtered_results)} filtered results")
                        
                        # Display summary
                        valid_count = len([r for r in filtered_results if r.is_valid])
                        st.write(f"Valid: {valid_count}/{len(filtered_results)} ({valid_count/len(filtered_results)*100:.1f}%)")
                        
                        # Option to load into session
                        if st.button("Load Filtered Results", key="load_filtered"):
                            loaded_results = []
                            for result in filtered_results:
                                loaded_results.append({
                                    'email': result.email,
                                    'is_valid': result.is_valid,
                                    'format_valid': result.format_valid,
                                    'blacklist_check': result.blacklist_check,
                                    'dns_valid': result.dns_valid,
                                    'smtp_valid': result.smtp_valid,
                                    'error_message': result.error_message,
                                    'validation_details': result.validation_details or {}
                                })
                            
                            st.session_state.validated_emails = loaded_results
                            st.session_state.scraped_emails = [r['email'] for r in loaded_results]
                            st.success("Filtered results loaded into current session!")
                            st.rerun()
                    else:
                        st.info("No results match the selected filters")
                        
                except Exception as e:
                    st.error(f"Filter error: {str(e)}")
        
        st.divider()
        
        # Database Maintenance
        st.subheader("🔧 Database Maintenance")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**Data Cleanup**")
            cleanup_days = st.number_input("Delete data older than (days):", min_value=1, max_value=365, value=30)
            
            if st.button("🗑️ Cleanup Old Data", type="secondary"):
                if st.button("Confirm Cleanup", key="confirm_cleanup"):
                    try:
                        result = db_manager.cleanup_old_data(days=cleanup_days)
                        st.success(f"Cleanup completed:")
                        st.write(f"- Validation results: {result['validation_results_deleted']}")
                        st.write(f"- Scraping sessions: {result['scraping_sessions_deleted']}")
                        st.write(f"- Validation sessions: {result['validation_sessions_deleted']}")
                    except Exception as e:
                        st.error(f"Cleanup error: {str(e)}")
        
        with col2:
            st.write("**Export Database**")
            if st.button("📥 Export All Data"):
                try:
                    all_results = db_manager.get_validation_results(limit=None)
                    if all_results:
                        # Convert to export format
                        export_data = []
                        for result in all_results:
                            export_data.append({
                                'email': result.email,
                                'is_valid': result.is_valid,
                                'format_valid': result.format_valid,
                                'blacklist_check': result.blacklist_check,
                                'dns_valid': result.dns_valid,
                                'smtp_valid': result.smtp_valid,
                                'error_message': result.error_message,
                                'validation_mode': result.validation_mode,
                                'created_at': result.created_at.isoformat()
                            })
                        
                        # Create CSV
                        export_df = pd.DataFrame(export_data)
                        csv_data = export_df.to_csv(index=False)
                        
                        st.download_button(
                            label="Download Database Export",
                            data=csv_data,
                            file_name=f"database_export_{int(time.time())}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("No data to export")
                except Exception as e:
                    st.error(f"Export error: {str(e)}")
        
        with col3:
            st.write("**Database Info**")
            try:
                # Check database connection
                test_session = db_manager.get_session()
                test_session.close()
                st.success("✅ Database connected")
                
                # Show database URL (masked)
                db_url = os.getenv('DATABASE_URL', '')
                if db_url:
                    masked_url = db_url[:20] + "..." + db_url[-10:] if len(db_url) > 30 else db_url
                    st.write(f"URL: {masked_url}")
                
            except Exception as e:
                st.error(f"Database connection issue: {str(e)}")

if __name__ == "__main__":
    main()
