"""
Simple authentication module for password protection.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os
from dotenv import load_dotenv

load_dotenv()

security = HTTPBasic()

# Get password from environment variable or use default
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme123")  # Change this!

def verify_password(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verify HTTP Basic auth credentials.
    Username can be anything, password must match ADMIN_PASSWORD.
    """
    if credentials.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
