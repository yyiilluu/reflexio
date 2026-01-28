"""
Database operations for organization/login data.

Supports three backends:
1. S3 storage (in self-host mode) - when SELF_HOST=true and CONFIG_S3_* vars are set
2. Cloud Supabase (via Supabase Python client) - when LOGIN_SUPABASE_URL and LOGIN_SUPABASE_KEY are set
3. SQLite (via SQLAlchemy) - fallback for local development
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from contextlib import contextmanager
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from reflexio.server.db import db_models
from reflexio.server.db.database import SessionLocal
from reflexio.server.db.login_supabase_client import (
    get_login_supabase_client,
    is_using_login_supabase,
)
from reflexio.server.db.s3_org_storage import (
    get_s3_org_storage,
    is_s3_org_storage_ready,
)

logger = logging.getLogger(__name__)

# Check if in self-host mode
SELF_HOST_MODE = os.getenv("SELF_HOST", "false").lower() == "true"


def _is_self_host_s3_mode() -> bool:
    """Check if we're in self-host mode with S3 storage."""
    return SELF_HOST_MODE and is_s3_org_storage_ready()


def _supabase_row_to_organization(row: dict) -> db_models.Organization:
    """
    Convert a Supabase row dict to an Organization model instance.

    Args:
        row: Dictionary from Supabase query result

    Returns:
        Organization model instance (detached, not bound to SQLAlchemy session)
    """
    org = db_models.Organization()
    org.id = row.get("id")
    org.created_at = row.get("created_at")
    org.email = row.get("email")
    org.hashed_password = row.get("hashed_password")
    org.is_active = row.get("is_active", True)
    org.is_verified = row.get("is_verified", False)
    org.interaction_count = row.get("interaction_count", 0)
    org.configuration_json = row.get("configuration_json", "")
    org.api_key = row.get("api_key", "")
    return org


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying get_organization_by_email (attempt {retry_state.attempt_number}): {retry_state.outcome.exception()}"
    ),
    reraise=True,
)
def get_organization_by_email(
    session: Session, email: str
) -> Optional[db_models.Organization]:
    """
    Get an organization by email.

    Args:
        session: SQLAlchemy session (ignored if using Supabase or S3)
        email: Email address

    Returns:
        Organization or None
    """
    # Check S3 storage first (self-host mode)
    if _is_self_host_s3_mode():
        s3_storage = get_s3_org_storage()
        return s3_storage.get_organization_by_email(email)

    client = get_login_supabase_client()
    if client:
        response = (
            client.table("organizations").select("*").eq("email", email).execute()
        )
        if response.data:
            return _supabase_row_to_organization(response.data[0])
        return None
    else:
        if session is None:
            logger.error("No session available and Supabase client not configured")
            return None
        return (
            session.query(db_models.Organization)
            .filter(db_models.Organization.email == email)
            .first()
        )


def get_organizations(
    session: Session, skip: int = 0, limit: int = 100
) -> list[db_models.Organization]:
    """
    Get a list of organizations with pagination.

    Args:
        session: SQLAlchemy session (ignored if using Supabase or S3)
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of Organization objects
    """
    # Check S3 storage first (self-host mode)
    if _is_self_host_s3_mode():
        s3_storage = get_s3_org_storage()
        return s3_storage.get_organizations(skip=skip, limit=limit)

    client = get_login_supabase_client()
    if client:
        response = (
            client.table("organizations")
            .select("*")
            .range(skip, skip + limit - 1)
            .execute()
        )
        return [_supabase_row_to_organization(row) for row in response.data]
    else:
        if session is None:
            logger.error("No session available and Supabase client not configured")
            return []
        return session.query(db_models.Organization).offset(skip).limit(limit).all()


def create_organization(
    session: Session, organization: db_models.Organization
) -> db_models.Organization:
    """
    Create a new organization.

    Args:
        session: SQLAlchemy session (ignored if using Supabase or S3)
        organization: Organization object to create

    Returns:
        Created Organization object with ID populated
    """
    # Check S3 storage first (self-host mode)
    if _is_self_host_s3_mode():
        s3_storage = get_s3_org_storage()
        return s3_storage.create_organization(organization)

    client = get_login_supabase_client()
    if client:
        data = {
            "created_at": organization.created_at
            or int(datetime.now(timezone.utc).timestamp()),
            "email": organization.email,
            "hashed_password": organization.hashed_password,
            "is_active": organization.is_active
            if organization.is_active is not None
            else True,
            "is_verified": organization.is_verified
            if organization.is_verified is not None
            else False,
            "interaction_count": organization.interaction_count
            if organization.interaction_count is not None
            else 0,
            "configuration_json": organization.configuration_json or "",
            "api_key": organization.api_key or "",
        }
        response = client.table("organizations").insert(data).execute()
        if response.data:
            return _supabase_row_to_organization(response.data[0])
        raise Exception("Failed to create organization in Supabase")
    else:
        if session is None:
            raise Exception("No session available and Supabase client not configured")
        session.add(organization)
        session.commit()
        session.refresh(organization)
        return organization


def update_organization(
    session: Session, organization: db_models.Organization
) -> db_models.Organization:
    """
    Update an existing organization.

    Args:
        session: SQLAlchemy session (ignored if using Supabase or S3)
        organization: Organization object with updated fields

    Returns:
        Updated Organization object
    """
    # Check S3 storage first (self-host mode)
    if _is_self_host_s3_mode():
        s3_storage = get_s3_org_storage()
        return s3_storage.update_organization(organization)

    client = get_login_supabase_client()
    if client:
        data = {
            "email": organization.email,
            "hashed_password": organization.hashed_password,
            "is_active": organization.is_active,
            "is_verified": organization.is_verified,
            "interaction_count": organization.interaction_count,
            "configuration_json": organization.configuration_json or "",
            "api_key": organization.api_key or "",
        }
        response = (
            client.table("organizations")
            .update(data)
            .eq("id", organization.id)
            .execute()
        )
        if response.data:
            return _supabase_row_to_organization(response.data[0])
        raise Exception("Failed to update organization in Supabase")
    else:
        if session is None:
            raise Exception("No session available and Supabase client not configured")
        session.commit()
        session.refresh(organization)
        return organization


# Dependency
def get_db_session():
    """
    FastAPI dependency that yields a database session.

    For Supabase mode, SessionLocal is None, so we yield None.
    The actual database operations check for Supabase client first.
    """
    if SessionLocal is None:
        # Supabase mode - yield None, operations will use Supabase client
        yield None
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def add_db_model(session: Session, db_model: db_models.Base) -> db_models.Base:
    """
    Add a generic database model (SQLAlchemy only, for backward compatibility).

    Args:
        session: SQLAlchemy session
        db_model: Model to add

    Returns:
        Added model
    """
    if session is None:
        raise Exception("Cannot add model: no SQLAlchemy session available")
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return db_model


@contextmanager
def db_session_context():
    """
    Context manager for database sessions.

    Yields a SQLAlchemy session that auto-closes on exit, or None if using Supabase.
    """
    if SessionLocal is None:
        # Supabase mode - yield None
        yield None
    else:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()


if __name__ == "__main__":
    if is_using_login_supabase():
        print("Using cloud Supabase for login database")
        # Test with Supabase
        with db_session_context() as s:
            orgs = get_organizations(s, limit=5)
            for org in orgs:
                print(f"  - {org.email}")
    else:
        print("Using local SQLite for login database")
        if SessionLocal is not None:
            with SessionLocal() as s:
                org = s.query(db_models.Organization).first()
                if org:
                    print(f"First org: {org.email}")
        else:
            print("No SessionLocal available")
