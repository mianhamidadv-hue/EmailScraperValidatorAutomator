import streamlit as st
import pandas as pd
import re
import time
from email_scraper import EmailScraper
from email_validator import EmailValidator
from utils import export_to_csv, rate_limiter
import os

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
    tab1, tab2, tab3 = st.tabs(["🕷️ Email Scraping", "✅ Email Validation", "📊 Results & Export"])
    
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
    
    # Email Validation Tab
    with tab2:
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
            st.write(f"**{len(st.session_state.scraped_emails)} emails ready for validation**")
            
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
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 Validate All Emails", disabled=st.session_state.validation_in_progress):
                    st.session_state.validation_in_progress = True
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        validator = EmailValidator(
                            enable_smtp=enable_smtp_check,
                            timeout=timeout_seconds
                        )
                        
                        validated_results = []
                        total_emails = len(st.session_state.scraped_emails)
                        
                        for i, email in enumerate(st.session_state.scraped_emails):
                            status_text.text(f"Validating: {email}")
                            
                            result = validator.validate_email(email)
                            validated_results.append(result)
                            
                            progress_bar.progress((i + 1) / total_emails)
                            
                            # Rate limiting
                            if i < total_emails - 1:
                                time.sleep(delay_between_requests)
                        
                        st.session_state.validated_emails = validated_results
                        st.success("✅ Email validation completed!")
                        
                    except Exception as e:
                        st.error(f"Validation error: {str(e)}")
                    
                    finally:
                        st.session_state.validation_in_progress = False
                        progress_bar.empty()
                        status_text.empty()
                        st.rerun()
            
            with col2:
                if st.session_state.validated_emails:
                    valid_count = len([r for r in st.session_state.validated_emails if r['is_valid']])
                    st.metric("Valid Emails", f"{valid_count}/{len(st.session_state.validated_emails)}")
    
    # Results & Export Tab
    with tab3:
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
                filtered_df = filtered_df[filtered_df['Email'].str.contains(f"@{domain_filter}")]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Export options
            st.subheader("Export Options")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📥 Export All Results"):
                    csv_data = export_to_csv(st.session_state.validated_emails)
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"email_validation_results_{int(time.time())}.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if st.button("📥 Export Valid Only"):
                    valid_results = [r for r in st.session_state.validated_emails if r['is_valid']]
                    if valid_results:
                        csv_data = export_to_csv(valid_results)
                        st.download_button(
                            label="Download Valid Emails CSV",
                            data=csv_data,
                            file_name=f"valid_emails_{int(time.time())}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("No valid emails to export.")
            
            with col3:
                if st.button("🔄 Clear Results"):
                    st.session_state.scraped_emails = []
                    st.session_state.validated_emails = []
                    st.success("Results cleared!")
                    st.rerun()
        
        else:
            st.info("No validation results available. Please validate some emails first.")

if __name__ == "__main__":
    main()
