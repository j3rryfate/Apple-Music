# ============================================
# FILE: bot/__init__.py
# ============================================
"""Telegram Bot for Apple Music Downloader"""
__version__ = "1.0.0"


# ============================================
# FILE: bot/config.py
# ============================================
import os
from pathlib import Path

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
DUMP_CHANNEL_ID = int(os.getenv("DUMP_CHANNEL_ID", "0"))

# Apple Music Configuration
COOKIES_PATH = Path(os.getenv("COOKIES_PATH", "./cookies.txt"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "./downloads"))
TEMP_PATH = Path(os.getenv("TEMP_PATH", "./temp"))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")

# Download Settings
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "2000"))
CONCURRENT_DOWNLOADS = int(os.getenv("CONCURRENT_DOWNLOADS", "3"))

# Messages
WELCOME_MESSAGE = """🎵 **Apple Music Downloader Bot**

ကြိုဆိုပါတယ်! ဒီ bot ကို အသုံးပြုဖို့ admin ရဲ့ အတည်ပြုချက် လိုအပ်ပါတယ်။

သင့် request ကို ပေးပို့ပြီးပါပြီ။ Admin approve လုပ်ပြီးမှ bot ကို အသုံးပြုနိုင်မှာ ဖြစ်ပါတယ်။"""

APPROVED_MESSAGE = """✅ **Access Granted!**

သင့်အား bot အသုံးပြုခွင့် ပေးလိုက်ပါပြီ။

**အသုံးပြုနည်း:**
• Apple Music URL တစ်ခုကို ပို့ပါ
• Download format ကို ရွေးပါ
• စောင့်ပါ!

**Supported URLs:**
- Songs
- Albums
- Playlists
- Music Videos"""

REJECTED_MESSAGE = "❌ သင့်ရဲ့ request ကို ပယ်ချခံရပါတယ်။"
UNAUTHORIZED_MESSAGE = "⛔ သင့်မှာ bot အသုံးပြုခွင့် မရှိပါ။ /start နှိပ်ပြီး access တောင်းပါ။"
PROCESSING_MESSAGE = "⏳ Processing your request..."

# Create directories
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
TEMP_PATH.mkdir(parents=True, exist_ok=True)


# ============================================
# FILE: bot/database/__init__.py
# ============================================
"""Database package"""


# ============================================
# FILE: bot/database/models.py
# ============================================
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    status = Column(String(20), default="pending")
    requested_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)
    approved_by = Column(Integer)
    
    def __repr__(self):
        return f"<User {self.user_id} - {self.status}>"

class Download(Base):
    __tablename__ = "downloads"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    url = Column(Text, nullable=False)
    download_type = Column(String(50))
    format_type = Column(String(20))
    status = Column(String(20), default="pending")
    file_paths = Column(Text)
    dump_message_ids = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    def __repr__(self):
        return f"<Download {self.id} - {self.status}>"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================
# FILE: bot/database/db.py
# ============================================
from datetime import datetime
from sqlalchemy.orm import Session
from bot.database.models import User, Download

class UserDB:
    @staticmethod
    def get_user(db: Session, user_id: int):
        return db.query(User).filter(User.user_id == user_id).first()
    
    @staticmethod
    def create_user(db: Session, user_id: int, username: str = None, 
                   first_name: str = None, last_name: str = None):
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            status="pending"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def update_user_status(db: Session, user_id: int, status: str, approved_by: int = None):
        user = UserDB.get_user(db, user_id)
        if user:
            user.status = status
            if status == "approved":
                user.approved_at = datetime.utcnow()
                user.approved_by = approved_by
            db.commit()
            db.refresh(user)
        return user
    
    @staticmethod
    def get_pending_users(db: Session):
        return db.query(User).filter(User.status == "pending").all()
    
    @staticmethod
    def get_all_users(db: Session, status: str = None):
        query = db.query(User)
        if status:
            query = query.filter(User.status == status)
        return query.all()
    
    @staticmethod
    def is_user_approved(db: Session, user_id: int):
        user = UserDB.get_user(db, user_id)
        return user and user.status == "approved"
    
    @staticmethod
    def get_user_downloads(db: Session, user_id: int, limit: int = 10):
        return db.query(Download).filter(
            Download.user_id == user_id
        ).order_by(Download.started_at.desc()).limit(limit).all()

class DownloadDB:
    @staticmethod
    def create_download(db: Session, user_id: int, url: str, 
                       download_type: str, format_type: str):
        download = Download(
            user_id=user_id,
            url=url,
            download_type=download_type,
            format_type=format_type,
            status="pending"
        )
        db.add(download)
        db.commit()
        db.refresh(download)
        return download
    
    @staticmethod
    def update_download_status(db: Session, download_id: int, 
                              status: str, error_message: str = None):
        download = db.query(Download).filter(Download.id == download_id).first()
        if download:
            download.status = status
            if error_message:
                download.error_message = error_message
            if status == "completed":
                download.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(download)
        return download
    
    @staticmethod
    def update_download_files(db: Session, download_id: int, 
                            file_paths: str, dump_message_ids: str = None):
        download = db.query(Download).filter(Download.id == download_id).first()
        if download:
            download.file_paths = file_paths
            if dump_message_ids:
                download.dump_message_ids = dump_message_ids
            db.commit()
            db.refresh(download)
        return download
    
    @staticmethod
    def get_download_stats(db: Session):
        total = db.query(Download).count()
        completed = db.query(Download).filter(Download.status == "completed").count()
        failed = db.query(Download).filter(Download.status == "failed").count()
        return {"total": total, "completed": completed, "failed": failed}


# ============================================
# FILE: bot/handlers/__init__.py
# ============================================
"""Handlers package"""


# ============================================
# FILE: bot/utils/__init__.py
# ============================================
"""Utils package"""
