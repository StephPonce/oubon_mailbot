"""
Ad Schedule Database Models
"""
from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class ScheduleStatus(enum.Enum):
    """Schedule status enum"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AdSchedule(Base):
    """Ad campaign schedule"""
    __tablename__ = 'ad_schedules'

    id = Column(String, primary_key=True)

    # Campaign info
    campaign_id = Column(String, nullable=True)  # Meta campaign ID (after created)
    product_id = Column(String, nullable=False)  # Internal product ID
    product_name = Column(String, nullable=False)

    # Schedule timing
    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=True)

    # Budget
    daily_budget = Column(Float, nullable=False)
    total_budget = Column(Float, nullable=True)

    # Status
    status = Column(SQLEnum(ScheduleStatus), default=ScheduleStatus.PENDING)

    # Platform
    platform = Column(String, default='meta')  # meta, tiktok, google

    # Targeting
    target_audience = Column(JSON, nullable=True)

    # Results
    campaign_data = Column(JSON, nullable=True)  # Full campaign response
    performance_data = Column(JSON, nullable=True)  # Latest metrics

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Metadata
    created_by = Column(String, nullable=True)
    notes = Column(String, nullable=True)


class ScheduleLog(Base):
    """Log of schedule actions"""
    __tablename__ = 'schedule_logs'

    id = Column(String, primary_key=True)
    schedule_id = Column(String, nullable=False)

    action = Column(String, nullable=False)  # created, activated, paused, completed, failed
    message = Column(String, nullable=True)
    details = Column(JSON, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow)
