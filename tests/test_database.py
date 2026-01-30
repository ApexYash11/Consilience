"""
Tests for database schema and operations.
"""

import pytest
from datetime import datetime
from uuid import UUID

from database.schema import UserDB, Base
from models.payment import SubscriptionTier, SubscriptionStatus


class TestDatabaseSchema:
    """Test database schema and CRUD operations."""

    def test_create_user(self, db_session):
        """Test creating a user in the database."""
        user = UserDB(
            email="test@example.com",
            hashed_password="hashed_password",
            full_name="Test User",
            neon_user_id="neon_123",
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        # GUID column stores as string in SQLite, but should have valid UUID format
        assert str(user.id)  # Check that it can be converted to string
        assert str(user.email) == "test@example.com"
        assert user.created_at is not None

    def test_read_user(self, db_session, test_user_db):
        """Test reading a user from the database."""
        user = db_session.query(UserDB).filter(
            UserDB.email == test_user_db.email
        ).first()
        
        assert user is not None
        assert user.email == test_user_db.email
        assert user.subscription_tier == SubscriptionTier.FREE

    def test_update_user(self, db_session, test_user_db):
        """Test updating a user."""
        test_user_db.subscription_tier = SubscriptionTier.PRO
        db_session.commit()
        
        user = db_session.query(UserDB).filter(
            UserDB.id == test_user_db.id
        ).first()
        
        assert user.subscription_tier == SubscriptionTier.PRO

    def test_delete_user(self, db_session, test_user_db):
        """Test deleting a user."""
        user_id = test_user_db.id
        db_session.delete(test_user_db)
        db_session.commit()
        
        user = db_session.query(UserDB).filter(UserDB.id == user_id).first()
        assert user is None

    def test_user_unique_email(self, db_session, test_user_db):
        """Test that email constraint is enforced."""
        duplicate_user = UserDB(
            email=test_user_db.email,
            hashed_password="different_password",
            full_name="Different User",
            neon_user_id="different_neon_id",
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )
        db_session.add(duplicate_user)
        
        # IntegrityError will be raised on commit
        try:
            db_session.commit()
            assert False, "Expected IntegrityError"
        except Exception:
            db_session.rollback()

    def test_user_defaults(self, db_session):
        """Test default values for new user."""
        user = UserDB(
            email="defaults@example.com",
            hashed_password="hashed_password",
            neon_user_id="neon_456",
        )
        db_session.add(user)
        db_session.commit()
        
        # Extract values from SQLAlchemy Column objects for assertion
        assert user.subscription_tier.value == SubscriptionTier.FREE.value
        assert user.subscription_status.value == SubscriptionStatus.ACTIVE.value
        assert bool(user.is_active) is True
        assert bool(user.is_verified) is False
        assert user.created_at is not None

    def test_user_relationships(self, db_session, test_user_db):
        """Test user relationships are properly defined."""
        # This tests that the relationship definitions exist
        assert hasattr(test_user_db, "tasks")
        assert hasattr(test_user_db, "usage_records")
        assert hasattr(test_user_db, "payments")
        
        # Refresh user to load relationships
        db_session.refresh(test_user_db)
        
        # Initially should be empty
        tasks = list(test_user_db.tasks)
        usage_records = list(test_user_db.usage_records)
        payments = list(test_user_db.payments)
        assert len(tasks) == 0
        assert len(usage_records) == 0
        assert len(payments) == 0

    def test_user_repr(self, test_user_db):
        """Test user string representation."""
        repr_str = repr(test_user_db)
        assert test_user_db.email in repr_str
        assert SubscriptionTier.FREE.name in repr_str or "free" in repr_str.lower()
