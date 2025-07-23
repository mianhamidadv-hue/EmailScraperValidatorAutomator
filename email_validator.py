import re
import smtplib
import dns.resolver
import socket
import requests
from typing import Dict, List
import time

class EmailValidator:
    def __init__(self, enable_smtp: bool = True, timeout: int = 10):
        """
        Initialize the email validator.
        
        Args:
            enable_smtp: Whether to perform SMTP verification
            timeout: Timeout for network operations in seconds
        """
        self.enable_smtp = enable_smtp
        self.timeout = timeout
        
        # RFC 5322 compliant email regex
        self.email_regex = re.compile(
            r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        )
        
        # Known disposable email domains (blacklist)
        self.disposable_domains = {
            '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
            'temp-mail.org', 'throwaway.email', 'getnada.com',
            'maildrop.cc', 'tempmail.email', 'yopmail.com',
            'dispostable.com', 'fakeinbox.com', 'spambox.us'
        }
        
        # Common invalid/test domains
        self.invalid_domains = {
            'example.com', 'test.com', 'domain.com', 'yoursite.com',
            'yourdomain.com', 'email.com', 'localhost'
        }
    
    def validate_format(self, email: str) -> bool:
        """
        Validate email format according to RFC 5322.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if format is valid
        """
        if not email or len(email) > 254:  # RFC 5321 limit
            return False
        
        # Check basic regex pattern
        if not self.email_regex.match(email):
            return False
        
        # Additional checks
        local, domain = email.rsplit('@', 1)
        
        # Local part checks
        if len(local) > 64:  # RFC 5321 limit
            return False
        
        if local.startswith('.') or local.endswith('.'):
            return False
        
        if '..' in local:
            return False
        
        # Domain part checks
        if len(domain) > 253:
            return False
        
        if domain.startswith('.') or domain.endswith('.'):
            return False
        
        if '..' in domain:
            return False
        
        return True
    
    def check_blacklist(self, email: str) -> Dict[str, bool]:
        """
        Check if email domain is on blacklists.
        
        Args:
            email: Email address to check
            
        Returns:
            dict: Results of blacklist checks
        """
        domain = email.split('@')[1].lower()
        
        result = {
            'is_blacklisted': False,
            'is_disposable': False,
            'is_invalid_domain': False
        }
        
        # Check disposable email providers
        if domain in self.disposable_domains:
            result['is_disposable'] = True
            result['is_blacklisted'] = True
        
        # Check invalid/test domains
        if domain in self.invalid_domains:
            result['is_invalid_domain'] = True
            result['is_blacklisted'] = True
        
        # Additional blacklist checks could be added here
        # For example, checking against external blacklist APIs
        
        return result
    
    def validate_dns(self, email: str) -> Dict[str, any]:
        """
        Validate domain DNS records.
        
        Args:
            email: Email address to validate
            
        Returns:
            dict: DNS validation results
        """
        domain = email.split('@')[1]
        
        result = {
            'has_mx': False,
            'has_a': False,
            'mx_records': [],
            'error': None
        }
        
        try:
            # Check for MX records
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                result['has_mx'] = True
                result['mx_records'] = [str(mx) for mx in mx_records]
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                result['has_mx'] = False
            
            # If no MX records, check for A records (fallback)
            if not result['has_mx']:
                try:
                    a_records = dns.resolver.resolve(domain, 'A')
                    result['has_a'] = True
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    result['has_a'] = False
                    
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def validate_smtp(self, email: str) -> Dict[str, any]:
        """
        Validate email existence via SMTP.
        
        Args:
            email: Email address to validate
            
        Returns:
            dict: SMTP validation results
        """
        if not self.enable_smtp:
            return {'smtp_valid': None, 'error': 'SMTP validation disabled'}
        
        domain = email.split('@')[1]
        
        result = {
            'smtp_valid': False,
            'smtp_response': None,
            'error': None
        }
        
        try:
            # Get MX records
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_record = str(mx_records[0].exchange).rstrip('.')
            
            # Connect to SMTP server
            with smtplib.SMTP(timeout=self.timeout) as server:
                server.connect(mx_record, 25)
                
                # HELO command
                code, response = server.helo('example.com')
                if code != 250:
                    result['error'] = f'HELO failed: {response}'
                    return result
                
                # MAIL FROM command
                code, response = server.mail('test@example.com')
                if code != 250:
                    result['error'] = f'MAIL FROM failed: {response}'
                    return result
                
                # RCPT TO command
                code, response = server.rcpt(email)
                result['smtp_response'] = response.decode() if isinstance(response, bytes) else str(response)
                
                if code == 250:
                    result['smtp_valid'] = True
                elif code == 550:
                    result['smtp_valid'] = False
                else:
                    result['smtp_valid'] = None
                    result['error'] = f'Uncertain response: {code} {response}'
                
        except dns.resolver.NXDOMAIN:
            result['error'] = 'No MX records found'
        except dns.resolver.NoAnswer:
            result['error'] = 'No MX records in DNS response'
        except socket.timeout:
            result['error'] = 'SMTP connection timeout'
        except socket.gaierror as e:
            result['error'] = f'DNS resolution error: {str(e)}'
        except smtplib.SMTPConnectError as e:
            result['error'] = f'SMTP connection error: {str(e)}'
        except smtplib.SMTPServerDisconnected:
            result['error'] = 'SMTP server disconnected'
        except Exception as e:
            result['error'] = f'SMTP validation error: {str(e)}'
        
        return result
    
    def validate_email(self, email: str) -> Dict[str, any]:
        """
        Perform complete 4-stage email validation.
        
        Args:
            email: Email address to validate
            
        Returns:
            dict: Complete validation results
        """
        email = email.strip().lower()
        
        result = {
            'email': email,
            'is_valid': False,
            'format_valid': False,
            'blacklist_check': False,
            'dns_valid': False,
            'smtp_valid': None,
            'error_message': None,
            'validation_details': {}
        }
        
        try:
            # Stage 1: Format validation
            result['format_valid'] = self.validate_format(email)
            if not result['format_valid']:
                result['error_message'] = 'Invalid email format'
                return result
            
            # Stage 2: Blacklist check
            blacklist_result = self.check_blacklist(email)
            result['blacklist_check'] = not blacklist_result['is_blacklisted']
            result['validation_details']['blacklist'] = blacklist_result
            
            if blacklist_result['is_blacklisted']:
                if blacklist_result['is_disposable']:
                    result['error_message'] = 'Disposable email address'
                elif blacklist_result['is_invalid_domain']:
                    result['error_message'] = 'Invalid/test domain'
                else:
                    result['error_message'] = 'Domain is blacklisted'
                return result
            
            # Stage 3: DNS validation
            dns_result = self.validate_dns(email)
            result['dns_valid'] = dns_result['has_mx'] or dns_result['has_a']
            result['validation_details']['dns'] = dns_result
            
            if not result['dns_valid']:
                result['error_message'] = dns_result.get('error', 'No valid DNS records found')
                return result
            
            # Stage 4: SMTP validation (if enabled)
            if self.enable_smtp:
                smtp_result = self.validate_smtp(email)
                result['smtp_valid'] = smtp_result['smtp_valid']
                result['validation_details']['smtp'] = smtp_result
                
                if smtp_result['smtp_valid'] is False:
                    result['error_message'] = 'Email address does not exist on server'
                    return result
                elif smtp_result['error']:
                    result['error_message'] = f"SMTP check failed: {smtp_result['error']}"
                    # Don't return here - treat SMTP errors as inconclusive
            
            # Email is valid if it passes all available checks
            result['is_valid'] = (
                result['format_valid'] and 
                result['blacklist_check'] and 
                result['dns_valid'] and
                (result['smtp_valid'] is not False)  # None (inconclusive) is acceptable
            )
            
        except Exception as e:
            result['error_message'] = f'Validation error: {str(e)}'
        
        return result
    
    def validate_bulk(self, emails: List[str]) -> List[Dict[str, any]]:
        """
        Validate multiple emails with rate limiting.
        
        Args:
            emails: List of email addresses to validate
            
        Returns:
            List of validation results
        """
        results = []
        
        for i, email in enumerate(emails):
            result = self.validate_email(email)
            results.append(result)
            
            # Rate limiting - small delay between validations
            if i < len(emails) - 1:
                time.sleep(0.5)
        
        return results
