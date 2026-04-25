"""
ACTION HISTORY - UNDO/REDO LOGGING SYSTEM

Tracks all executed actions for audit trail and undo capability.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class ActionLog(Base):
    """Database model for action history"""
    __tablename__ = 'action_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    action_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False)  # completed, failed, undone
    params = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    undo_available = Column(Boolean, default=False)
    undo_data = Column(JSON, nullable=True)  # Data needed to undo action
    undone_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "action_id": self.action_id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "status": self.status,
            "params": self.params,
            "result": self.result,
            "error_message": self.error_message,
            "undo_available": self.undo_available,
            "undone_at": self.undone_at.isoformat() if self.undone_at else None,
            "created_at": self.created_at.isoformat()
        }


class ActionHistory:
    """Manages action history logging and undo functionality"""

    def __init__(self, db_path: str = "data/action_history.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"[SUCCESS] Action history initialized: {db_path}")

    def log_action(
        self,
        action_id: str,
        user_id: int,
        action_type: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        status: str = "completed",
        undo_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> ActionLog:
        """
        Log an executed action.

        Args:
            action_id: Unique action identifier
            user_id: User who executed action
            action_type: Type of action
            params: Action parameters
            result: Action result
            status: Action status (completed, failed, undone)
            undo_data: Data needed to undo action
            error_message: Error message if failed

        Returns:
            ActionLog record
        """
        db = self.SessionLocal()

        try:
            action_log = ActionLog(
                action_id=action_id,
                user_id=user_id,
                action_type=action_type,
                status=status,
                params=params,
                result=result,
                error_message=error_message,
                undo_available=undo_data is not None,
                undo_data=undo_data
            )

            db.add(action_log)
            db.commit()
            db.refresh(action_log)

            logger.info(f"[SUCCESS] Action logged: {action_id} ({action_type}) by user {user_id}")
            return action_log

        except Exception as e:
            db.rollback()
            logger.error(f"[ERROR] Failed to log action: {e}")
            raise

        finally:
            db.close()

    def get_action(self, action_id: str) -> Optional[ActionLog]:
        """Get action by ID"""
        db = self.SessionLocal()
        try:
            return db.query(ActionLog).filter(ActionLog.action_id == action_id).first()
        finally:
            db.close()

    def get_user_actions(
        self,
        user_id: int,
        limit: int = 50,
        action_type: Optional[str] = None
    ) -> List[ActionLog]:
        """Get actions by user"""
        db = self.SessionLocal()
        try:
            query = db.query(ActionLog).filter(ActionLog.user_id == user_id)

            if action_type:
                query = query.filter(ActionLog.action_type == action_type)

            return query.order_by(ActionLog.created_at.desc()).limit(limit).all()

        finally:
            db.close()

    def mark_as_undone(self, action_id: str) -> bool:
        """Mark action as undone"""
        db = self.SessionLocal()

        try:
            action_log = db.query(ActionLog).filter(ActionLog.action_id == action_id).first()

            if not action_log:
                logger.error(f"[ERROR] Action not found: {action_id}")
                return False

            if not action_log.undo_available:
                logger.error(f"[ERROR] Action cannot be undone: {action_id}")
                return False

            if action_log.status == "undone":
                logger.warning(f"[WARNING]  Action already undone: {action_id}")
                return True

            action_log.status = "undone"
            action_log.undone_at = datetime.now(timezone.utc)

            db.commit()
            logger.info(f"[SUCCESS] Action marked as undone: {action_id}")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"[ERROR] Failed to mark action as undone: {e}")
            return False

        finally:
            db.close()

    def get_undo_data(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get undo data for action"""
        db = self.SessionLocal()
        try:
            action_log = db.query(ActionLog).filter(ActionLog.action_id == action_id).first()

            if not action_log:
                return None

            return action_log.undo_data

        finally:
            db.close()

    def get_action_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get action statistics"""
        db = self.SessionLocal()

        try:
            query = db.query(ActionLog)

            if user_id:
                query = query.filter(ActionLog.user_id == user_id)

            total_actions = query.count()
            completed_actions = query.filter(ActionLog.status == "completed").count()
            failed_actions = query.filter(ActionLog.status == "failed").count()
            undone_actions = query.filter(ActionLog.status == "undone").count()

            # Actions by type
            action_types = {}
            for action_type in ["deploy_product", "pause_campaign", "discontinue_product", "adjust_price", "create_campaign", "reply_email"]:
                count = query.filter(ActionLog.action_type == action_type).count()
                if count > 0:
                    action_types[action_type] = count

            return {
                "total_actions": total_actions,
                "completed": completed_actions,
                "failed": failed_actions,
                "undone": undone_actions,
                "by_type": action_types
            }

        finally:
            db.close()

    def cleanup_old_actions(self, days: int = 90) -> int:
        """Delete actions older than specified days"""
        db = self.SessionLocal()

        try:
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

            deleted = db.query(ActionLog).filter(ActionLog.created_at < cutoff_date).delete()
            db.commit()

            logger.info(f"[SUCCESS] Cleaned up {deleted} old actions (older than {days} days)")
            return deleted

        except Exception as e:
            db.rollback()
            logger.error(f"[ERROR] Failed to cleanup old actions: {e}")
            return 0

        finally:
            db.close()


# Singleton instance
_action_history = None


def get_action_history() -> ActionHistory:
    """Get or create action history instance"""
    global _action_history
    if _action_history is None:
        _action_history = ActionHistory()
    return _action_history
