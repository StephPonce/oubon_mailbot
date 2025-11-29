"""
Monitoring Models - Database schemas for system health monitoring

Tables:
- system_health_snapshots: Periodic system health snapshots
- integration_health_logs: Integration health check logs
- job_runs: Background job run history
- system_errors: System error log
- system_alerts: Active system alerts
- api_request_logs: API request metrics (sampled)
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class SystemHealthSnapshot(Base):
    """Periodic system health snapshots"""
    __tablename__ = "system_health_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, default=datetime.utcnow)

    overall_status = Column(String(50))  # HEALTHY, DEGRADED, CRITICAL, DOWN
    integrations_status = Column(JSON)
    jobs_status = Column(JSON)
    api_performance = Column(JSON)
    system_resources = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_snapshots_timestamp', 'timestamp'),
    )


class IntegrationHealthLog(Base):
    """Integration health check logs"""
    __tablename__ = "integration_health_logs"

    id = Column(Integer, primary_key=True, index=True)
    integration_name = Column(String(100), index=True, nullable=False)

    status = Column(String(50), nullable=False)  # CONNECTED, DEGRADED, DISCONNECTED, ERROR
    latency_ms = Column(Float)
    error_message = Column(Text)
    details = Column(JSON)

    checked_at = Column(DateTime, index=True, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_integration_health_name_time', 'integration_name', 'checked_at'),
    )


class JobRun(Base):
    """Background job run history"""
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), unique=True, index=True, nullable=False)
    job_name = Column(String(100), index=True, nullable=False)

    status = Column(String(50), nullable=False)  # RUNNING, SUCCESS, FAILED, CANCELLED
    started_at = Column(DateTime, index=True, nullable=False)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    items_processed = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    error_message = Column(Text)
    details = Column(JSON)

    triggered_by = Column(String(50), default="scheduler")  # scheduler, manual, system

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_job_runs_name_time', 'job_name', 'started_at'),
        Index('ix_job_runs_status', 'status'),
    )


class SystemError(Base):
    """System error log"""
    __tablename__ = "system_errors"

    id = Column(Integer, primary_key=True, index=True)
    error_id = Column(String(100), unique=True, index=True, nullable=False)

    category = Column(String(100), index=True, nullable=False)
    severity = Column(String(50), index=True, nullable=False)
    source = Column(String(200))
    message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    details = Column(JSON)

    acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(100))

    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime)
    resolution = Column(Text)

    occurred_at = Column(DateTime, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_errors_category_time', 'category', 'occurred_at'),
        Index('ix_errors_severity_time', 'severity', 'occurred_at'),
    )


class SystemAlert(Base):
    """Active system alerts"""
    __tablename__ = "system_alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, index=True, nullable=False)

    alert_type = Column(String(100), index=True, nullable=False)
    severity = Column(String(50), index=True, nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    source = Column(String(200))

    is_active = Column(Boolean, default=True, index=True)
    triggered_at = Column(DateTime, index=True, nullable=False)
    resolved_at = Column(DateTime)

    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_alerts_active_time', 'is_active', 'triggered_at'),
        Index('ix_alerts_type', 'alert_type'),
    )


class ApiRequestLog(Base):
    """API request metrics (sampled)"""
    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, index=True)

    endpoint = Column(String(255), index=True, nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, index=True, nullable=False)
    duration_ms = Column(Float, nullable=False)

    error = Column(Text)

    timestamp = Column(DateTime, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_api_logs_endpoint_time', 'endpoint', 'timestamp'),
        Index('ix_api_logs_status', 'status_code'),
    )
