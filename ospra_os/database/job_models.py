"""
Job Database Models
====================

Models for persisting background job status to the database.
Replaces in-memory job storage for production reliability.

Author: OspraOS
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum

# Use the shared Base from database.base for proper table creation
from ospra_os.database.base import Base

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """
    Background job model for persistent job tracking.

    Stores job status, progress, results, and errors in the database
    instead of in-memory for reliability across restarts.
    """
    __tablename__ = "background_jobs"

    id = Column(String(50), primary_key=True, index=True)
    job_type = Column(String(50), nullable=False, index=True)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, index=True)
    user_id = Column(Integer, index=True, nullable=True)

    # Progress tracking
    progress_percent = Column(Integer, default=0)
    progress_message = Column(String(255), nullable=True)
    progress_data = Column(Text, nullable=True)  # JSON

    # Results
    result_data = Column(Text, nullable=True)  # JSON
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def set_progress(self, percent: int, message: str = None, data: dict = None):
        """Update job progress."""
        self.progress_percent = percent
        self.progress_message = message
        if data:
            self.progress_data = json.dumps(data)

    def get_progress(self) -> Dict[str, Any]:
        """Get progress as dictionary."""
        return {
            "percent": self.progress_percent,
            "message": self.progress_message,
            "data": json.loads(self.progress_data) if self.progress_data else None
        }

    def set_result(self, result: dict):
        """Set job result."""
        self.result_data = json.dumps(result)
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def get_result(self) -> Optional[Dict[str, Any]]:
        """Get result as dictionary."""
        return json.loads(self.result_data) if self.result_data else None

    def set_error(self, error: str):
        """Set job error."""
        self.error_message = error
        self.status = JobStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "job_id": self.id,
            "job_type": self.job_type,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "progress": self.get_progress(),
            "result": self.get_result(),
            "error": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class JobStorage:
    """
    Database-backed job storage.

    Provides a dictionary-like interface for compatibility with existing code,
    but stores jobs in the database for persistence.
    """

    def __init__(self, session_factory):
        """
        Initialize with a session factory.

        Args:
            session_factory: SQLAlchemy session factory or callable that returns a session
        """
        self._session_factory = session_factory

    def _get_session(self):
        """Get a database session."""
        return self._session_factory()

    def create_job(self, job_id: str, job_type: str, user_id: int = None) -> Job:
        """Create a new job."""
        session = self._get_session()
        try:
            job = Job(id=job_id, job_type=job_type, user_id=user_id)
            session.add(job)
            session.commit()
            return job
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create job {job_id}: {e}")
            raise
        finally:
            session.close()

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        session = self._get_session()
        try:
            return session.query(Job).filter(Job.id == job_id).first()
        finally:
            session.close()

    def update_job(self, job_id: str, **kwargs) -> Optional[Job]:
        """Update a job."""
        session = self._get_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                session.commit()
            return job
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update job {job_id}: {e}")
            raise
        finally:
            session.close()

    def start_job(self, job_id: str) -> Optional[Job]:
        """Mark a job as running."""
        return self.update_job(
            job_id,
            status=JobStatus.RUNNING,
            started_at=datetime.now(timezone.utc)
        )

    def complete_job(self, job_id: str, result: dict) -> Optional[Job]:
        """Mark a job as completed with result."""
        session = self._get_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.set_result(result)
                session.commit()
            return job
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to complete job {job_id}: {e}")
            raise
        finally:
            session.close()

    def fail_job(self, job_id: str, error: str) -> Optional[Job]:
        """Mark a job as failed with error."""
        session = self._get_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.set_error(error)
                session.commit()
            return job
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to fail job {job_id}: {e}")
            raise
        finally:
            session.close()

    def update_progress(self, job_id: str, percent: int, message: str = None, data: dict = None):
        """Update job progress."""
        session = self._get_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.set_progress(percent, message, data)
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update progress for job {job_id}: {e}")
        finally:
            session.close()

    def get_user_jobs(self, user_id: int, limit: int = 20) -> list:
        """Get jobs for a user."""
        session = self._get_session()
        try:
            jobs = session.query(Job).filter(
                Job.user_id == user_id
            ).order_by(Job.created_at.desc()).limit(limit).all()
            return [job.to_dict() for job in jobs]
        finally:
            session.close()

    def cleanup_old_jobs(self, days: int = 7):
        """Clean up jobs older than specified days."""
        from datetime import timedelta

        session = self._get_session()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            deleted = session.query(Job).filter(
                Job.completed_at < cutoff
            ).delete()
            session.commit()
            logger.info(f"Cleaned up {deleted} old jobs")
            return deleted
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0
        finally:
            session.close()

    # Dictionary-like interface for compatibility
    def __getitem__(self, job_id: str) -> dict:
        """Get job as dictionary."""
        job = self.get_job(job_id)
        if job:
            return job.to_dict()
        raise KeyError(job_id)

    def __setitem__(self, job_id: str, value: dict):
        """Update job from dictionary."""
        job = self.get_job(job_id)
        if job:
            self.update_job(job_id, **value)
        else:
            # Create new job
            self.create_job(
                job_id,
                job_type=value.get("job_type", "unknown"),
                user_id=value.get("user_id")
            )

    def __contains__(self, job_id: str) -> bool:
        """Check if job exists."""
        return self.get_job(job_id) is not None

    def get(self, job_id: str, default=None):
        """Get job or default."""
        job = self.get_job(job_id)
        return job.to_dict() if job else default


logger.info("[SUCCESS] Job models loaded")
