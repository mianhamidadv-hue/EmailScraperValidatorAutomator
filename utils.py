import csv
import io
import time
from typing import List, Dict, Any

def export_to_csv(validation_results: List[Dict[str, Any]]) -> str:
    """
    Convert validation results to CSV format.
    
    Args:
        validation_results: List of validation result dictionaries
        
    Returns:
        CSV data as string
    """
    if not validation_results:
        return ""
    
    # Create CSV in memory
    output = io.StringIO()
    
    # Define CSV columns
    fieldnames = [
        'email',
        'is_valid',
        'format_valid',
        'blacklist_check',
        'dns_valid',
        'smtp_valid',
        'error_message'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for result in validation_results:
        # Create a clean row with only the fields we want
        row = {field: result.get(field, '') for field in fieldnames}
        writer.writerow(row)
    
    csv_data = output.getvalue()
    output.close()
    
    return csv_data

def rate_limiter(delay: float):
    """
    Simple rate limiting decorator.
    
    Args:
        delay: Delay in seconds between function calls
    """
    def decorator(func):
        last_called = [0.0]
        
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < delay:
                time.sleep(delay - elapsed)
            
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        
        return wrapper
    return decorator

def format_validation_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a summary of validation results.
    
    Args:
        results: List of validation result dictionaries
        
    Returns:
        Summary statistics dictionary
    """
    if not results:
        return {}
    
    total = len(results)
    valid = len([r for r in results if r.get('is_valid', False)])
    format_valid = len([r for r in results if r.get('format_valid', False)])
    dns_valid = len([r for r in results if r.get('dns_valid', False)])
    smtp_valid = len([r for r in results if r.get('smtp_valid') is True])
    
    # Count error types
    error_types = {}
    for result in results:
        if not result.get('is_valid', False) and result.get('error_message'):
            error_msg = result['error_message']
            error_types[error_msg] = error_types.get(error_msg, 0) + 1
    
    # Domain statistics
    domains = {}
    for result in results:
        email = result.get('email', '')
        if '@' in email:
            domain = email.split('@')[1]
            domains[domain] = domains.get(domain, 0) + 1
    
    summary = {
        'total_emails': total,
        'valid_emails': valid,
        'valid_percentage': (valid / total) * 100 if total > 0 else 0,
        'format_valid': format_valid,
        'dns_valid': dns_valid,
        'smtp_valid': smtp_valid,
        'error_types': error_types,
        'top_domains': sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10],
        'unique_domains': len(domains)
    }
    
    return summary

def clean_email_list(emails: List[str]) -> List[str]:
    """
    Clean and deduplicate a list of email addresses.
    
    Args:
        emails: List of email addresses
        
    Returns:
        Cleaned list of unique email addresses
    """
    cleaned = []
    seen = set()
    
    for email in emails:
        if not email:
            continue
            
        # Clean the email
        email = email.strip().lower()
        
        # Skip if already seen
        if email in seen:
            continue
            
        # Basic validation to filter out obvious non-emails
        if '@' in email and '.' in email.split('@')[1]:
            cleaned.append(email)
            seen.add(email)
    
    return cleaned

def get_domain_from_email(email: str) -> str:
    """
    Extract domain from email address.
    
    Args:
        email: Email address
        
    Returns:
        Domain part of the email
    """
    if '@' not in email:
        return ''
    
    return email.split('@')[1].lower()

def group_emails_by_domain(emails: List[str]) -> Dict[str, List[str]]:
    """
    Group emails by their domain.
    
    Args:
        emails: List of email addresses
        
    Returns:
        Dictionary mapping domains to lists of emails
    """
    grouped = {}
    
    for email in emails:
        domain = get_domain_from_email(email)
        if domain:
            if domain not in grouped:
                grouped[domain] = []
            grouped[domain].append(email)
    
    return grouped

def validate_url(url: str) -> str:
    """
    Validate and normalize a URL.
    
    Args:
        url: URL to validate
        
    Returns:
        Normalized URL or empty string if invalid
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        return ""
    
    # Remove trailing slash
    if url.endswith('/'):
        url = url[:-1]
    
    return url

def estimate_processing_time(num_emails: int, enable_smtp: bool = True) -> str:
    """
    Estimate processing time for email validation.
    
    Args:
        num_emails: Number of emails to validate
        enable_smtp: Whether SMTP validation is enabled
        
    Returns:
        Estimated time as a formatted string
    """
    if num_emails == 0:
        return "0 seconds"
    
    # Base time per email (format + blacklist + DNS)
    base_time_per_email = 0.5
    
    # Additional time for SMTP validation
    smtp_time_per_email = 2.0 if enable_smtp else 0
    
    # Rate limiting delay
    rate_limit_time = num_emails * 0.5
    
    total_seconds = (num_emails * (base_time_per_email + smtp_time_per_email)) + rate_limit_time
    
    if total_seconds < 60:
        return f"{int(total_seconds)} seconds"
    elif total_seconds < 3600:
        minutes = int(total_seconds / 60)
        return f"{minutes} minutes"
    else:
        hours = int(total_seconds / 3600)
        minutes = int((total_seconds % 3600) / 60)
        return f"{hours} hours {minutes} minutes"
