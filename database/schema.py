"""
Database models and schema for Consilience platform.
Uses SQLAlchemy ORM with support for SQLite (dev) and PostgreSQL (prod).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.types import TypeDecorator, CHAR

from models.payment import SubscriptionTier, SubscriptionStatus
from models.research import TaskStatus, ResearchDepth


# Base class for all models
Base = declarative_base()


# Custom UUID type that works with both SQLite and PostgreSQL
class GUID(TypeDecorator):
    """Platform-independent GUID type."""
    impl = CHAR
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID())
        else:
            return dialect.type_descriptor(CHAR(36))
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if isinstance(value, str):
                return value
            return str(value)
    
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, str):
            return value
        return str(value)


# ============================================================================
# USER TABLES
# ============================================================================

class UserDB(Base):
    """User account database model."""
    __tablename__ = "users"
    
    id = Column(GUID, primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    
    # OAuth integration
    neon_user_id = Column(String(255), unique=True, index=True)
    
    # Subscription
    subscription_tier = Column(
        Enum(SubscriptionTier),
        default=SubscriptionTier.FREE,
        nullable=False
    )
    subscription_status = Column(
        Enum(SubscriptionStatus),
        default=SubscriptionStatus.ACTIVE,
        nullable=False
    )
    stripe_customer_id = Column(String(255), unique=True, index=True)
    stripe_subscription_id = Column(String(255), unique=True, index=True)
    
    # Quotas
    monthly_standard_quota = Column(Integer, default=5)
    monthly_deep_quota = Column(Integer, default=0)
    
    # Usage tracking (reset monthly)
    standard_papers_this_month = Column(Integer, default=0)
    deep_papers_this_month = Column(Integer, default=0)
    total_tokens_this_month = Column(Integer, default=0)
    total_cost_this_month = Column(Numeric(10, 2), default=0.00)
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    tasks = relationship("ResearchTaskDB", back_populates="user")
    usage_records = relationship("UsageRecordDB", back_populates="user")
    payments = relationship("PaymentDB", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.email} ({self.subscription_tier})>"


class UsageRecordDB(Base):
    """Monthly usage records for billing and analytics."""
    __tablename__ = "usage_records"
    
    id = Column(GUID, primary_key=True, default=uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False, index=True)
    
    # Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Usage counts
    standard_papers = Column(Integer, default=0)
    deep_papers = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Numeric(10, 2), default=0.00)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("UserDB", back_populates="usage_records")
    
    def __repr__(self):
        return f"<UsageRecord {self.user_id} {self.period_start}>"


# ============================================================================
# RESEARCH TASK TABLES
# ============================================================================

class ResearchTaskDB(Base):
    """Research task database model."""
    __tablename__ = "research_tasks"
    
    id = Column(GUID, primary_key=True, default=uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False, index=True)
    
    # Task details
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    
    # Configuration
    research_depth = Column(Enum(ResearchDepth), nullable=False)
    config_json = Column(JSON)  # Stores full ResearchConfig as JSON
    
    # Status
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Cost tracking
    estimated_cost_usd = Column(Numeric(10, 4))
    actual_cost_usd = Column(Numeric(10, 4))
    tokens_used = Column(Integer)
    
    # Results
    output_path = Column(String(1000))
    error_message = Column(Text)
    metadata_json = Column(JSON)
    final_state_json = Column(JSON)
    
    # Relationships
    user = relationship("UserDB", back_populates="tasks")
    agent_actions = relationship("AgentActionDB", back_populates="task")
    
    def __repr__(self):
        return f"<ResearchTask {self.id} ({self.status})>"


class AgentActionDB(Base):
    """Individual agent action log."""
    __tablename__ = "agent_actions"
    
    id = Column(GUID, primary_key=True, default=uuid4)
    task_id = Column(GUID, ForeignKey("research_tasks.id"), nullable=False, index=True)
    
    # Agent details
    agent_id = Column(GUID)
    agent_name = Column(String(100))
    agent_type = Column(String(50))
    action = Column(String(100))
    
    # Data
    input_data_json = Column(JSON)
    output_data_json = Column(JSON)
    
    # Cost
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Numeric(10, 4), default=0.0000)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Error handling
    error = Column(Text)
    
    # Relationships
    task = relationship("ResearchTaskDB", back_populates="agent_actions")
    
    def __repr__(self):
        return f"<AgentAction {self.agent_name} {self.action}>"


# ============================================================================
# PAYMENT TABLES
# ============================================================================

class PaymentDB(Base):
    """Payment transaction records."""
    __tablename__ = "payments"
    
    id = Column(GUID, primary_key=True, default=uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False, index=True)
    
    # Stripe details
    stripe_payment_intent_id = Column(String(255), unique=True, index=True)
    stripe_session_id = Column(String(255), unique=True)
    
    # Amount
    amount_usd = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    
    # Status
    status = Column(String(50), nullable=False)  # succeeded, failed, pending, etc.
    
    # Plan
    subscription_tier = Column(Enum(SubscriptionTier))
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Metadata
    metadata_json = Column(JSON)
    
    # Relationships
    user = relationship("UserDB", back_populates="payments")
    
    def __repr__(self):
        return f"<Payment {self.id} {self.amount_usd} {self.status}>"


class StripeWebhookEventDB(Base):
    """Stripe webhook event log."""
    __tablename__ = "stripe_webhook_events"
    
    id = Column(GUID, primary_key=True, default=uuid4)
    
    # Stripe event details
    stripe_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    
    # Data
    data_json = Column(JSON)
    
    # Processing
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)
    error = Column(Text)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<StripeWebhookEvent {self.event_type} {self.processed}>"


# ============================================================================
# AUDIT LOG TABLE
# ============================================================================

class AuditLogDB(Base):
    """Comprehensive audit log."""
    __tablename__ = "audit_logs"
    
    id = Column(GUID, primary_key=True, default=uuid4)
    
    # Event details
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor = Column(String(255), nullable=False)  # user_id, agent_name, or "system"
    action = Column(String(100), nullable=False, index=True)
    
    # Resource
    resource_type = Column(String(50))  # "task", "user", "payment"
    resource_id = Column(String(255), index=True)
    
    # Details
    details_json = Column(JSON)
    
    # Network
    ip_address = Column(String(45))  # Supports IPv6
    
    def __repr__(self):
        return f"<AuditLog {self.timestamp} {self.actor} {self.action}>"


# ============================================================================
# DATABASE SETUP
# ============================================================================

def create_database_engine(database_url: str):
    """
    Create database engine.
    
    Args:
        database_url: SQLAlchemy database URL
            - SQLite: "sqlite:///./consilience.db"
            - PostgreSQL: "postgresql://user:pass@localhost/dbname"
    """
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,  # Verify connections before using
    )
    return engine


def init_database(database_url: str):
    """Initialize database with all tables."""
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def get_session_maker(database_url: str):
    """Get SQLAlchemy session maker."""
    engine = create_database_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Development: SQLite
    engine = init_database("sqlite:///./consilience.db")
    print("Database initialized successfully!")
    
    # Production would use:
    # engine = init_database("postgresql://user:pass@localhost/consilience")
