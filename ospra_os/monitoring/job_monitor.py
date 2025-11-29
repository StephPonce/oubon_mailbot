"""
Job Monitor
Monitor background job status and history
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import statistics


class JobMonitor:
    """Monitor background jobs"""

    # Registered jobs with their schedules
    JOBS = {
        "product_discovery": {
            "description": "Daily product discovery and scoring",
            "schedule": "0 3 * * *",  # 3 AM daily
            "timeout_minutes": 30
        },
        "competitor_monitoring": {
            "description": "Monitor competitor prices and products",
            "schedule": "0 2 * * *",  # 2 AM daily
            "timeout_minutes": 60
        },
        "email_processor": {
            "description": "Process and respond to emails",
            "schedule": "*/5 * * * *",  # Every 5 minutes
            "timeout_minutes": 5
        },
        "inventory_sync": {
            "description": "Sync inventory with Shopify",
            "schedule": "0 */6 * * *",  # Every 6 hours
            "timeout_minutes": 15
        },
        "analytics_aggregation": {
            "description": "Aggregate daily analytics",
            "schedule": "0 0 * * *",  # Midnight daily
            "timeout_minutes": 20
        },
        "ab_test_monitor": {
            "description": "Monitor A/B tests for significance",
            "schedule": "0 * * * *",  # Every hour
            "timeout_minutes": 10
        },
        "ranking_update": {
            "description": "Update product rankings",
            "schedule": "0 3 * * *",  # 3 AM daily
            "timeout_minutes": 15
        },
        "niche_analysis": {
            "description": "Weekly niche health analysis",
            "schedule": "0 6 * * 0",  # Sunday 6 AM
            "timeout_minutes": 45
        }
    }

    def __init__(self):
        self.job_runs = {}  # run_id -> run_data
        self.runs_by_job = {job_name: [] for job_name in self.JOBS.keys()}
        self.running_jobs = {}  # job_name -> run_id
        self.disabled_jobs = set()

    async def get_job_status(self, job_name: str) -> Optional[dict]:
        """Get current status of job"""
        if job_name not in self.JOBS:
            return None

        job_info = self.JOBS[job_name]
        runs = self.runs_by_job.get(job_name, [])

        # Get last run
        last_run = None
        if runs:
            last_run_id = runs[-1]
            last_run = self.job_runs.get(last_run_id)

        # Calculate stats from last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_runs = [
            self.job_runs[rid] for rid in runs
            if self.job_runs.get(rid) and self.job_runs[rid]['started_at'] > week_ago
        ]

        successful_runs = [r for r in recent_runs if r['status'] == 'SUCCESS']
        success_rate = (len(successful_runs) / len(recent_runs) * 100) if recent_runs else 100

        durations = [r['duration_seconds'] for r in successful_runs if r.get('duration_seconds')]
        avg_duration = statistics.mean(durations) if durations else 0

        # Get recent errors
        recent_errors = [
            {"time": r['started_at'], "error": r['error_message']}
            for r in recent_runs
            if r['status'] == 'FAILED' and r.get('error_message')
        ][:3]

        # Determine current status
        is_running = job_name in self.running_jobs
        is_disabled = job_name in self.disabled_jobs

        status = "IDLE"
        if is_disabled:
            status = "DISABLED"
        elif is_running:
            status = "RUNNING"
        elif last_run and last_run['status'] == 'FAILED':
            status = "FAILED"

        return {
            "name": job_name,
            "description": job_info['description'],
            "status": status,
            "schedule": job_info['schedule'],
            "timeout_minutes": job_info['timeout_minutes'],
            "last_run": {
                "started_at": last_run['started_at'] if last_run else None,
                "completed_at": last_run.get('completed_at') if last_run else None,
                "duration_seconds": last_run.get('duration_seconds') if last_run else None,
                "status": last_run['status'] if last_run else None,
                "items_processed": last_run.get('items_processed', 0) if last_run else 0,
                "errors": last_run.get('errors_count', 0) if last_run else 0
            } if last_run else None,
            "success_rate_7d": success_rate,
            "avg_duration_7d": avg_duration,
            "recent_errors": recent_errors
        }

    async def get_all_jobs(self) -> List[dict]:
        """Get status of all jobs"""
        jobs = []
        for job_name in self.JOBS.keys():
            status = await self.get_job_status(job_name)
            if status:
                jobs.append(status)
        return jobs

    async def start_job_run(self, job_name: str, triggered_by: str = "scheduler") -> str:
        """Record job start, returns run_id"""
        if job_name not in self.JOBS:
            raise ValueError(f"Unknown job: {job_name}")

        run_id = str(uuid.uuid4())[:8]

        run_data = {
            "run_id": run_id,
            "job_name": job_name,
            "status": "RUNNING",
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "duration_seconds": None,
            "items_processed": 0,
            "errors_count": 0,
            "error_message": None,
            "details": {},
            "triggered_by": triggered_by
        }

        self.job_runs[run_id] = run_data
        self.runs_by_job[job_name].append(run_id)
        self.running_jobs[job_name] = run_id

        return run_id

    async def complete_job_run(
        self,
        run_id: str,
        status: str,
        items_processed: int = 0,
        errors: int = 0,
        details: dict = None
    ):
        """Record job completion"""
        if run_id not in self.job_runs:
            return

        run = self.job_runs[run_id]
        run['status'] = status
        run['completed_at'] = datetime.utcnow()
        run['duration_seconds'] = (run['completed_at'] - run['started_at']).total_seconds()
        run['items_processed'] = items_processed
        run['errors_count'] = errors
        if details:
            run['details'] = details

        # Remove from running jobs
        job_name = run['job_name']
        if job_name in self.running_jobs and self.running_jobs[job_name] == run_id:
            del self.running_jobs[job_name]

    async def fail_job_run(self, run_id: str, error: str):
        """Record job failure"""
        if run_id not in self.job_runs:
            return

        run = self.job_runs[run_id]
        run['status'] = 'FAILED'
        run['completed_at'] = datetime.utcnow()
        run['duration_seconds'] = (run['completed_at'] - run['started_at']).total_seconds()
        run['error_message'] = error

        # Remove from running jobs
        job_name = run['job_name']
        if job_name in self.running_jobs and self.running_jobs[job_name] == run_id:
            del self.running_jobs[job_name]

    async def get_job_history(self, job_name: str, days: int = 7) -> List[dict]:
        """Get run history for job"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        runs = self.runs_by_job.get(job_name, [])
        history = [
            self.job_runs[rid] for rid in runs
            if rid in self.job_runs and self.job_runs[rid]['started_at'] > cutoff
        ]

        history.sort(key=lambda x: x['started_at'], reverse=True)
        return history

    async def trigger_job(self, job_name: str) -> dict:
        """Manually trigger job execution"""
        if job_name not in self.JOBS:
            raise ValueError(f"Unknown job: {job_name}")

        if job_name in self.running_jobs:
            return {
                "success": False,
                "message": f"Job {job_name} is already running"
            }

        if job_name in self.disabled_jobs:
            return {
                "success": False,
                "message": f"Job {job_name} is disabled"
            }

        # This would actually trigger the job - for now just return success
        return {
            "success": True,
            "message": f"Job {job_name} triggered successfully",
            "job_name": job_name
        }

    async def disable_job(self, job_name: str):
        """Temporarily disable job"""
        if job_name in self.JOBS:
            self.disabled_jobs.add(job_name)

    async def enable_job(self, job_name: str):
        """Re-enable disabled job"""
        self.disabled_jobs.discard(job_name)

    async def get_running_jobs(self) -> List[dict]:
        """Get currently running jobs"""
        running = []
        for job_name, run_id in self.running_jobs.items():
            run = self.job_runs.get(run_id)
            if run:
                duration = (datetime.utcnow() - run['started_at']).total_seconds()
                running.append({
                    "job_name": job_name,
                    "run_id": run_id,
                    "started_at": run['started_at'],
                    "duration_seconds": duration,
                    "details": run.get('details', {})
                })
        return running

    async def check_stalled_jobs(self) -> List[dict]:
        """Find jobs running longer than timeout"""
        stalled = []
        for job_name, run_id in self.running_jobs.items():
            run = self.job_runs.get(run_id)
            if not run:
                continue

            timeout_seconds = self.JOBS[job_name]['timeout_minutes'] * 60
            duration = (datetime.utcnow() - run['started_at']).total_seconds()

            if duration > timeout_seconds:
                stalled.append({
                    "name": job_name,
                    "run_id": run_id,
                    "duration": duration,
                    "timeout": timeout_seconds,
                    "started_at": run['started_at']
                })

        return stalled


# Global job monitor instance
job_monitor = JobMonitor()


class JobRun:
    """Context manager for tracking job runs"""

    def __init__(self, job_name: str, monitor: JobMonitor = None):
        self.job_name = job_name
        self.monitor = monitor or job_monitor
        self.run_id = None
        self.items_processed = 0
        self.errors = 0

    async def __aenter__(self):
        self.run_id = await self.monitor.start_job_run(self.job_name, triggered_by="manual")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.monitor.fail_job_run(self.run_id, str(exc_val))
        else:
            await self.monitor.complete_job_run(
                self.run_id,
                status="SUCCESS",
                items_processed=self.items_processed,
                errors=self.errors
            )
        return False  # Don't suppress exceptions
