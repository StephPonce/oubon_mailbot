"""
Schedule Manager - Handle ad scheduling and automation
"""
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from ospra_os.models.ad_schedule import AdSchedule, ScheduleLog, ScheduleStatus, Base
from ospra_os.integrations.meta.campaign_builder import CampaignBuilder
from ospra_os.integrations.meta.client import MetaAdsClient


class ScheduleManager:
    """Manage ad campaign scheduling"""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        try:
            self.meta_builder = CampaignBuilder()
            self.meta_client = MetaAdsClient()
        except ValueError:
            # Meta credentials not configured - that's OK
            self.meta_builder = None
            self.meta_client = None

    def _get_session(self) -> Session:
        """Get database session"""
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=self.engine)
        return SessionLocal()

    async def create_schedule(
        self,
        product: Dict,
        scheduled_start: datetime,
        daily_budget: float,
        scheduled_end: datetime = None,
        total_budget: float = None,
        platform: str = 'meta',
        target_audience: Dict = None
    ) -> Dict:
        """
        Schedule an ad campaign for future activation

        Args:
            product: Product data
            scheduled_start: When to activate campaign
            daily_budget: Daily ad spend
            scheduled_end: Optional end date
            total_budget: Optional total budget cap
            platform: Ad platform (meta, tiktok, google)
            target_audience: Targeting parameters

        Returns:
            Schedule details with schedule_id
        """
        try:
            session = self._get_session()

            schedule_id = str(uuid.uuid4())

            schedule = AdSchedule(
                id=schedule_id,
                product_id=product.get('id', str(uuid.uuid4())),
                product_name=product.get('name', 'Unknown Product'),
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                daily_budget=daily_budget,
                total_budget=total_budget,
                status=ScheduleStatus.PENDING,
                platform=platform,
                target_audience=target_audience
            )

            session.add(schedule)

            # Log creation
            log = ScheduleLog(
                id=str(uuid.uuid4()),
                schedule_id=schedule_id,
                action='created',
                message='Schedule created',
                details={
                    'scheduled_start': scheduled_start.isoformat(),
                    'daily_budget': daily_budget,
                    'platform': platform
                }
            )
            session.add(log)

            session.commit()

            print(f"[SUCCESS] Schedule created: {schedule_id}")
            print(f"   Activation: {scheduled_start}")
            print(f"   Budget: ${daily_budget}/day")

            return {
                'success': True,
                'schedule_id': schedule_id,
                'scheduled_start': scheduled_start.isoformat(),
                'status': 'pending'
            }

        except Exception as e:
            print(f"[ERROR] Schedule creation error: {e}")
            session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            session.close()

    async def process_pending_schedules(self) -> List[Dict]:
        """
        Check for schedules that should be activated
        Called by background job every 5 minutes

        Returns list of activated schedules
        """
        try:
            session = self._get_session()

            now = datetime.utcnow()

            # Get schedules that should start now
            pending = session.query(AdSchedule).filter(
                AdSchedule.status == ScheduleStatus.PENDING,
                AdSchedule.scheduled_start <= now
            ).all()

            if not pending:
                return []

            print(f"\n[ALARM] Processing {len(pending)} pending schedules...")

            results = []

            for schedule in pending:
                result = await self._activate_schedule(schedule, session)
                results.append(result)

            session.commit()

            successful = sum(1 for r in results if r.get('success'))
            print(f"[SUCCESS] Activated {successful}/{len(pending)} schedules")

            return results

        except Exception as e:
            print(f"[ERROR] Schedule processing error: {e}")
            session.rollback()
            return []
        finally:
            session.close()

    async def _activate_schedule(
        self,
        schedule: AdSchedule,
        session: Session
    ) -> Dict:
        """Activate a single schedule"""
        try:
            print(f"\n[START] Activating schedule: {schedule.id}")
            print(f"   Product: {schedule.product_name}")

            if not self.meta_builder:
                raise Exception("Meta integration not configured")

            # Get product data (simplified for now)
            product = {
                'id': schedule.product_id,
                'name': schedule.product_name,
                'price': 29.99,  # TODO: Get from DB
                'niche': 'general'
            }

            # Create campaign
            if schedule.platform == 'meta':
                campaign_result = await self.meta_builder.create_complete_campaign(
                    product=product,
                    daily_budget=schedule.daily_budget,
                    target_audience=schedule.target_audience,
                    auto_activate=True  # Activate immediately
                )

                if not campaign_result.get('success'):
                    raise Exception(campaign_result.get('error'))

                # Update schedule
                schedule.campaign_id = campaign_result['campaign_id']
                schedule.campaign_data = campaign_result
                schedule.status = ScheduleStatus.ACTIVE
                schedule.activated_at = datetime.utcnow()

                # Log activation
                log = ScheduleLog(
                    id=str(uuid.uuid4()),
                    schedule_id=schedule.id,
                    action='activated',
                    message='Campaign activated',
                    details=campaign_result
                )
                session.add(log)

                print(f"[SUCCESS] Schedule activated! Campaign: {campaign_result['campaign_id']}")

                return {
                    'success': True,
                    'schedule_id': schedule.id,
                    'campaign_id': campaign_result['campaign_id']
                }

            else:
                raise Exception(f"Platform {schedule.platform} not supported yet")

        except Exception as e:
            print(f"[ERROR] Activation failed: {e}")

            schedule.status = ScheduleStatus.FAILED

            log = ScheduleLog(
                id=str(uuid.uuid4()),
                schedule_id=schedule.id,
                action='failed',
                message=str(e)
            )
            session.add(log)

            return {
                'success': False,
                'schedule_id': schedule.id,
                'error': str(e)
            }

    async def check_expired_schedules(self) -> List[Dict]:
        """
        Check for schedules that should end
        Called by background job every hour
        """
        try:
            session = self._get_session()

            now = datetime.utcnow()

            # Get active schedules past end date
            expired = session.query(AdSchedule).filter(
                AdSchedule.status == ScheduleStatus.ACTIVE,
                AdSchedule.scheduled_end <= now,
                AdSchedule.scheduled_end.isnot(None)
            ).all()

            if not expired:
                return []

            print(f"\n[ALARM] Processing {len(expired)} expired schedules...")

            results = []

            for schedule in expired:
                result = await self._complete_schedule(schedule, session)
                results.append(result)

            session.commit()

            return results

        except Exception as e:
            print(f"[ERROR] Expiry check error: {e}")
            session.rollback()
            return []
        finally:
            session.close()

    async def _complete_schedule(
        self,
        schedule: AdSchedule,
        session: Session
    ) -> Dict:
        """Complete/pause an expired schedule"""
        try:
            print(f"[STOP]  Completing schedule: {schedule.id}")

            # Pause Meta campaign
            if schedule.platform == 'meta' and schedule.campaign_id and self.meta_client:
                await self.meta_client.update_campaign_status(
                    schedule.campaign_id,
                    'PAUSED'
                )

            schedule.status = ScheduleStatus.COMPLETED
            schedule.completed_at = datetime.utcnow()

            log = ScheduleLog(
                id=str(uuid.uuid4()),
                schedule_id=schedule.id,
                action='completed',
                message='Schedule completed'
            )
            session.add(log)

            print(f"[SUCCESS] Schedule completed")

            return {
                'success': True,
                'schedule_id': schedule.id
            }

        except Exception as e:
            print(f"[ERROR] Completion error: {e}")
            return {
                'success': False,
                'schedule_id': schedule.id,
                'error': str(e)
            }

    def get_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Get schedule details"""
        try:
            session = self._get_session()

            schedule = session.query(AdSchedule).filter(
                AdSchedule.id == schedule_id
            ).first()

            if not schedule:
                return None

            return {
                'id': schedule.id,
                'product_name': schedule.product_name,
                'campaign_id': schedule.campaign_id,
                'scheduled_start': schedule.scheduled_start.isoformat(),
                'scheduled_end': schedule.scheduled_end.isoformat() if schedule.scheduled_end else None,
                'daily_budget': schedule.daily_budget,
                'status': schedule.status.value,
                'platform': schedule.platform,
                'created_at': schedule.created_at.isoformat(),
                'activated_at': schedule.activated_at.isoformat() if schedule.activated_at else None
            }

        finally:
            session.close()

    def list_schedules(
        self,
        status: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """List schedules"""
        try:
            session = self._get_session()

            query = session.query(AdSchedule)

            if status:
                query = query.filter(AdSchedule.status == ScheduleStatus(status))

            schedules = query.order_by(
                AdSchedule.scheduled_start.desc()
            ).limit(limit).all()

            return [
                {
                    'id': s.id,
                    'product_name': s.product_name,
                    'campaign_id': s.campaign_id,
                    'scheduled_start': s.scheduled_start.isoformat(),
                    'daily_budget': s.daily_budget,
                    'status': s.status.value,
                    'platform': s.platform
                }
                for s in schedules
            ]

        finally:
            session.close()

    async def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a pending schedule"""
        try:
            session = self._get_session()

            schedule = session.query(AdSchedule).filter(
                AdSchedule.id == schedule_id
            ).first()

            if not schedule:
                return False

            if schedule.status != ScheduleStatus.PENDING:
                print(f"[WARNING]  Cannot cancel schedule with status: {schedule.status.value}")
                return False

            schedule.status = ScheduleStatus.CANCELLED

            log = ScheduleLog(
                id=str(uuid.uuid4()),
                schedule_id=schedule_id,
                action='cancelled',
                message='Schedule cancelled by user'
            )
            session.add(log)

            session.commit()

            print(f"[SUCCESS] Schedule cancelled: {schedule_id}")

            return True

        except Exception as e:
            print(f"[ERROR] Cancel error: {e}")
            session.rollback()
            return False
        finally:
            session.close()
