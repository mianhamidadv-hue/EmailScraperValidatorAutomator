import os
import sys
from typing import List, Dict, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Personalization
import json
import time
import logging

# Reference: python_sendgrid integration
class EmailCampaignManager:
    def __init__(self):
        """Initialize the SendGrid email campaign manager."""
        self.api_key = os.environ.get('SENDGRID_API_KEY')
        if not self.api_key:
            raise ValueError("SENDGRID_API_KEY environment variable must be set")
        
        self.sg = SendGridAPIClient(self.api_key)
        self.logger = logging.getLogger(__name__)
        
    def send_single_email(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        text_content: str = None,
        html_content: str = None
    ) -> Dict:
        """
        Send a single email using SendGrid.
        
        Args:
            to_email: Recipient email address
            from_email: Sender email address
            subject: Email subject
            text_content: Plain text content
            html_content: HTML content
            
        Returns:
            Dict with status and message
        """
        try:
            message = Mail(
                from_email=Email(from_email),
                to_emails=To(to_email),
                subject=subject
            )

            if html_content:
                message.content = Content("text/html", html_content)
            elif text_content:
                message.content = Content("text/plain", text_content)
            else:
                return {"success": False, "error": "No email content provided"}

            response = self.sg.send(message)
            
            return {
                "success": True,
                "status_code": response.status_code,
                "message": "Email sent successfully",
                "to": to_email
            }
            
        except Exception as e:
            self.logger.error(f"SendGrid error sending to {to_email}: {e}")
            return {
                "success": False,
                "error": str(e),
                "to": to_email
            }
    
    def send_bulk_campaign(
        self,
        recipients: List[str],
        from_email: str,
        subject: str,
        text_content: str = None,
        html_content: str = None,
        delay_seconds: int = 1
    ) -> Dict:
        """
        Send a bulk email campaign to multiple recipients.
        
        Args:
            recipients: List of recipient email addresses
            from_email: Sender email address
            subject: Email subject
            text_content: Plain text content
            html_content: HTML content
            delay_seconds: Delay between emails to respect rate limits
            
        Returns:
            Dict with campaign results
        """
        results = {
            "total_sent": 0,
            "total_failed": 0,
            "successful_sends": [],
            "failed_sends": [],
            "campaign_id": f"campaign_{int(time.time())}"
        }
        
        for i, recipient in enumerate(recipients):
            result = self.send_single_email(
                to_email=recipient,
                from_email=from_email,
                subject=subject,
                text_content=text_content,
                html_content=html_content
            )
            
            if result["success"]:
                results["total_sent"] += 1
                results["successful_sends"].append(recipient)
            else:
                results["total_failed"] += 1
                results["failed_sends"].append({
                    "email": recipient,
                    "error": result.get("error", "Unknown error")
                })
            
            # Rate limiting - don't overwhelm SendGrid
            if i < len(recipients) - 1:
                time.sleep(delay_seconds)
        
        return results
    
    def create_email_template(self, template_name: str, subject: str, html_content: str, text_content: str = None):
        """Create an email template for campaigns."""
        template = {
            "name": template_name,
            "subject": subject,
            "html_content": html_content,
            "text_content": text_content,
            "created_at": time.time()
        }
        return template
    
    def personalize_email_content(self, template: str, recipient_data: Dict[str, str]) -> str:
        """
        Replace placeholders in email template with personalized data.
        
        Args:
            template: Email template with placeholders like {{name}}, {{company}}
            recipient_data: Dict with replacement values
            
        Returns:
            Personalized email content
        """
        personalized = template
        for key, value in recipient_data.items():
            placeholder = f"{{{{{key}}}}}"
            personalized = personalized.replace(placeholder, value)
        
        return personalized

class AutoReplyManager:
    """Manage automatic email replies and follow-ups."""
    
    def __init__(self, campaign_manager: EmailCampaignManager):
        self.campaign_manager = campaign_manager
        self.auto_replies = {}
        self.followup_schedules = {}
    
    def setup_auto_reply(self, campaign_id: str, reply_template: str, delay_hours: int = 24):
        """Set up automatic reply for a campaign."""
        self.auto_replies[campaign_id] = {
            "template": reply_template,
            "delay_hours": delay_hours,
            "created_at": time.time()
        }
    
    def schedule_followup(
        self, 
        original_recipients: List[str],
        from_email: str,
        followup_subject: str,
        followup_content: str,
        days_delay: int = 7
    ):
        """Schedule follow-up emails."""
        followup_id = f"followup_{int(time.time())}"
        
        followup_data = {
            "recipients": original_recipients,
            "from_email": from_email,
            "subject": followup_subject,
            "content": followup_content,
            "scheduled_for": time.time() + (days_delay * 24 * 3600),
            "status": "scheduled"
        }
        
        self.followup_schedules[followup_id] = followup_data
        return followup_id
    
    def send_scheduled_followups(self):
        """Send any follow-ups that are due."""
        current_time = time.time()
        sent_followups = []
        
        for followup_id, followup_data in self.followup_schedules.items():
            if (followup_data["status"] == "scheduled" and 
                current_time >= followup_data["scheduled_for"]):
                
                # Send the follow-up campaign
                results = self.campaign_manager.send_bulk_campaign(
                    recipients=followup_data["recipients"],
                    from_email=followup_data["from_email"],
                    subject=followup_data["subject"],
                    html_content=followup_data["content"]
                )
                
                followup_data["status"] = "sent"
                followup_data["results"] = results
                sent_followups.append(followup_id)
        
        return sent_followups