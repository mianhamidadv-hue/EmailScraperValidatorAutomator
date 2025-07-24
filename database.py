import os
import sqlalchemy as sa
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', '')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class EmailAddress(Base):
    __tablename__ = "email_addresses"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(254), unique=True, index=True, nullable=False)
    domain = Column(String(253), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ValidationResult(Base):
    __tablename__ = "validation_results"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, sa.ForeignKey("email_addresses.id"), nullable=False, index=True)
    email = Column(String(254), index=True, nullable=False)  # Denormalized for quick access
    is_valid = Column(Boolean, default=False)
    format_valid = Column(Boolean, default=False)
    blacklist_check = Column(Boolean, default=False)
    dns_valid = Column(Boolean, default=False)
    smtp_valid = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)
    validation_details = Column(JSON, nullable=True)
    validation_mode = Column(String(50), default="complete")  # complete, quick, format_only
    created_at = Column(DateTime, default=datetime.utcnow)

class ScrapingSession(Base):
    __tablename__ = "scraping_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_name = Column(String(200), nullable=True)
    urls_scraped = Column(JSON, nullable=True)  # List of URLs processed
    scraping_options = Column(JSON, nullable=True)  # Scraping configuration
    emails_found = Column(Integer, default=0)
    unique_domains = Column(Integer, default=0)
    status = Column(String(50), default="in_progress")  # in_progress, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class ValidationSession(Base):
    __tablename__ = "validation_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_name = Column(String(200), nullable=True)
    total_emails = Column(Integer, default=0)
    processed_emails = Column(Integer, default=0)
    valid_emails = Column(Integer, default=0)
    validation_mode = Column(String(50), default="complete")
    batch_size = Column(Integer, default=100)
    status = Column(String(50), default="in_progress")  # in_progress, completed, paused, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

# Database operations class
class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
        
    def create_tables(self):
        """Create all database tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logging.info("Database tables created successfully")
        except Exception as e:
            logging.error(f"Error creating database tables: {str(e)}")
            raise
    
    def get_session(self) -> Session:
        """Get a database session"""
        return self.SessionLocal()
    
    # Email Address operations
    def add_email(self, email: str) -> EmailAddress:
        """Add an email address to database"""
        session = self.get_session()
        try:
            # Check if email already exists
            existing_email = session.query(EmailAddress).filter(
                EmailAddress.email == email.lower()
            ).first()
            
            if existing_email:
                return existing_email
            
            # Extract domain
            domain = email.split('@')[1] if '@' in email else None
            
            # Create new email record
            email_record = EmailAddress(
                email=email.lower(),
                domain=domain.lower() if domain else None
            )
            
            session.add(email_record)
            session.commit()
            session.refresh(email_record)
            return email_record
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error adding email {email}: {str(e)}")
            raise
        finally:
            session.close()
    
    def bulk_add_emails(self, emails: List[str]) -> List[EmailAddress]:
        """Add multiple emails to database efficiently"""
        session = self.get_session()
        try:
            email_records = []
            emails_to_add = []
            
            # Check which emails already exist
            existing_emails = session.query(EmailAddress.email).filter(
                EmailAddress.email.in_([email.lower() for email in emails])
            ).all()
            existing_set = {email[0] for email in existing_emails}
            
            # Prepare new emails for bulk insert
            for email in emails:
                email_lower = email.lower()
                if email_lower not in existing_set:
                    domain = email.split('@')[1] if '@' in email else None
                    emails_to_add.append({
                        'email': email_lower,
                        'domain': domain.lower() if domain else None,
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    })
            
            # Bulk insert new emails
            if emails_to_add:
                session.execute(sa.insert(EmailAddress), emails_to_add)
                session.commit()
            
            # Get all email records
            all_emails = session.query(EmailAddress).filter(
                EmailAddress.email.in_([email.lower() for email in emails])
            ).all()
            
            return all_emails
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error bulk adding emails: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_emails_by_domain(self, domain: str) -> List[EmailAddress]:
        """Get all emails for a specific domain"""
        session = self.get_session()
        try:
            return session.query(EmailAddress).filter(
                EmailAddress.domain == domain.lower()
            ).all()
        finally:
            session.close()
    
    # Validation Result operations
    def save_validation_result(self, result: Dict[str, Any]) -> ValidationResult:
        """Save validation result to database"""
        session = self.get_session()
        try:
            # Get or create email record
            email_record = self.add_email(result['email'])
            
            # Check if validation result already exists
            existing_result = session.query(ValidationResult).filter(
                ValidationResult.email_id == email_record.id
            ).first()
            
            if existing_result:
                # Update existing result
                existing_result.is_valid = result.get('is_valid', False)
                existing_result.format_valid = result.get('format_valid', False)
                existing_result.blacklist_check = result.get('blacklist_check', False)
                existing_result.dns_valid = result.get('dns_valid', False)
                existing_result.smtp_valid = result.get('smtp_valid')
                existing_result.error_message = result.get('error_message')
                existing_result.validation_details = result.get('validation_details')
                existing_result.validation_mode = result.get('validation_mode', 'complete')
                validation_result = existing_result
            else:
                # Create new validation result
                validation_result = ValidationResult(
                    email_id=email_record.id,
                    email=result['email'],
                    is_valid=result.get('is_valid', False),
                    format_valid=result.get('format_valid', False),
                    blacklist_check=result.get('blacklist_check', False),
                    dns_valid=result.get('dns_valid', False),
                    smtp_valid=result.get('smtp_valid'),
                    error_message=result.get('error_message'),
                    validation_details=result.get('validation_details'),
                    validation_mode=result.get('validation_mode', 'complete')
                )
                session.add(validation_result)
            
            session.commit()
            session.refresh(validation_result)
            return validation_result
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error saving validation result: {str(e)}")
            raise
        finally:
            session.close()
    
    def bulk_save_validation_results(self, results: List[Dict[str, Any]]) -> int:
        """Save multiple validation results efficiently"""
        session = self.get_session()
        try:
            # First, ensure all emails exist
            emails = [result['email'] for result in results]
            email_records = self.bulk_add_emails(emails)
            email_id_map = {record.email: record.id for record in email_records}
            
            # Prepare validation results for bulk insert
            validation_data = []
            for result in results:
                email_id = email_id_map.get(result['email'].lower())
                if email_id:
                    validation_data.append({
                        'email_id': email_id,
                        'email': result['email'],
                        'is_valid': result.get('is_valid', False),
                        'format_valid': result.get('format_valid', False),
                        'blacklist_check': result.get('blacklist_check', False),
                        'dns_valid': result.get('dns_valid', False),
                        'smtp_valid': result.get('smtp_valid'),
                        'error_message': result.get('error_message'),
                        'validation_details': result.get('validation_details'),
                        'validation_mode': result.get('validation_mode', 'complete'),
                        'created_at': datetime.utcnow()
                    })
            
            # Delete existing validation results for these emails
            email_ids = [email_id_map[result['email'].lower()] for result in results 
                        if result['email'].lower() in email_id_map]
            if email_ids:
                session.query(ValidationResult).filter(
                    ValidationResult.email_id.in_(email_ids)
                ).delete(synchronize_session=False)
            
            # Bulk insert new validation results
            if validation_data:
                session.execute(sa.insert(ValidationResult), validation_data)
                session.commit()
                return len(validation_data)
            
            return 0
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error bulk saving validation results: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_validation_results(self, limit: int = None, valid_only: bool = None) -> List[ValidationResult]:
        """Get validation results with optional filters"""
        session = self.get_session()
        try:
            query = session.query(ValidationResult).order_by(ValidationResult.created_at.desc())
            
            if valid_only is not None:
                query = query.filter(ValidationResult.is_valid == valid_only)
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        finally:
            session.close()
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        session = self.get_session()
        try:
            total = session.query(ValidationResult).count()
            valid = session.query(ValidationResult).filter(ValidationResult.is_valid == True).count()
            format_valid = session.query(ValidationResult).filter(ValidationResult.format_valid == True).count()
            dns_valid = session.query(ValidationResult).filter(ValidationResult.dns_valid == True).count()
            smtp_valid = session.query(ValidationResult).filter(ValidationResult.smtp_valid == True).count()
            
            return {
                'total_emails': total,
                'valid_emails': valid,
                'valid_percentage': (valid / total * 100) if total > 0 else 0,
                'format_valid': format_valid,
                'dns_valid': dns_valid,
                'smtp_valid': smtp_valid
            }
        finally:
            session.close()
    
    # Session management operations
    def create_scraping_session(self, session_name: str = None, urls: List[str] = None, 
                               options: Dict[str, Any] = None) -> ScrapingSession:
        """Create a new scraping session"""
        session = self.get_session()
        try:
            scraping_session = ScrapingSession(
                session_name=session_name or f"Scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                urls_scraped=urls or [],
                scraping_options=options or {},
                status="in_progress"
            )
            
            session.add(scraping_session)
            session.commit()
            session.refresh(scraping_session)
            return scraping_session
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error creating scraping session: {str(e)}")
            raise
        finally:
            session.close()
    
    def update_scraping_session(self, session_id: int, emails_found: int = None, 
                               unique_domains: int = None, status: str = None, 
                               error_message: str = None) -> ScrapingSession:
        """Update scraping session"""
        session = self.get_session()
        try:
            scraping_session = session.query(ScrapingSession).filter(
                ScrapingSession.id == session_id
            ).first()
            
            if not scraping_session:
                raise ValueError(f"Scraping session {session_id} not found")
            
            if emails_found is not None:
                scraping_session.emails_found = emails_found
            if unique_domains is not None:
                scraping_session.unique_domains = unique_domains  
            if status is not None:
                scraping_session.status = status
                if status == "completed":
                    scraping_session.completed_at = datetime.utcnow()
            if error_message is not None:
                scraping_session.error_message = error_message
            
            session.commit()
            session.refresh(scraping_session)
            return scraping_session
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error updating scraping session: {str(e)}")
            raise
        finally:
            session.close()
    
    def create_validation_session(self, session_name: str = None, total_emails: int = 0,
                                 validation_mode: str = "complete", batch_size: int = 100) -> ValidationSession:
        """Create a new validation session"""
        session = self.get_session()
        try:
            validation_session = ValidationSession(
                session_name=session_name or f"Validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                total_emails=total_emails,
                validation_mode=validation_mode,
                batch_size=batch_size,
                status="in_progress"
            )
            
            session.add(validation_session)
            session.commit()
            session.refresh(validation_session)
            return validation_session
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error creating validation session: {str(e)}")
            raise
        finally:
            session.close()
    
    def update_validation_session(self, session_id: int, processed_emails: int = None,
                                 valid_emails: int = None, status: str = None,
                                 error_message: str = None) -> ValidationSession:
        """Update validation session"""
        session = self.get_session()
        try:
            validation_session = session.query(ValidationSession).filter(
                ValidationSession.id == session_id
            ).first()
            
            if not validation_session:
                raise ValueError(f"Validation session {session_id} not found")
            
            if processed_emails is not None:
                validation_session.processed_emails = processed_emails
            if valid_emails is not None:
                validation_session.valid_emails = valid_emails
            if status is not None:
                validation_session.status = status
                if status == "completed":
                    validation_session.completed_at = datetime.utcnow()
            if error_message is not None:
                validation_session.error_message = error_message
            
            session.commit()
            session.refresh(validation_session)
            return validation_session
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error updating validation session: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_recent_sessions(self, session_type: str = "both", limit: int = 10):
        """Get recent scraping and/or validation sessions"""
        session = self.get_session()
        try:
            results = {}
            
            if session_type in ["scraping", "both"]:
                scraping_sessions = session.query(ScrapingSession).order_by(
                    ScrapingSession.created_at.desc()
                ).limit(limit).all()
                results['scraping'] = scraping_sessions
            
            if session_type in ["validation", "both"]:
                validation_sessions = session.query(ValidationSession).order_by(
                    ValidationSession.created_at.desc()
                ).limit(limit).all()
                results['validation'] = validation_sessions
            
            return results
        finally:
            session.close()
    
    def search_emails(self, query: str, limit: int = 100) -> List[ValidationResult]:
        """Search emails by email address or domain"""
        session = self.get_session()
        try:
            search_pattern = f"%{query.lower()}%"
            results = session.query(ValidationResult).filter(
                ValidationResult.email.like(search_pattern)
            ).order_by(ValidationResult.created_at.desc()).limit(limit).all()
            
            return results
        finally:
            session.close()
    
    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """Clean up old data older than specified days"""
        session = self.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old validation results
            validation_deleted = session.query(ValidationResult).filter(
                ValidationResult.created_at < cutoff_date
            ).delete()
            
            # Delete old sessions
            scraping_deleted = session.query(ScrapingSession).filter(
                ScrapingSession.created_at < cutoff_date
            ).delete()
            
            validation_sessions_deleted = session.query(ValidationSession).filter(
                ValidationSession.created_at < cutoff_date
            ).delete()
            
            session.commit()
            
            return {
                'validation_results_deleted': validation_deleted,
                'scraping_sessions_deleted': scraping_deleted,
                'validation_sessions_deleted': validation_sessions_deleted
            }
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error cleaning up old data: {str(e)}")
            raise
        finally:
            session.close()

# Global database manager instance
db_manager = DatabaseManager()