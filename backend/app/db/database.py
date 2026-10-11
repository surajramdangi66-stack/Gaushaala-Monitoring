import os
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.config import BASE_DIR, DEFAULT_USERS
from backend.app.db.models import (
    Base,
    UserModel,
    CensusSettingModel,
    FeedingScheduleModel
)

logger = logging.getLogger("gaushala.db")

# Default to SQLite local database file; support PostgreSQL via DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    db_path = BASE_DIR / "data" / "gaushala.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{db_path.resolve()}"

# Engine options
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """FastAPI dependency for obtaining a thread-safe database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes schema and seeds baseline operational configuration."""
    logger.info(f"Initializing database at: {DATABASE_URL}")
    Base.metadata.create_all(bind=engine)

    # Seed initial users, census settings, and feeding schedules if empty
    db = SessionLocal()
    try:
        # 1. Seed users
        if db.query(UserModel).count() == 0:
            logger.info("Seeding initial default users from config...")
            for user_key, udata in DEFAULT_USERS.items():
                db.add(UserModel(
                    username=udata["username"],
                    full_name=udata["full_name"],
                    password_hash=udata["password_hash"],
                    role=udata["role"]
                ))
            db.commit()

        # 2. Seed default Census Settings
        if db.query(CensusSettingModel).count() == 0:
            logger.info("Seeding default census settings (05:00 and 17:00 IST)...")
            db.add(CensusSettingModel(
                primary_camera_id="cam-01",
                morning_time="05:00",
                evening_time="17:00",
                capture_window_seconds=5.0,
                min_stable_frames=3,
                timezone="Asia/Kolkata"
            ))
            db.commit()

        # 3. Seed default Feeding Schedule (10:00 AM IST)
        if db.query(FeedingScheduleModel).count() == 0:
            logger.info("Seeding default feeding schedule (10:00 AM IST)...")
            db.add(FeedingScheduleModel(
                camera_id="cam-01",
                trough_name="Feeder Trough A",
                target_time="10:00",
                observation_window_seconds=5.0,
                is_active=True
            ))
            db.commit()

        logger.info("Database schema initialized and verified successfully.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        db.rollback()
    finally:
        db.close()
