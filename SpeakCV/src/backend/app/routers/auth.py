# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

import os
import secrets
import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import models
from ..database import sql_models
from ..database.database import get_db
from ..auth import security
from ..auth.dependencies import get_authenticated_user
from ..core.rate_limit import LOGIN_LIMIT, limiter
from ..schemas.companies import PasswordChange

router = APIRouter()

@router.post("/api/register")
@limiter.limit(LOGIN_LIMIT)
def register(request: Request, user: models.UserCreate, db: Session = Depends(get_db)):
    if len(user.password) < security.MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=422, detail=f"Password must be at least {security.MIN_PASSWORD_LENGTH} characters")
    email = user.email.strip().lower()
    db_user = db.query(sql_models.User).filter(func.lower(sql_models.User.email) == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already in use")
    
    hashed_pw = security.get_password_hash(user.password)
    new_user = sql_models.User(email=email, full_name=user.full_name, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    return {"message": "Registration successful"}

@router.post("/api/login", response_model=models.Token)
@limiter.limit(LOGIN_LIMIT)
def login(request: Request, user_data: models.UserLogin, db: Session = Depends(get_db)):
    email = user_data.email.strip().lower()
    user = db.query(sql_models.User).filter(func.lower(sql_models.User.email) == email).first()
    if not user or not security.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = security.create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_name": user.full_name,
        "role": user.role,
        "must_change_password": user.must_change_password,
    }

@router.post("/api/me/password")
@limiter.limit(LOGIN_LIMIT)
def change_password(
    request: Request,
    body: PasswordChange,
    user: sql_models.User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    if not security.verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    # Otherwise a temporary password someone else has seen would pass as the "new" one.
    if body.new_password == body.current_password:
        raise HTTPException(status_code=422, detail="The new password must differ from the current one")
    user.hashed_password = security.get_password_hash(body.new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "Password changed"}

@router.post("/api/auth/google", response_model=models.Token)
@limiter.limit(LOGIN_LIMIT)
def login_google(request: Request, google_data: models.GoogleAuthRequest, db: Session = Depends(get_db)):
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(status_code=503, detail="Google login is not configured")
    try:
        tokeninfo = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": google_data.token},
            timeout=10,
        )
        if not tokeninfo.ok or tokeninfo.json().get("aud") != client_id:
            raise ValueError("Token was not issued for this application")

        # Verify the access token by fetching user profile from Google
        response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {google_data.token}"},
            timeout=10,
        )
        
        if not response.ok:
            raise ValueError("Failed to fetch user info with provided token")
            
        idinfo = response.json()

        email = (idinfo.get("email") or "").strip().lower()
        full_name = idinfo.get("name") or "Google User"

        if not email:
            raise HTTPException(status_code=400, detail="Google token does not contain email")

        # Check if user exists
        user = db.query(sql_models.User).filter(func.lower(sql_models.User.email) == email).first()

        if not user:
            # Create a new user with a random unguessable password since they use Google
            random_pw = secrets.token_urlsafe(32)
            hashed_pw = security.get_password_hash(random_pw)
            
            user = sql_models.User(
                email=email,
                full_name=full_name,
                hashed_password=hashed_pw,
                role="user"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        access_token = security.create_access_token(data={"sub": user.email})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_name": user.full_name,
            "role": user.role,
            "must_change_password": user.must_change_password,
        }

    # Checked first: a bad JSON body from Google is both a RequestException and a ValueError.
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Could not reach Google. Please try again.")
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
