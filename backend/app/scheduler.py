import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Set

from backend.app.db.database import SessionLocal
from backend.app.db.models import CensusSettingModel, FeedingScheduleModel, CensusRecordModel, FeedingObservationModel
from backend.app.census.census_engine import get_census_engine
from backend.app.feeding.feeding_engine import get_feeding_engine

logger = logging.getLogger("gaushala.scheduler")

class GaushalaScheduler:
    """
    Automated Background Scheduler for:
    - Official 05:00 AM & 05:00 PM Herd Census (Asia/Kolkata timezone)
    - 10:00 AM Feeding compliance checks
    Includes restart persistence and duplicate execution prevention.
    """
    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.executed_jobs: Set[str] = set()
        self.timezone_name = "Asia/Kolkata"
        self.tz = ZoneInfo(self.timezone_name)

    def _sync_already_executed_today(self):
        """Loads jobs executed today from database so server restarts never duplicate runs."""
        db = SessionLocal()
        try:
            today_str = datetime.now(self.tz).strftime("%Y%m%d")
            # Check census records for today
            records = db.query(CensusRecordModel).filter(CensusRecordModel.session_id.like(f"census_{today_str}%")).all()
            for r in records:
                job_key = f"{r.census_type}_{r.scheduled_time}_{today_str}_{r.camera_id}"
                self.executed_jobs.add(job_key)

            # Check feeding records for today
            feeds = db.query(FeedingObservationModel).filter(FeedingObservationModel.session_id.like(f"feed_{today_str}%")).all()
            for f in feeds:
                job_key = f"feed_{today_str}_{f.camera_id}_{f.schedule_id}"
                self.executed_jobs.add(job_key)
            logger.info(f"Loaded {len(self.executed_jobs)} previously executed jobs for today ({today_str}).")
        except Exception as e:
            logger.error(f"Error syncing executed jobs: {e}")
        finally:
            db.close()

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._sync_already_executed_today()
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"Gaushala Scheduler started with timezone: {self.timezone_name}")

    async def stop(self):
        self.is_running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Gaushala Scheduler stopped cleanly.")

    async def _scheduler_loop(self):
        while self.is_running:
            try:
                now_ist = datetime.now(self.tz)
                current_time_str = now_ist.strftime("%H:%M")
                today_str = now_ist.strftime("%Y%m%d")

                db = SessionLocal()
                try:
                    # 1. Evaluate Scheduled Herd Census (05:00 and 17:00 IST by default)
                    settings = db.query(CensusSettingModel).first()
                    morning_target = settings.morning_time if settings else "05:00"
                    evening_target = settings.evening_time if settings else "17:00"
                    primary_camera = settings.primary_camera_id if settings else "cam-01"

                    # Morning Census
                    if current_time_str == morning_target:
                        job_key = f"SCHEDULED_MORNING_{morning_target}_{today_str}_{primary_camera}"
                        if job_key not in self.executed_jobs:
                            self.executed_jobs.add(job_key)
                            logger.info(f"Triggering scheduled 05:00 AM Morning Census for {primary_camera}...")
                            census_engine = get_census_engine()
                            census_engine.run_census(
                                camera_id=primary_camera,
                                census_type="SCHEDULED_MORNING",
                                scheduled_time=morning_target
                            )

                    # Evening Census
                    if current_time_str == evening_target:
                        job_key = f"SCHEDULED_EVENING_{evening_target}_{today_str}_{primary_camera}"
                        if job_key not in self.executed_jobs:
                            self.executed_jobs.add(job_key)
                            logger.info(f"Triggering scheduled 05:00 PM Evening Census for {primary_camera}...")
                            census_engine = get_census_engine()
                            census_engine.run_census(
                                camera_id=primary_camera,
                                census_type="SCHEDULED_EVENING",
                                scheduled_time=evening_target
                            )

                    # 2. Evaluate Scheduled Feeding Compliance (10:00 AM IST)
                    feeding_schedules = db.query(FeedingScheduleModel).filter(FeedingScheduleModel.is_active == True).all()
                    for sched in feeding_schedules:
                        if current_time_str == sched.target_time:
                            feed_job_key = f"feed_{today_str}_{sched.camera_id}_{sched.id}"
                            if feed_job_key not in self.executed_jobs:
                                self.executed_jobs.add(feed_job_key)
                                logger.info(f"Triggering feeding compliance check for {sched.trough_name} ({sched.target_time} IST)...")
                                feeding_engine = get_feeding_engine()
                                feeding_engine.check_feeding_compliance(
                                    schedule_id=sched.id,
                                    camera_id=sched.camera_id,
                                    trough_name=sched.trough_name
                                )
                finally:
                    db.close()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler tick: {e}", exc_info=True)

            # Check every 10 seconds
            await asyncio.sleep(10.0)

_scheduler_instance: Optional[GaushalaScheduler] = None

def get_scheduler() -> GaushalaScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = GaushalaScheduler()
    return _scheduler_instance
