import streamlit as st
import pandas as pd
import re
import time
from email_scraper import EmailScraper
from email_validator import EmailValidator
from utils import export_to_csv, rate_limiter
from sendgrid_client import EmailCampaignManager, AutoReplyManager
from email_templates import EmailTemplates
import os
import json

# Page configuration
st.set_page_config(
    page_title="Email Scraper & Validator",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'scraped_emails' not in st.session_state:
    st.session_state.scraped_emails = []
if 'validated_emails' not in st.session_state:
    st.session_state.validated_emails = []
if 'scraping_in_progress' not in st.session_state:
    st.session_state.scraping_in_progress = False
if 'validation_in_progress' not in st.session_state:
    st.session_state.validation_in_progress = False
if 'campaign_history' not in st.session_state:
    st.session_state.campaign_history = []
if 'scheduled_followups' not in st.session_state:
    st.session_state.scheduled_followups = {}
if 'email_templates' not in st.session_state:
    st.session_state.email_templates = EmailTemplates.get_all_templates()

def main():
    st.title("📧 Email Scraper & Validator")
    st.write("Extract and validate email addresses from websites with comprehensive verification.")
    
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
    
    # Main interface tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🕷️ Email Scraping", "📦 Bulk Operations", "✅ Email Validation", "📊 Results & Export", "📬 Email Campaigns"])
    
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
                        index=1,
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
    
    # Email Campaigns Tab
    with tab5:
        st.header("📧 Email Campaign Manager")
        
        # Check if SendGrid API key is configured
        sendgrid_configured = os.environ.get('SENDGRID_API_KEY') is not None
        
        if not sendgrid_configured:
            st.warning("⚠️ SendGrid API Key not configured. Please set up your SendGrid API key to use email campaigns.")
            with st.expander("How to set up SendGrid API Key"):
                st.markdown("""
                1. Sign up for a SendGrid account at https://sendgrid.com
                2. Create an API Key in your SendGrid dashboard
                3. Add the API key to your environment variables as `SENDGRID_API_KEY`
                """)
            
            # Still allow template creation and viewing
            st.subheader("📝 Email Template Manager")
            
            template_action = st.radio(
                "Choose action:",
                ["View Templates", "Create Custom Template"],
                horizontal=True
            )
            
            if template_action == "View Templates":
                template_names = list(st.session_state.email_templates.keys())
                if template_names:
                    selected_template = st.selectbox("Select template to view:", template_names)
                    template = st.session_state.email_templates[selected_template]
                    
                    st.subheader(f"Template: {template['name']}")
                    st.write(f"**Subject:** {template['subject']}")
                    
                    with st.expander("HTML Content"):
                        st.code(template['html_content'], language='html')
                    
                    with st.expander("Text Content"):
                        st.text(template.get('text_content', 'No text content available'))
            
            elif template_action == "Create Custom Template":
                with st.form("custom_template_form"):
                    template_name = st.text_input("Template Name:")
                    template_subject = st.text_input("Subject Line:")
                    template_html = st.text_area("HTML Content:", height=300)
                    template_text = st.text_area("Text Content (optional):", height=150)
                    
                    if st.form_submit_button("Save Template"):
                        if template_name and template_subject and template_html:
                            custom_template = {
                                "name": template_name,
                                "subject": template_subject,
                                "html_content": template_html,
                                "text_content": template_text
                            }
                            st.session_state.email_templates[template_name.lower().replace(' ', '_')] = custom_template
                            st.success(f"Template '{template_name}' saved successfully!")
                        else:
                            st.error("Please fill in all required fields (Name, Subject, HTML Content)")
        
        else:
            # Full campaign functionality when SendGrid is configured
            st.success("✅ SendGrid API configured - Full campaign functionality available")
            
            campaign_tab1, campaign_tab2, campaign_tab3 = st.tabs(["🚀 Create Campaign", "📋 Templates", "📊 Campaign History"])
            
            with campaign_tab1:
                st.subheader("Create Email Campaign")
                
                if not st.session_state.scraped_emails and not st.session_state.validated_emails:
                    st.info("No email recipients available. Please scrape and validate emails first, or upload a recipient list.")
                    
                    # File upload for recipients
                    uploaded_recipients = st.file_uploader(
                        "Upload recipient list (CSV):",
                        type=['csv'],
                        help="CSV file should have an 'email' column"
                    )
                    
                    if uploaded_recipients:
                        try:
                            df_recipients = pd.read_csv(uploaded_recipients)
                            if 'email' in df_recipients.columns:
                                recipient_emails = df_recipients['email'].dropna().tolist()
                                st.success(f"Loaded {len(recipient_emails)} recipients from file!")
                                st.session_state.scraped_emails = recipient_emails
                            else:
                                st.error("CSV file must contain an 'email' column.")
                        except Exception as e:
                            st.error(f"Error reading file: {str(e)}")
                
                if st.session_state.scraped_emails or st.session_state.validated_emails:
                    # Campaign configuration
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Recipient selection
                        recipient_source = st.radio(
                            "Use recipients from:",
                            ["All scraped emails", "Validated emails only", "Custom selection"],
                            horizontal=True
                        )
                        
                        if recipient_source == "All scraped emails":
                            recipients = st.session_state.scraped_emails
                        elif recipient_source == "Validated emails only":
                            if st.session_state.validated_emails:
                                recipients = [r['email'] for r in st.session_state.validated_emails if r['is_valid']]
                            else:
                                recipients = []
                                st.warning("No validated emails available.")
                        else:
                            # Custom selection
                            all_available = list(set(st.session_state.scraped_emails + [r['email'] for r in st.session_state.validated_emails]))
                            recipients = st.multiselect("Select recipients:", all_available)
                        
                        # Campaign details
                        from_email = st.text_input(
                            "From Email:",
                            placeholder="your-email@yourdomain.com",
                            help="Your verified sender email address"
                        )
                        
                        # Template selection
                        template_choice = st.radio(
                            "Choose template source:",
                            ["Pre-built template", "Custom template", "Write from scratch"],
                            horizontal=True
                        )
                        
                        if template_choice == "Pre-built template":
                            template_names = list(st.session_state.email_templates.keys())
                            selected_template_key = st.selectbox("Select template:", template_names)
                            selected_template = st.session_state.email_templates[selected_template_key]
                            
                            campaign_subject = st.text_input("Subject:", value=selected_template['subject'])
                            
                            # Show template preview
                            with st.expander("Template Preview", expanded=False):
                                st.write("**Subject:** " + selected_template['subject'])
                                st.write("**HTML Content:**")
                                st.markdown(selected_template['html_content'][:500] + "..." if len(selected_template['html_content']) > 500 else selected_template['html_content'])
                            
                            campaign_html = selected_template['html_content']
                            campaign_text = selected_template.get('text_content', '')
                            
                        elif template_choice == "Custom template":
                            custom_template_names = [k for k in st.session_state.email_templates.keys() if not k in ['guest_post', 'collaboration', 'press_inquiry', 'follow_up']]
                            if custom_template_names:
                                selected_custom = st.selectbox("Select custom template:", custom_template_names)
                                custom_template = st.session_state.email_templates[selected_custom]
                                campaign_subject = st.text_input("Subject:", value=custom_template['subject'])
                                campaign_html = custom_template['html_content']
                                campaign_text = custom_template.get('text_content', '')
                            else:
                                st.info("No custom templates available. Create one in the Templates tab.")
                                campaign_subject = st.text_input("Subject:")
                                campaign_html = st.text_area("HTML Content:", height=300)
                                campaign_text = st.text_area("Text Content:", height=150)
                        
                        else:
                            # Write from scratch
                            campaign_subject = st.text_input("Subject:")
                            campaign_html = st.text_area("HTML Content:", height=300)
                            campaign_text = st.text_area("Text Content (optional):", height=150)
                    
                    with col2:
                        st.write("**Campaign Summary**")
                        if recipients:
                            st.metric("Recipients", len(recipients))
                            
                            # Estimate sending time
                            est_time_minutes = len(recipients) * 1 / 60  # 1 second per email
                            if est_time_minutes < 1:
                                st.metric("Est. Send Time", f"{len(recipients)} seconds")
                            else:
                                st.metric("Est. Send Time", f"{est_time_minutes:.1f} minutes")
                        
                        # Campaign options
                        st.write("**Campaign Options**")
                        delay_between_emails = st.slider("Delay between emails (seconds):", 1, 10, 2)
                        
                        # Follow-up options
                        setup_followup = st.checkbox("Setup automatic follow-up")
                        if setup_followup:
                            followup_days = st.number_input("Follow-up after (days):", min_value=1, max_value=30, value=7)
                            followup_subject = st.text_input("Follow-up subject:", placeholder="Following up on...")
                    
                    # Campaign launch
                    if st.button("🚀 Launch Campaign", type="primary"):
                        if not from_email:
                            st.error("Please enter a 'From' email address.")
                        elif not campaign_subject:
                            st.error("Please enter a subject line.")
                        elif not campaign_html and not campaign_text:
                            st.error("Please provide email content (HTML or text).")
                        elif not recipients:
                            st.error("Please select recipients for the campaign.")
                        else:
                            try:
                                # Initialize campaign manager
                                campaign_manager = EmailCampaignManager()
                                
                                # Progress tracking
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                                results_container = st.empty()
                                
                                with st.spinner("Launching email campaign..."):
                                    # Send campaign
                                    results = campaign_manager.send_bulk_campaign(
                                        recipients=recipients,
                                        from_email=from_email,
                                        subject=campaign_subject,
                                        html_content=campaign_html if campaign_html else None,
                                        text_content=campaign_text if campaign_text else None,
                                        delay_seconds=delay_between_emails
                                    )
                                
                                # Store campaign results
                                campaign_record = {
                                    "campaign_id": results["campaign_id"],
                                    "timestamp": time.time(),
                                    "subject": campaign_subject,
                                    "from_email": from_email,
                                    "total_recipients": len(recipients),
                                    "total_sent": results["total_sent"],
                                    "total_failed": results["total_failed"],
                                    "successful_sends": results["successful_sends"],
                                    "failed_sends": results["failed_sends"]
                                }
                                
                                st.session_state.campaign_history.append(campaign_record)
                                
                                # Show results
                                st.success(f"Campaign completed! Sent {results['total_sent']} emails successfully.")
                                if results["total_failed"] > 0:
                                    st.warning(f"Failed to send {results['total_failed']} emails.")
                                
                                # Setup follow-up if requested
                                if setup_followup and followup_subject:
                                    auto_reply = AutoReplyManager(campaign_manager)
                                    followup_id = auto_reply.schedule_followup(
                                        original_recipients=results["successful_sends"],
                                        from_email=from_email,
                                        followup_subject=followup_subject,
                                        followup_content=f"<p>Following up on my previous email about {campaign_subject}</p>",
                                        days_delay=followup_days
                                    )
                                    st.session_state.scheduled_followups[followup_id] = auto_reply.followup_schedules[followup_id]
                                    st.info(f"Follow-up scheduled for {followup_days} days from now.")
                                
                                progress_bar.empty()
                                status_text.empty()
                                
                            except Exception as e:
                                st.error(f"Campaign failed: {str(e)}")
            
            with campaign_tab2:
                st.subheader("Email Templates")
                
                template_action = st.radio(
                    "Choose action:",
                    ["View All Templates", "Create New Template", "Edit Template"],
                    horizontal=True
                )
                
                if template_action == "View All Templates":
                    for template_key, template in st.session_state.email_templates.items():
                        with st.expander(f"📧 {template['name']}"):
                            st.write(f"**Subject:** {template['subject']}")
                            st.markdown("**HTML Preview:**")
                            st.code(template['html_content'][:300] + "..." if len(template['html_content']) > 300 else template['html_content'], language='html')
                
                elif template_action == "Create New Template":
                    with st.form("new_template_form"):
                        st.write("Create a new email template:")
                        template_name = st.text_input("Template Name:")
                        template_subject = st.text_input("Subject Line:")
                        template_html = st.text_area("HTML Content:", height=400)
                        template_text = st.text_area("Text Content (optional):", height=200)
                        
                        if st.form_submit_button("Create Template"):
                            if template_name and template_subject and template_html:
                                template_key = template_name.lower().replace(' ', '_')
                                new_template = {
                                    "name": template_name,
                                    "subject": template_subject,
                                    "html_content": template_html,
                                    "text_content": template_text
                                }
                                st.session_state.email_templates[template_key] = new_template
                                st.success(f"Template '{template_name}' created successfully!")
                                st.rerun()
                            else:
                                st.error("Please fill in all required fields.")
            
            with campaign_tab3:
                st.subheader("Campaign History & Analytics")
                
                if st.session_state.campaign_history:
                    for i, campaign in enumerate(reversed(st.session_state.campaign_history)):
                        with st.expander(f"Campaign: {campaign['subject']} - {time.strftime('%Y-%m-%d %H:%M', time.localtime(campaign['timestamp']))}"):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Total Recipients", campaign['total_recipients'])
                                st.metric("Successfully Sent", campaign['total_sent'])
                            
                            with col2:
                                st.metric("Failed Sends", campaign['total_failed'])
                                success_rate = (campaign['total_sent'] / campaign['total_recipients']) * 100 if campaign['total_recipients'] > 0 else 0
                                st.metric("Success Rate", f"{success_rate:.1f}%")
                            
                            with col3:
                                st.write("**Campaign Details:**")
                                st.write(f"From: {campaign['from_email']}")
                                st.write(f"Campaign ID: {campaign['campaign_id']}")
                            
                            if campaign['failed_sends']:
                                with st.expander("Failed Sends Details"):
                                    for failed in campaign['failed_sends']:
                                        st.write(f"❌ {failed['email']}: {failed['error']}")
                
                else:
                    st.info("No campaign history available. Launch your first campaign to see results here.")
                
                # Scheduled follow-ups
                if st.session_state.scheduled_followups:
                    st.subheader("Scheduled Follow-ups")
                    for followup_id, followup_data in st.session_state.scheduled_followups.items():
                        scheduled_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(followup_data['scheduled_for']))
                        status = followup_data['status']
                        
                        st.write(f"**Follow-up:** {followup_data['subject']}")
                        st.write(f"Status: {status.title()} | Scheduled: {scheduled_time}")
                        st.write(f"Recipients: {len(followup_data['recipients'])}")

if __name__ == "__main__":
    main()
