# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import uuid
from datetime import datetime
from io import BytesIO
import json
from docx import Document

from ..ai_service import call_ai_chat

from .. import models
from ..database import sql_models
from ..database.database import get_db
from .profile import get_current_user
from ..auth import security

router = APIRouter()

@router.get("/api/admin/dashboard")
async def get_admin_dashboard(current_user: sql_models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    from sqlalchemy import func, cast, Date
    from datetime import datetime, timedelta

    total_users = db.query(sql_models.User).count()
    total_interviews = db.query(sql_models.InterviewHistory).count()
    estimated_total_tokens = total_interviews * 2500
    pro_users = db.query(sql_models.User).filter(sql_models.User.plan == "pro").count()

    # Pending questions count
    pending_questions = 0
    try:
        pending_questions = db.query(sql_models.CompanyQuestion).filter(
            sql_models.CompanyQuestion.is_approved == False
        ).count()
    except Exception:
        pass

    # Interviews per day (last 7 days)
    interviews_by_day = []
    for i in range(6, -1, -1):
        day = datetime.now().date() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        count = db.query(sql_models.InterviewHistory).filter(
            sql_models.InterviewHistory.created_at >= day_start,
            sql_models.InterviewHistory.created_at <= day_end
        ).count()
        interviews_by_day.append({
            "date": day.strftime("%d/%m"),
            "count": count
        })

    # Top 5 users by interview count
    top_users_query = db.query(
        sql_models.User.id,
        sql_models.User.full_name,
        sql_models.User.email,
        sql_models.User.plan,
        func.count(sql_models.InterviewHistory.id).label("interview_count")
    ).join(
        sql_models.InterviewHistory,
        sql_models.InterviewHistory.user_id == sql_models.User.id
    ).group_by(
        sql_models.User.id
    ).order_by(
        func.count(sql_models.InterviewHistory.id).desc()
    ).limit(5).all()

    top_users = [
        {
            "id": u[0], "full_name": u[1], "email": u[2],
            "plan": u[3], "interview_count": u[4]
        }
        for u in top_users_query
    ]

    # 5 most recent interviews
    recent_interviews_query = db.query(
        sql_models.InterviewHistory,
        sql_models.User.full_name,
        sql_models.User.email
    ).join(
        sql_models.User,
        sql_models.User.id == sql_models.InterviewHistory.user_id
    ).order_by(
        sql_models.InterviewHistory.created_at.desc()
    ).limit(5).all()

    recent_interviews = [
        {
            "id": h.id, "user_name": name, "user_email": email,
            "position": h.position, "score": h.score, "title": h.title,
            "interview_type": h.interview_type,
            "created_at": h.created_at.isoformat() if h.created_at else None
        }
        for h, name, email in recent_interviews_query
    ]

    # User list (existing)
    users = db.query(sql_models.User).order_by(sql_models.User.id.desc()).all()
    user_list = []
    for u in users:
        user_interview_count = db.query(sql_models.InterviewHistory).filter(sql_models.InterviewHistory.user_id == u.id).count()
        user_list.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "plan": u.plan,
            "interview_count": user_interview_count,
            "tokens_used": user_interview_count * 2500,
            "credits": u.credits 
        })

    return {
        "stats": {
            "total_users": total_users,
            "total_interviews": total_interviews,
            "total_tokens": estimated_total_tokens,
            "pro_users": pro_users,
            "pending_questions": pending_questions,
            "interviews_by_day": interviews_by_day,
            "top_users": top_users,
            "recent_interviews": recent_interviews,
        },
        "users": user_list
    }

@router.get("/api/admin/config")
async def get_system_config(
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    prompt_config = db.query(sql_models.SystemConfig).filter_by(setting_key="system_prompt").first()
    temp_config = db.query(sql_models.SystemConfig).filter_by(setting_key="temperature").first()
    brain_toggle_config = db.query(sql_models.SystemConfig).filter_by(setting_key="ai_enable_brain_retrieval").first()

    enrichment_toggle_config = db.query(sql_models.SystemConfig).filter_by(setting_key="ai_brain_ingestion_enrichment_enabled").first()

    return {
        "system_prompt": prompt_config.setting_value if prompt_config else "Bạn là một Giám đốc Nhân sự (HR) chuyên nghiệp...",
        "temperature": float(temp_config.setting_value) if temp_config else 0.7,
        "ai_enable_brain_retrieval": (brain_toggle_config.setting_value.lower() == "true") if brain_toggle_config else True,
        "ai_brain_ingestion_enrichment_enabled": (enrichment_toggle_config.setting_value.lower() == "true") if enrichment_toggle_config else True,
    }

@router.put("/api/admin/config")
async def update_system_config(
    request: models.SystemConfigUpdate,
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    prompt_config = db.query(sql_models.SystemConfig).filter_by(setting_key="system_prompt").first()
    if not prompt_config:
        prompt_config = sql_models.SystemConfig(setting_key="system_prompt", setting_value=request.system_prompt)
        db.add(prompt_config)
    else:
        prompt_config.setting_value = request.system_prompt

    temp_config = db.query(sql_models.SystemConfig).filter_by(setting_key="temperature").first()
    if not temp_config:
        temp_config = sql_models.SystemConfig(setting_key="temperature", setting_value=str(request.temperature))
        db.add(temp_config)
    else:
        temp_config.setting_value = str(request.temperature)

    if request.ai_enable_brain_retrieval is not None:
        brain_toggle_config = db.query(sql_models.SystemConfig).filter_by(setting_key="ai_enable_brain_retrieval").first()
        if not brain_toggle_config:
            brain_toggle_config = sql_models.SystemConfig(
                setting_key="ai_enable_brain_retrieval",
                setting_value=str(request.ai_enable_brain_retrieval),
            )
            db.add(brain_toggle_config)
        else:
            brain_toggle_config.setting_value = str(request.ai_enable_brain_retrieval)

    if hasattr(request, "ai_brain_ingestion_enrichment_enabled") and request.ai_brain_ingestion_enrichment_enabled is not None:
        enrichment_toggle_config = db.query(sql_models.SystemConfig).filter_by(setting_key="ai_brain_ingestion_enrichment_enabled").first()
        if not enrichment_toggle_config:
            enrichment_toggle_config = sql_models.SystemConfig(
                setting_key="ai_brain_ingestion_enrichment_enabled",
                setting_value=str(request.ai_brain_ingestion_enrichment_enabled),
            )
            db.add(enrichment_toggle_config)
        else:
            enrichment_toggle_config.setting_value = str(request.ai_brain_ingestion_enrichment_enabled)

    db.commit()
    return {"message": "Config updated successfully!"}

@router.get("/api/admin/interviews")
async def get_all_interviews(
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    interviews = db.query(
        sql_models.InterviewHistory, 
        sql_models.User.email, 
        sql_models.User.full_name
    ).join(
        sql_models.User, sql_models.User.id == sql_models.InterviewHistory.user_id
    ).order_by(
        sql_models.InterviewHistory.created_at.desc()
    ).all()
    
    result = []
    for hist, email, full_name in interviews:
        result.append({
            "id": hist.id,
            "user_email": email,
            "user_name": full_name,
            "position": hist.position,
            "score": hist.score,
            "title": hist.title,
            "details": hist.details,
            "created_at": hist.created_at
        })
        
    return {"interviews": result}

# Get all JD templates
@router.get("/api/templates")
async def get_jd_templates(db: Session = Depends(get_db)):
    templates = db.query(sql_models.JDTemplate).order_by(sql_models.JDTemplate.created_at.desc()).all()
    return {"templates": templates}

# Create a new JD template
@router.post("/api/admin/templates")
async def create_jd_template(
    request: models.JDTemplateRequest, 
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    new_template = sql_models.JDTemplate(
        title=request.title,
        description=request.description
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    return {"message": "JD template created!", "template": new_template}

# Update a JD template
@router.put("/api/admin/templates/{template_id}")
async def update_jd_template(
    template_id: int, 
    request: models.JDTemplateRequest, 
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    template = db.query(sql_models.JDTemplate).filter(sql_models.JDTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="JD template not found")
        
    template.title = request.title
    template.description = request.description
    db.commit()
    return {"message": "Updated successfully!"}

# Delete a JD template
@router.delete("/api/admin/templates/{template_id}")
async def delete_jd_template(
    template_id: int, 
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    template = db.query(sql_models.JDTemplate).filter(sql_models.JDTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="JD template not found")
        
    db.delete(template)
    db.commit()
    return {"message": "Deleted successfully!"}

# Delete a user
@router.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int, 
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    # Prevent admin from deleting themselves
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account!")
        
    user = db.query(sql_models.User).filter(sql_models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Cascade delete all related records before deleting the user
    db.query(sql_models.InterviewHistory).filter(sql_models.InterviewHistory.user_id == user_id).delete()
    db.query(sql_models.TransactionHistory).filter(sql_models.TransactionHistory.user_id == user_id).delete()
    db.query(sql_models.SupportMessage).filter(sql_models.SupportMessage.user_id == user_id).delete()
    db.query(sql_models.Transaction).filter(sql_models.Transaction.user_id == user_id).delete()
    db.query(sql_models.UserProfile).filter(sql_models.UserProfile.user_id == user_id).delete()
    db.query(sql_models.Experience).filter(sql_models.Experience.user_id == user_id).delete()
    db.query(sql_models.Education).filter(sql_models.Education.user_id == user_id).delete()
        
    db.delete(user)
    db.commit()
    return {"message": "User permanently deleted!"}

# Create a new user (Admin only)
@router.post("/api/admin/users")
async def create_user_admin(
    request: models.AdminUserCreate, 
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    # Check if email exists
    existing_user = db.query(sql_models.User).filter(sql_models.User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_pw = security.get_password_hash(request.password)
    
    new_user = sql_models.User(
        email=request.email,
        full_name=request.full_name,
        hashed_password=hashed_pw,
        role=request.role,
        credits=request.credits,
        plan=request.plan
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User created successfully!", "user_id": new_user.id}

# Update a user (Admin only)
@router.put("/api/admin/users/{user_id}")
async def update_user_admin(
    user_id: int,
    request: models.AdminUserUpdate, 
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    user = db.query(sql_models.User).filter(sql_models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Check if new email conflicts with another user
    if request.email and request.email != user.email:
        existing_email = db.query(sql_models.User).filter(sql_models.User.email == request.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already taken by another user")
            
    if request.email is not None:
        user.email = request.email
    if request.full_name is not None:
        user.full_name = request.full_name
    if request.role is not None:
        user.role = request.role
    if request.credits is not None:
        user.credits = request.credits
    if request.plan is not None:
        user.plan = request.plan
    if request.password is not None and request.password != "":
        user.hashed_password = security.get_password_hash(request.password)
        
    db.commit()
    
    return {"message": "User updated successfully!"}

# Add credits for a user (Admin only)
@router.post("/api/admin/users/{user_id}/add-credits")
async def add_user_credits(
    user_id: int, 
    request: models.AddCreditRequest, 
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    user = db.query(sql_models.User).filter(sql_models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.credits += request.amount

    new_txn = sql_models.TransactionHistory(
        user_id=user.id,
        amount=request.amount,
        transaction_type="add_credits",
        note=f"Admin {current_user.email} added {request.amount} credits."
    )
    db.add(new_txn)
    
    db.commit()
    
    return {
        "message": f"Successfully added {request.amount} credits for {user.full_name}!",
        "new_credits": user.credits
    }

# Transaction history (Credit logs)
@router.get("/api/admin/transactions")
async def get_admin_transactions(
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    transactions = db.query(
        sql_models.TransactionHistory,
        sql_models.User.email,
        sql_models.User.full_name
    ).join(
        sql_models.User, sql_models.User.id == sql_models.TransactionHistory.user_id
    ).order_by(
        sql_models.TransactionHistory.created_at.desc()
    ).all()
    
    result = []
    for txn, email, full_name in transactions:
        result.append({
            "id": txn.id,
            "user_email": email,
            "user_name": full_name,
            "amount": txn.amount,
            "transaction_type": txn.transaction_type,
            "note": txn.note,
            "created_at": txn.created_at
        })
        
    return {"transactions": result}

# Get user detail (Admin only)
@router.get("/api/admin/users/{user_id}")
async def get_user_detail(
    user_id: int,
    current_user: sql_models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    user = db.query(sql_models.User).filter(sql_models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Interview history
    interviews = db.query(sql_models.InterviewHistory).filter(
        sql_models.InterviewHistory.user_id == user_id
    ).order_by(sql_models.InterviewHistory.created_at.desc()).all()
    
    interview_list = [{
        "id": iv.id,
        "title": iv.title,
        "position": iv.position,
        "score": iv.score,
        "interview_type": iv.interview_type,
        "created_at": iv.created_at
    } for iv in interviews]
    
    # Transaction history
    transactions = db.query(sql_models.TransactionHistory).filter(
        sql_models.TransactionHistory.user_id == user_id
    ).order_by(sql_models.TransactionHistory.created_at.desc()).all()
    
    transaction_list = [{
        "id": txn.id,
        "amount": txn.amount,
        "transaction_type": txn.transaction_type,
        "note": txn.note,
        "created_at": txn.created_at
    } for txn in transactions]
    
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "plan": user.plan,
            "credits": user.credits
        },
        "interviews": interview_list,
        "transactions": transaction_list
    }


def _ensure_admin(current_user: sql_models.User):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


def _extract_text_from_upload(upload: UploadFile, content: bytes) -> str:
    filename = (upload.filename or "").lower()
    if filename.endswith(".txt") or filename.endswith(".md"):
        return content.decode("utf-8", errors="ignore")
    if filename.endswith(".docx"):
        doc = Document(BytesIO(content))
        return "\n".join([p.text for p in doc.paragraphs if p.text and p.text.strip()])
    raise HTTPException(status_code=400, detail="Unsupported file type. Use .txt, .md, or .docx")


def _infer_node_type(line: str) -> str:
    text = line.lower()
    if ("if " in text and " then " in text) or ("if" in text and any(k in text for k in ["follow up", "follow-up"])):
        return "follow_up_strategy"
    if any(k in text for k in ["do not", "don't", "avoid", "never", "forbidden", "must not"]):
        return "red_flag"
    if any(k in text for k in ["evaluate", "assessment", "rubric", "score", "scoring", "criteria"]):
        return "rubric"
    if "?" in text or any(k in text for k in ["question", "ask", "describe a time", "how would you"]):
        return "question_pattern"
    if any(k in text for k in ["should", "must", "always", "principle", "guideline"]):
        return "principle"
    return "domain_knowledge"


VALID_BRAIN_NODE_TYPES = {"principle", "rubric", "red_flag", "follow_up_strategy", "question_pattern", "domain_knowledge"}


def _parse_text_to_candidates(raw_text: str, strict: bool = False, max_candidates: int = 300):
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    nodes = []
    edges = []
    section_type = "domain_knowledge"

    for line in lines:
        lower = line.lower().strip()
        if lower.startswith("##"):
            heading = lower.lstrip("#").strip().replace(" ", "_").replace("-", "_")
            if heading in {"principle", "rubric", "red_flag", "follow_up_strategy", "question_pattern", "domain_knowledge"}:
                section_type = heading
            continue
        if lower.startswith("#"):
            continue

        content = line[1:].strip() if line.startswith("-") else line
        if not content:
            continue

        node_key = f"n_{len(nodes) + 1}"
        inferred_type = _infer_node_type(content)
        node_type = section_type if section_type != "domain_knowledge" else inferred_type
        confidence = 0.75 if len(content) >= 24 else 0.6
        nodes.append({
            "id": node_key,
            "type": node_type,
            "label": (content[:80] + "...") if len(content) > 80 else content,
            "content": content,
            "tags": [],
            "weight": 0.7,
            "active": True,
            "confidence": confidence,
        })

        if len(nodes) >= max_candidates:
            break

    if not strict:
        for idx in range(len(nodes) - 1):
            edges.append({
                "id": f"e_{idx+1}",
                "source": nodes[idx]["id"],
                "target": nodes[idx + 1]["id"],
                "type": "supports",
                "weight": 0.5,
                "confidence": 0.62,
            })

    return nodes, edges


def _safe_json_loads(raw: str):
    cleaned = (raw or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def _normalize_enriched_item(item: dict):
    if not isinstance(item, dict):
        return None
    node_type = str(item.get("type", "")).strip().lower()
    if node_type not in VALID_BRAIN_NODE_TYPES:
        return None
    tags = item.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()][:8]
    try:
        weight = float(item.get("weight", 0.7))
    except Exception:
        weight = 0.7
    weight = max(0.1, min(1.0, weight))
    try:
        confidence = float(item.get("confidence", 0.75))
    except Exception:
        confidence = 0.75
    confidence = max(0.1, min(1.0, confidence))
    return {
        "id": str(item.get("id", "")).strip(),
        "type": node_type,
        "tags": tags,
        "weight": weight,
        "confidence": confidence,
    }


def _enrich_candidates_with_llm(nodes: list[dict], model: str, max_items: int):
    target_nodes = nodes[:max_items]
    payload = [{"id": n["id"], "content": n.get("content", ""), "type": n.get("type", "domain_knowledge")} for n in target_nodes]
    system_prompt = (
        "You are a strict data normalizer for interviewer brain graph nodes. "
        "Classify each item into exactly one type: principle, rubric, red_flag, follow_up_strategy, question_pattern, domain_knowledge. "
        "Return pure JSON object with key 'items' (array). Each item must have id, type, tags (array up to 5), weight (0.1..1.0), confidence (0.1..1.0)."
    )
    user_prompt = json.dumps({"items": payload}, ensure_ascii=False)
    raw = call_ai_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=0.2,
        max_tokens=1200,
        response_format={"type": "json_object"},
        timeout=60,
    )
    data = _safe_json_loads(raw)
    items = data.get("items", []) if isinstance(data, dict) else []
    normalized = [_normalize_enriched_item(i) for i in items]
    normalized = [i for i in normalized if i]
    by_id = {i["id"]: i for i in normalized}

    enriched = []
    for n in nodes:
        patch = by_id.get(n["id"])
        if not patch:
            enriched.append(n)
            continue
        updated = dict(n)
        updated["type"] = patch["type"]
        updated["tags"] = patch["tags"]
        updated["weight"] = patch["weight"]
        updated["confidence"] = patch["confidence"]
        enriched.append(updated)
    return enriched


def _get_or_create_version(db: Session, version: str, user_id: int | None = None):
    item = db.query(sql_models.AIBrainVersion).filter(sql_models.AIBrainVersion.version == version).first()
    if item:
        return item
    item = sql_models.AIBrainVersion(version=version, name="speakcv-interviewer-brain", status="draft", created_by=user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/api/admin/ai-brain/ingestion/upload")
async def ai_brain_upload_file(
    file: UploadFile = File(...),
    current_user: sql_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    content = await file.read()
    text = _extract_text_from_upload(file, content)
    file_key = f"f_{uuid.uuid4().hex[:12]}"

    rec = sql_models.AIBrainIngestionFile(
        file_key=file_key,
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        raw_text=text,
        created_by=current_user.id,
    )
    db.add(rec)
    db.commit()
    return {"file_key": file_key, "filename": rec.filename, "chars": len(text)}


@router.post("/api/admin/ai-brain/ingestion/jobs")
async def ai_brain_start_job(
    request: models.AIBrainIngestionStartRequest,
    current_user: sql_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    source = db.query(sql_models.AIBrainIngestionFile).filter(sql_models.AIBrainIngestionFile.file_key == request.file_key).first()
    if not source:
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    version_name = request.version or datetime.now().strftime("%Y.%m.%d-draft")
    version = _get_or_create_version(db, version_name, current_user.id)

    nodes, edges = _parse_text_to_candidates(source.raw_text or "", strict=False, max_candidates=300)

    enrich_cfg = db.query(sql_models.SystemConfig).filter_by(setting_key="ai_brain_ingestion_enrichment_enabled").first()
    enrich_enabled = True if not enrich_cfg else enrich_cfg.setting_value.strip().lower() == "true"
    enrich_model_cfg = db.query(sql_models.SystemConfig).filter_by(setting_key="ai_brain_ingestion_enrichment_model").first()
    enrich_model = enrich_model_cfg.setting_value.strip() if enrich_model_cfg and enrich_model_cfg.setting_value else "gpt-4o-mini"
    enrich_max_cfg = db.query(sql_models.SystemConfig).filter_by(setting_key="ai_brain_ingestion_enrichment_max_items").first()
    try:
        enrich_max_items = int(enrich_max_cfg.setting_value) if enrich_max_cfg and enrich_max_cfg.setting_value else 80
    except Exception:
        enrich_max_items = 80

    enriched = False
    enrich_error = None
    if enrich_enabled and nodes:
        try:
            nodes = _enrich_candidates_with_llm(nodes, enrich_model, max(1, min(enrich_max_items, 200)))
            enriched = True
        except Exception as e:
            enrich_error = str(e)

    job_key = f"j_{uuid.uuid4().hex[:12]}"
    summary = {"nodes": len(nodes), "edges": len(edges), "enriched": enriched}
    if enrich_error:
        summary["enrich_error"] = enrich_error[:200]

    job = sql_models.AIBrainIngestionJob(
        job_key=job_key,
        version_id=version.id,
        source_filename=source.filename,
        source_type=(source.filename.split(".")[-1].lower() if "." in source.filename else "txt"),
        raw_text=source.raw_text,
        status="ready_for_review",
        summary=summary,
        created_by=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    for node in nodes:
        db.add(sql_models.AIBrainIngestionCandidate(job_id=job.id, candidate_kind="node", payload=node, confidence=node["confidence"]))
    for edge in edges:
        db.add(sql_models.AIBrainIngestionCandidate(job_id=job.id, candidate_kind="edge", payload=edge, confidence=edge["confidence"]))
    db.commit()

    return {"job_id": job_key, "status": job.status, "summary": job.summary, "version": version.version}


@router.get("/api/admin/ai-brain/ingestion/jobs/{job_id}")
async def ai_brain_job_status(
    job_id: str,
    current_user: sql_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    job = db.query(sql_models.AIBrainIngestionJob).filter(sql_models.AIBrainIngestionJob.job_key == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    candidates = db.query(sql_models.AIBrainIngestionCandidate).filter(sql_models.AIBrainIngestionCandidate.job_id == job.id).all()
    return {
        "job_id": job.job_key,
        "status": job.status,
        "summary": job.summary or {},
        "candidates": [
            {
                "id": c.id,
                "kind": c.candidate_kind,
                "payload": c.payload,
                "confidence": c.confidence,
                "accepted": c.accepted,
                "rejected": c.rejected,
            }
            for c in candidates
        ],
    }


@router.post("/api/admin/ai-brain/ingestion/jobs/{job_id}/apply-draft")
async def ai_brain_apply_draft(
    job_id: str,
    request: models.AIBrainApplyDraftRequest,
    current_user: sql_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    job = db.query(sql_models.AIBrainIngestionJob).filter(sql_models.AIBrainIngestionJob.job_key == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    candidates = db.query(sql_models.AIBrainIngestionCandidate).filter(sql_models.AIBrainIngestionCandidate.job_id == job.id).all()
    accepted_nodes = 0
    accepted_edges = 0

    for c in candidates:
        if request.accept_all_high_confidence and c.confidence < request.confidence_threshold:
            continue
        payload = c.payload or {}
        if c.candidate_kind == "node":
            node_type = payload.get("type", "domain_knowledge")
            content = payload.get("content", "")
            existing_node = db.query(sql_models.AIBrainNode).filter(
                sql_models.AIBrainNode.version_id == job.version_id,
                sql_models.AIBrainNode.node_type == node_type,
                sql_models.AIBrainNode.content == content,
            ).first()
            if existing_node:
                c.accepted = True
                c.rejected = False
                continue

            db.add(sql_models.AIBrainNode(
                version_id=job.version_id,
                node_key=payload.get("id", f"n_{c.id}"),
                node_type=node_type,
                label=payload.get("label", "Untitled"),
                content=content,
                tags=payload.get("tags", []),
                weight=float(payload.get("weight", 0.7)),
                active=bool(payload.get("active", True)),
            ))
            accepted_nodes += 1
        elif c.candidate_kind == "edge":
            db.add(sql_models.AIBrainEdge(
                version_id=job.version_id,
                edge_key=payload.get("id", f"e_{c.id}"),
                source_node_key=payload.get("source", ""),
                target_node_key=payload.get("target", ""),
                edge_type=payload.get("type", "supports"),
                weight=float(payload.get("weight", 0.5)),
            ))
            accepted_edges += 1
        c.accepted = True
        c.rejected = False

    job.status = "applied"
    db.commit()
    return {"message": "Applied to draft", "accepted_nodes": accepted_nodes, "accepted_edges": accepted_edges}


@router.post("/api/admin/ai-brain/ingestion/jobs/{job_id}/reject")
async def ai_brain_reject_job(
    job_id: str,
    request: models.AIBrainRejectJobRequest,
    current_user: sql_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    job = db.query(sql_models.AIBrainIngestionJob).filter(sql_models.AIBrainIngestionJob.job_key == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "rejected"
    summary = job.summary or {}
    summary["reject_reason"] = request.reason
    job.summary = summary
    db.commit()
    return {"message": "Job rejected", "job_id": job_id, "reason": request.reason}


@router.post("/api/admin/ai-brain/publish/{version}")
async def ai_brain_publish(
    version: str,
    current_user: sql_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    target = db.query(sql_models.AIBrainVersion).filter(sql_models.AIBrainVersion.version == version).first()
    if not target:
        raise HTTPException(status_code=404, detail="Version not found")

    db.query(sql_models.AIBrainVersion).filter(sql_models.AIBrainVersion.status == "active").update({"status": "archived"})
    target.status = "active"
    db.commit()
    return {"message": "Published", "version": version}


@router.post("/api/admin/ai-brain/assemble-prompt")
async def ai_brain_assemble_prompt(
    request: models.AIBrainAssemblePromptRequest,
    current_user: sql_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    if request.version:
        version = db.query(sql_models.AIBrainVersion).filter(sql_models.AIBrainVersion.version == request.version).first()
    else:
        version = db.query(sql_models.AIBrainVersion).filter(sql_models.AIBrainVersion.status == "active").first()

    if not version:
        return {"prompt": "", "version": None, "selected_nodes": []}

    nodes = db.query(sql_models.AIBrainNode).filter(
        sql_models.AIBrainNode.version_id == version.id,
        sql_models.AIBrainNode.active == True
    ).order_by(sql_models.AIBrainNode.weight.desc()).all()

    parts = [
        f"Interview role: {request.job_role}",
        f"Seniority: {request.seniority}",
        f"Mode: {request.interview_mode}",
    ]
    selected = []
    seen_lines = set()
    for n in nodes:
        line = f"[{n.node_type}] {n.content}"
        if line in seen_lines:
            continue
        seen_lines.add(line)
        parts.append(line)
        selected.append({"node_key": n.node_key, "type": n.node_type, "weight": n.weight})
        if len(selected) >= request.max_items:
            break

    prompt = "\n".join(parts)
    if len(prompt) > request.max_chars:
        prompt = prompt[: request.max_chars]

    return {"version": version.version, "prompt": prompt, "selected_nodes": selected}


@router.get("/api/admin/ai-brain/versions")
async def ai_brain_versions(
    current_user: sql_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    versions = db.query(sql_models.AIBrainVersion).order_by(sql_models.AIBrainVersion.id.desc()).all()
    return {
        "versions": [
            {
                "version": v.version,
                "name": v.name,
                "status": v.status,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]
    }