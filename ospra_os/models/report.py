"""
Report Models - Database schemas for reporting engine

Tables:
- report_templates: Predefined and custom report templates
- generated_reports: History of generated reports
- report_schedules: Automated report schedules
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class ReportTemplate(Base):
    """Report templates - system templates and user-created custom templates"""
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    report_type = Column(String(50))  # executive, revenue, full, pnl, product, ad, custom

    # Configuration
    default_config = Column(JSON)  # Default settings for this template
    sections = Column(JSON)  # Available sections ["executive", "revenue", "products"]
    filters = Column(JSON)  # Default filters

    # Metadata
    is_system = Column(Boolean, default=False)  # System templates vs user-created
    created_by = Column(String(100))  # User ID or 'system'
    store_id = Column(String(100))  # For multi-tenant support

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GeneratedReport(Base):
    """Generated reports - history of all reports created"""
    __tablename__ = "generated_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String(100), unique=True, index=True, nullable=False)
    template_id = Column(String(100), index=True)
    name = Column(String(255), nullable=False)

    # Configuration used
    config = Column(JSON)  # Full config used to generate this report

    # Generation details
    format = Column(String(20), default='pdf')  # pdf, html, csv
    file_path = Column(String(512))  # Relative path to stored file
    file_size_kb = Column(Integer)
    generation_time_ms = Column(Integer)

    # Date range covered by report
    date_range_start = Column(DateTime)
    date_range_end = Column(DateTime)

    # Metadata
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    generated_by = Column(String(100))  # User ID or schedule_id
    store_id = Column(String(100), index=True)

    # Delivery status
    delivery_status = Column(JSON)  # {"email": "sent", "slack": "sent", "webhook": "failed"}
    delivery_attempts = Column(Integer, default=0)

    # Soft delete
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)


class ReportSchedule(Base):
    """Report schedules - automated report generation"""
    __tablename__ = "report_schedules"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Report configuration
    report_config = Column(JSON, nullable=False)  # Full config for report generation

    # Schedule settings
    frequency = Column(String(20), nullable=False)  # daily, weekly, monthly
    day_of_week = Column(Integer)  # 0-6 (Monday-Sunday) for weekly schedules
    day_of_month = Column(Integer)  # 1-31 for monthly schedules
    time = Column(String(5), nullable=False)  # HH:MM format (24-hour)
    timezone = Column(String(50), default='UTC')

    # Delivery settings
    recipients = Column(JSON)  # {"email": [...], "slack": "#channel", "webhook": "url"}

    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_run = Column(DateTime)
    next_run = Column(DateTime, index=True)

    # Statistics
    total_runs = Column(Integer, default=0)
    successful_runs = Column(Integer, default=0)
    failed_runs = Column(Integer, default=0)

    # Metadata
    created_by = Column(String(100))
    store_id = Column(String(100), index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Initialize database tables
def init_report_tables(engine):
    """Create all report tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Report tables created")
