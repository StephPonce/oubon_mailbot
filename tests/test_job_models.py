"""
Tests for Job Database Models
==============================

Tests for background job persistence and storage.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from ospra_os.database.job_models import (
    Job,
    JobStatus,
    JobStorage,
)


class TestJobStatus:
    """Tests for JobStatus enum"""

    def test_status_values(self):
        """Test all status values exist"""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"


class TestJobModel:
    """Tests for Job model"""

    def test_create_job(self, db_session):
        """Test creating a job"""
        job = Job(
            id="job_123",
            job_type="product_deploy",
            user_id=1,
            status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        assert job.id == "job_123"
        assert job.job_type == "product_deploy"
        assert job.status == JobStatus.PENDING
        assert job.progress_percent == 0

    def test_set_progress(self, db_session):
        """Test setting job progress"""
        job = Job(
            id="job_progress",
            job_type="test",
            status=JobStatus.RUNNING
        )
        db_session.add(job)
        db_session.commit()

        job.set_progress(50, "Half done", {"items_processed": 10})
        db_session.commit()

        assert job.progress_percent == 50
        assert job.progress_message == "Half done"
        assert json.loads(job.progress_data) == {"items_processed": 10}

    def test_get_progress(self, db_session):
        """Test getting job progress"""
        job = Job(
            id="job_get_progress",
            job_type="test",
            status=JobStatus.RUNNING,
            progress_percent=75,
            progress_message="Almost done",
            progress_data=json.dumps({"step": 3})
        )
        db_session.add(job)
        db_session.commit()

        progress = job.get_progress()

        assert progress["percent"] == 75
        assert progress["message"] == "Almost done"
        assert progress["data"] == {"step": 3}

    def test_set_result(self, db_session):
        """Test setting job result"""
        job = Job(
            id="job_result",
            job_type="test",
            status=JobStatus.RUNNING
        )
        db_session.add(job)
        db_session.commit()

        job.set_result({"output": "success", "count": 42})
        db_session.commit()

        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert json.loads(job.result_data) == {"output": "success", "count": 42}

    def test_get_result(self, db_session):
        """Test getting job result"""
        job = Job(
            id="job_get_result",
            job_type="test",
            status=JobStatus.COMPLETED,
            result_data=json.dumps({"data": [1, 2, 3]})
        )
        db_session.add(job)
        db_session.commit()

        result = job.get_result()

        assert result == {"data": [1, 2, 3]}

    def test_get_result_none(self, db_session):
        """Test getting result when none exists"""
        job = Job(
            id="job_no_result",
            job_type="test",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        assert job.get_result() is None

    def test_set_error(self, db_session):
        """Test setting job error"""
        job = Job(
            id="job_error",
            job_type="test",
            status=JobStatus.RUNNING
        )
        db_session.add(job)
        db_session.commit()

        job.set_error("Connection timeout")
        db_session.commit()

        assert job.status == JobStatus.FAILED
        assert job.error_message == "Connection timeout"
        assert job.completed_at is not None

    def test_to_dict(self, db_session):
        """Test converting job to dictionary"""
        now = datetime.utcnow()
        job = Job(
            id="job_dict",
            job_type="product_deploy",
            status=JobStatus.COMPLETED,
            progress_percent=100,
            progress_message="Done",
            result_data=json.dumps({"success": True}),
            created_at=now,
            started_at=now,
            completed_at=now
        )
        db_session.add(job)
        db_session.commit()

        job_dict = job.to_dict()

        assert job_dict["job_id"] == "job_dict"
        assert job_dict["job_type"] == "product_deploy"
        assert job_dict["status"] == "completed"
        assert job_dict["progress"]["percent"] == 100
        assert job_dict["result"] == {"success": True}


class TestJobStorage:
    """Tests for JobStorage class"""

    @pytest.fixture
    def job_storage(self, db_session):
        """Create job storage with test session"""
        def session_factory():
            return db_session

        return JobStorage(session_factory)

    def test_create_job(self, job_storage, db_session):
        """Test creating a job via storage"""
        job = job_storage.create_job(
            job_id="storage_job_1",
            job_type="test_job",
            user_id=1
        )

        # Retrieve the job to verify (the returned job may be detached from session)
        retrieved = job_storage.get_job("storage_job_1")
        assert retrieved is not None
        assert retrieved.id == "storage_job_1"
        assert retrieved.job_type == "test_job"
        assert retrieved.user_id == 1

    def test_get_job(self, job_storage, db_session):
        """Test getting a job"""
        # Create job directly
        job = Job(
            id="storage_get_job",
            job_type="test",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        # Get via storage
        retrieved = job_storage.get_job("storage_get_job")

        assert retrieved is not None
        assert retrieved.id == "storage_get_job"

    def test_get_nonexistent_job(self, job_storage):
        """Test getting a job that doesn't exist"""
        job = job_storage.get_job("nonexistent_job")

        assert job is None

    def test_update_job(self, job_storage, db_session):
        """Test updating a job"""
        job = Job(
            id="storage_update_job",
            job_type="test",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        job_storage.update_job(
            "storage_update_job",
            progress_percent=50,
            progress_message="Halfway"
        )

        updated = job_storage.get_job("storage_update_job")
        assert updated.progress_percent == 50
        assert updated.progress_message == "Halfway"

    def test_start_job(self, job_storage, db_session):
        """Test starting a job"""
        job = Job(
            id="storage_start_job",
            job_type="test",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        job_storage.start_job("storage_start_job")

        started = job_storage.get_job("storage_start_job")
        assert started.status == JobStatus.RUNNING
        assert started.started_at is not None

    def test_complete_job(self, job_storage, db_session):
        """Test completing a job"""
        job = Job(
            id="storage_complete_job",
            job_type="test",
            status=JobStatus.RUNNING
        )
        db_session.add(job)
        db_session.commit()

        job_storage.complete_job(
            "storage_complete_job",
            result={"items": 100}
        )

        completed = job_storage.get_job("storage_complete_job")
        assert completed.status == JobStatus.COMPLETED
        assert completed.get_result() == {"items": 100}

    def test_fail_job(self, job_storage, db_session):
        """Test failing a job"""
        job = Job(
            id="storage_fail_job",
            job_type="test",
            status=JobStatus.RUNNING
        )
        db_session.add(job)
        db_session.commit()

        job_storage.fail_job("storage_fail_job", "Network error")

        failed = job_storage.get_job("storage_fail_job")
        assert failed.status == JobStatus.FAILED
        assert failed.error_message == "Network error"

    def test_update_progress(self, job_storage, db_session):
        """Test updating job progress"""
        job = Job(
            id="storage_progress_job",
            job_type="test",
            status=JobStatus.RUNNING
        )
        db_session.add(job)
        db_session.commit()

        job_storage.update_progress(
            "storage_progress_job",
            percent=75,
            message="Processing items",
            data={"current_item": 15}
        )

        updated = job_storage.get_job("storage_progress_job")
        assert updated.progress_percent == 75

    def test_get_user_jobs(self, job_storage, db_session):
        """Test getting jobs for a user"""
        # Create multiple jobs for user
        for i in range(5):
            job = Job(
                id=f"user_job_{i}",
                job_type="test",
                user_id=42,
                status=JobStatus.COMPLETED
            )
            db_session.add(job)
        db_session.commit()

        jobs = job_storage.get_user_jobs(user_id=42, limit=10)

        assert len(jobs) == 5

    def test_dictionary_interface_getitem(self, job_storage, db_session):
        """Test dictionary-like access"""
        job = Job(
            id="dict_job",
            job_type="test",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        job_dict = job_storage["dict_job"]

        assert job_dict["job_id"] == "dict_job"
        assert job_dict["status"] == "pending"

    def test_dictionary_interface_contains(self, job_storage, db_session):
        """Test dictionary-like contains check"""
        job = Job(
            id="contains_job",
            job_type="test",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        assert "contains_job" in job_storage
        assert "nonexistent" not in job_storage

    def test_dictionary_interface_get(self, job_storage, db_session):
        """Test dictionary-like get with default"""
        job = Job(
            id="get_job",
            job_type="test",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        # Existing job
        result = job_storage.get("get_job")
        assert result is not None

        # Non-existing with default
        result = job_storage.get("nonexistent", default={"status": "unknown"})
        assert result == {"status": "unknown"}
