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
from ..core.rate_limit import LOGIN_LIMIT, limiter

router = APIRouter()

@router.post("/api/register")
@limiter.limit(LOGIN_LIMIT)
def register(request: Request, user: models.UserCreate, db: Session = Depends(get_db)):
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
    return {"access_token": access_token, "token_type": "bearer", "user_name": user.full_name, "role": user.role}

@router.post("/api/auth/google", response_model=models.Token)
def login_google(google_data: models.GoogleAuthRequest, db: Session = Depends(get_db)):
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
        return {"access_token": access_token, "token_type": "bearer", "user_name": user.full_name, "role": user.role}

    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
