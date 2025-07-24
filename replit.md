# Email Scraper & Validator

## Overview

This is a Python-based web application built with Streamlit that provides comprehensive email scraping and validation capabilities with bulk processing support. The application allows users to extract email addresses from websites, import large email lists (up to 1000 emails), and validate them using a 4-stage verification process including format validation, blacklist checking, DNS verification, and SMTP testing.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application follows a modular architecture with clear separation of concerns:

### Frontend Architecture
- **Streamlit-based UI**: Web interface built with Streamlit providing an interactive dashboard
- **Multi-tab interface**: Organized into five main sections - Email Scraping, Bulk Operations, Email Validation, Results & Export, and Database Management
- **Real-time feedback**: Progress indicators, batch processing updates, and session state management for user interaction
- **Sidebar configuration**: Centralized settings panel for rate limiting, validation options, and database settings
- **Bulk processing interface**: Dedicated tab for handling large-scale operations with progress tracking
- **Database management**: Advanced interface for searching, filtering, and managing stored data

### Backend Architecture
- **Modular Python components**: Separate classes for scraping (`EmailScraper`) and validation (`EmailValidator`)
- **Database layer**: PostgreSQL database with SQLAlchemy ORM for persistent data storage
- **Session management**: Both Streamlit session state and database session tracking
- **Utility functions**: Helper functions for data export, rate limiting, and database operations

## Key Components

### 1. EmailScraper Class
- **Purpose**: Extracts email addresses from web pages
- **Key features**: 
  - BeautifulSoup and Trafilatura for content extraction
  - Regex-based email pattern matching (RFC 5322 compliant)
  - Rate limiting with configurable delays
  - Contact page discovery and crawling
  - False positive filtering

### 2. EmailValidator Class
- **Purpose**: Validates extracted email addresses through multiple verification layers
- **Validation methods**:
  - Format validation (RFC 5322 compliance)
  - Blacklist checking against disposable email providers
  - DNS MX record verification
  - Optional SMTP verification
- **Configurable timeouts** and SMTP checking toggle

### 3. Utility Functions
- **CSV Export**: Converts validation results to downloadable CSV format
- **Rate Limiting**: Decorator for controlling request frequency

### 4. Main Application (app.py)
- **Streamlit interface**: Five-tab UI with configuration sidebar
- **Hybrid storage**: Both session state and database persistence
- **Progress tracking**: Real-time status updates during scraping/validation operations
- **Bulk processing**: Support for processing up to 1000 emails with batch management
- **Advanced export**: Multiple export formats (CSV, Excel, JSON) with filtering options

### 5. Database Layer (database.py)
- **PostgreSQL integration**: Full database schema with tables for emails, validation results, and sessions
- **SQLAlchemy ORM**: Object-relational mapping for type-safe database operations
- **Bulk operations**: Efficient batch processing for large datasets
- **Data integrity**: Foreign key relationships and transaction management
- **Search capabilities**: Advanced search and filtering across all stored data

## Data Flow

1. **User Input**: User provides website URLs, bulk email lists, or uploads files with configuration settings
2. **Bulk Processing**: Support for multiple input methods including text area input, CSV uploads, and URL lists
3. **Email Scraping**: EmailScraper crawls specified websites and extracts email addresses with batch processing for multiple URLs
4. **Data Storage**: Scraped emails stored in Streamlit session state with deduplication
5. **Email Validation**: EmailValidator processes emails through 4-stage validation with batch support and resume capability
6. **Results Analysis**: Advanced analytics including domain analysis, error categorization, and success rate tracking
7. **Bulk Export**: Results can be exported in multiple formats (CSV, Excel, JSON) with filtering and scope options

## External Dependencies

### Core Libraries
- **Streamlit**: Web application framework for the user interface
- **Requests**: HTTP client for web scraping and API calls
- **BeautifulSoup4**: HTML parsing for email extraction
- **Trafilatura**: Advanced web content extraction
- **pandas**: Data manipulation and analysis
- **dnspython**: DNS resolution for MX record validation
- **openpyxl**: Excel file generation for advanced export options
- **SQLAlchemy**: Database ORM and connection management
- **psycopg2-binary**: PostgreSQL database adapter

### Network Services
- **DNS Servers**: For MX record validation
- **SMTP Servers**: For optional email deliverability testing
- **Target Websites**: External websites being scraped for email addresses
- **PostgreSQL Database**: Cloud-hosted database for persistent storage

## Deployment Strategy

### Current Setup
- **Cloud-ready**: Designed to run on Replit with PostgreSQL database integration
- **Hybrid Storage**: Streamlit session state for UI responsiveness plus database for persistence
- **PostgreSQL Database**: Full database schema with relational tables and advanced querying

### Architecture Decisions

1. **Streamlit Choice**: 
   - **Problem**: Need for rapid prototyping of web interface
   - **Solution**: Streamlit for quick UI development
   - **Pros**: Fast development, built-in components, Python-native
   - **Cons**: Limited customization, session-based state only

2. **Modular Class Design**:
   - **Problem**: Separation of scraping and validation logic
   - **Solution**: Separate EmailScraper and EmailValidator classes
   - **Pros**: Maintainable, testable, reusable components
   - **Cons**: Additional complexity for simple operations

3. **Multi-layer Validation**:
   - **Problem**: Need for comprehensive email verification
   - **Solution**: Progressive validation (format → DNS → SMTP)
   - **Pros**: High accuracy, configurable depth
   - **Cons**: Slower processing, potential for false negatives

4. **Hybrid Storage Architecture**:
   - **Problem**: Need both responsive UI and persistent data storage
   - **Solution**: Streamlit session state + PostgreSQL database
   - **Pros**: Fast UI responsiveness, persistent storage, data recovery, advanced search
   - **Cons**: Increased complexity, database dependency

5. **Rate Limiting Implementation**:
   - **Problem**: Need to respect target websites and avoid blocking
   - **Solution**: Configurable delays and request limits
   - **Pros**: Ethical scraping, reduced server load
   - **Cons**: Slower data collection

The application is designed for both individual users and enterprise scenarios with full database persistence, making it suitable for cloud deployment with PostgreSQL infrastructure. Enhanced bulk processing capabilities support enterprise-level email validation tasks with up to 1000 emails per session, with all data saved persistently for future reference and analysis.

## Recent Changes (July 24, 2025)

### Added Database Support (PostgreSQL)
- **Persistent Data Storage**: All scraped emails and validation results now saved to PostgreSQL database
- **Database Management Tab**: New dedicated interface for database operations
- **Session Tracking**: Automatic tracking of scraping and validation sessions with metadata
- **Advanced Search**: Search emails by domain or address across all historical data
- **Data Recovery**: Load previous results and continue interrupted validation sessions
- **Database Analytics**: Comprehensive statistics and analytics dashboard
- **Data Export**: Full database export capabilities with filtering options
- **Database Maintenance**: Built-in cleanup tools and connection monitoring

### Enhanced Bulk Processing Features
- **New Bulk Operations Tab**: Dedicated interface for large-scale email processing
- **Bulk Website Scraping**: Process up to 50 URLs simultaneously with progress tracking
- **Bulk Email Import**: Support for importing up to 1000 emails via text area or CSV upload
- **Enhanced Validation**: Batch processing with configurable batch sizes (50-500 emails)
- **Resume Capability**: Continue validation from interruption points
- **Validation Modes**: Three modes - Complete (4-stage), Quick (format + DNS), Format only
- **Advanced Export**: Multiple formats (CSV, Excel, JSON) with filtering and analytics
- **Performance Optimization**: Reduced rate limiting for bulk operations while maintaining ethical scraping practices