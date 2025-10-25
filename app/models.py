"""Database models for email tracking and follow-ups."""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class EmailFollowup(Base):
    """Track emails that need AI follow-up during operating hours."""

    __tablename__ = "email_followups"

    gmail_message_id = Column(String, primary_key=True)  # Gmail message ID
    customer_email = Column(String, nullable=False)
    customer_name = Column(String)
    subject = Column(String)
    body = Column(Text)
    label = Column(String)  # Support, Tracking, Return/Refund, etc.

    needs_followup = Column(Boolean, default=False)  # True if sent template during quiet hours
    followup_sent = Column(Boolean, default=False)   # True after AI follow-up sent

    received_at = Column(DateTime, default=datetime.utcnow)
    template_sent_at = Column(DateTime)  # When template was sent
    followup_sent_at = Column(DateTime)  # When AI follow-up was sent

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EmailFollowup {self.gmail_message_id} - {self.customer_email}>"


def init_followup_db(database_url: str):
    """Initialize the follow-up tracking database."""
    # Convert async URL to sync for table creation
    sync_url = database_url.replace("+aiosqlite", "")

    engine = create_engine(sync_url, echo=False)
    Base.metadata.create_all(engine)
    print("✅ Follow-up tracking database initialized")

    return engine


def get_followup_session(database_url: str):
    """Get a database session for follow-up tracking."""
    sync_url = database_url.replace("+aiosqlite", "")
    engine = create_engine(sync_url, echo=False)
    Session = sessionmaker(bind=engine)
    return Session()
