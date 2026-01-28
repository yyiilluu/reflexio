from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from cachetools import TTLCache
import threading
from fastapi import FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from reflexio.server.db import db_models
from reflexio.server.db.db_operations import (
    get_organization_by_email,
    create_organization,
)

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 36500  # 100 years
VERIFICATION_TOKEN_EXPIRE_DAYS = 7
VERIFICATION_TOKEN_TYPE = "email_verification"
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 1
PASSWORD_RESET_TOKEN_TYPE = "password_reset"

# Organization cache configuration
# TTL of 300 seconds (5 minutes) - balances performance vs security
# maxsize of 1000 orgs should be sufficient for most deployments
ORG_CACHE_TTL_SECONDS = 300
ORG_CACHE_MAX_SIZE = 1000
_org_cache: TTLCache = TTLCache(maxsize=ORG_CACHE_MAX_SIZE, ttl=ORG_CACHE_TTL_SECONDS)
_org_cache_lock = threading.Lock()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
app = FastAPI()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Convert stored hash back to bytes
        hashed_bytes = hashed_password.encode("utf-8")
        # Verify password
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_bytes)
    except Exception as e:
        print(f"Error in password verification: {e}")
        return False


def get_password_hash(password: str) -> str:
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    # Store hash as string
    return hashed.decode("utf-8")


def authenticate_organization(
    org_email: str, password: str, session: Session
) -> Optional[db_models.Organization]:
    user = get_organization_by_email(session=session, email=org_email)
    if not user:
        print(f"User not found: {org_email}")
        return None
    if not verify_password(password, str(user.hashed_password)):
        print(f"Password verification failed for user: {org_email}")
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def _get_cached_org(
    org_email: str, session: Session
) -> Optional[db_models.Organization]:
    """Get organization from cache or database.

    Args:
        org_email (str): Organization email to look up
        session (Session): Database session for fallback lookup

    Returns:
        Optional[db_models.Organization]: Cached or freshly fetched organization
    """
    with _org_cache_lock:
        # Check cache first
        cached = _org_cache.get(org_email)
        if cached is not None:
            return cached

    # Cache miss - fetch from database
    org = get_organization_by_email(session=session, email=org_email)
    if org is not None:
        with _org_cache_lock:
            _org_cache[org_email] = org

    return org


def invalidate_org_cache(org_email: str) -> None:
    """Invalidate cached organization entry.

    Call this when an organization is deactivated, verified status changes,
    or any security-sensitive update occurs.

    Args:
        org_email (str): Organization email to invalidate from cache
    """
    with _org_cache_lock:
        _org_cache.pop(org_email, None)


def clear_org_cache() -> None:
    """Clear the entire organization cache.

    Useful for testing or when bulk security updates occur.
    """
    with _org_cache_lock:
        _org_cache.clear()


def get_current_org(token: str, session: Session) -> db_models.Organization:
    """Get the current organization from a JWT token.

    Uses TTL-based caching to reduce database lookups.
    Cache entries expire after ORG_CACHE_TTL_SECONDS (default: 5 minutes).

    Args:
        token (str): JWT access token
        session (Session): Database session

    Returns:
        db_models.Organization: The authenticated organization

    Raises:
        HTTPException: If token is invalid or organization not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        org_email = payload.get("sub")
        if org_email is None:
            raise credentials_exception
    except JWTError as e:
        raise credentials_exception from e

    org = _get_cached_org(org_email=org_email, session=session)
    if org is None:
        raise credentials_exception
    return org


def get_current_active_org(
    token: str,
    session: Session,
) -> db_models.Organization:
    current_org = get_current_org(token=token, session=session)
    if current_org.is_active is False:
        raise HTTPException(status_code=400, detail="Account is inactive")
    if current_org.is_verified is False:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email address. Check your inbox for the verification link.",
        )
    return current_org


def register_organization(
    org_email: str,
    password: str,
    api_key: str,
    session: Session,
) -> db_models.Organization:
    org = authenticate_organization(
        org_email=org_email, password=password, session=session
    )
    if org:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="user email has already been registered",
        )

    hashed_password = get_password_hash(password)
    org_model = db_models.Organization(
        email=org_email, hashed_password=hashed_password, api_key=api_key
    )
    org = create_organization(organization=org_model, session=session)
    return org


def create_verification_token(email: str) -> str:
    """
    Create a JWT token for email verification.

    Args:
        email (str): The email address to verify

    Returns:
        str: JWT verification token
    """
    expire = datetime.now(timezone.utc) + timedelta(days=VERIFICATION_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": email,
        "type": VERIFICATION_TOKEN_TYPE,
        "exp": expire,
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_email_token(token: str) -> Optional[str]:
    """
    Verify an email verification token and return the email address.

    Args:
        token (str): The JWT verification token

    Returns:
        Optional[str]: The email address if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")

        if email is None or token_type != VERIFICATION_TOKEN_TYPE:
            return None

        return email
    except JWTError:
        return None


def create_password_reset_token(email: str) -> str:
    """
    Create a JWT token for password reset.

    Args:
        email (str): The email address for password reset

    Returns:
        str: JWT password reset token
    """
    expire = datetime.now(timezone.utc) + timedelta(
        hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )
    to_encode = {
        "sub": email,
        "type": PASSWORD_RESET_TOKEN_TYPE,
        "exp": expire,
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token and return the email address.

    Args:
        token (str): The JWT password reset token

    Returns:
        Optional[str]: The email address if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")

        if email is None or token_type != PASSWORD_RESET_TOKEN_TYPE:
            return None

        return email
    except JWTError:
        return None
