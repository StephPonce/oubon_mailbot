"""
Discovery jobs — job+poll replacement for the synchronous cold path.

The on-demand discovery request was a single 45–95s HTTP call threaded
through TimeoutMiddleware (120s) and Render's proxy timeout — any kill along
that chain surfaced as the browser's "Discovery unavailable / Load failed"
(July 2026 reliability spec). A job row + 3s polling makes the long run
survivable, and the one-live-job-per-niche rule is the refresh-spam cost
guard: page refreshes used to stack concurrent 45–95s discovery runs, each
burning paid API calls.

Deliberately NOT Celery: the runner is FastAPI BackgroundTasks in-process
(no worker service exists in render.yaml and none is being added). Restart
orphans are recovered lazily by the GET handler (running >10min → error) —
no reaper process.

Results are NOT stored here — the job runner upserts into discovered_catalog
(via catalog_warm.warm_niche), which stays the single source of truth. This
table only tracks run state.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from ospra_os.database.base import Base

# status values
QUEUED = "queued"
RUNNING = "running"
DONE = "done"
ERROR = "error"

# A running job with started_at older than this is a deploy-restart orphan:
# BackgroundTasks die with the process and nothing else will ever finish it.
ORPHAN_MINUTES = 10


class DiscoveryJob(Base):
    __tablename__ = "discovery_jobs"

    id = Column(Integer, primary_key=True)
    niche = Column(String(64), nullable=False, index=True)
    count = Column(Integer, nullable=False, default=20)
    status = Column(String(16), nullable=False, default=QUEUED, index=True)
    error_text = Column(Text, nullable=True)
    result_count = Column(Integer, nullable=True)
    requested_by = Column(String(128), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "niche": self.niche,
            "count": self.count,
            "status": self.status,
            "error": self.error_text,
            "result_count": self.result_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
