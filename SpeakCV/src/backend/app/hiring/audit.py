from app.database.sql_models import AuditLog


def record(db, company_id, actor_user_id, action, target_type, target_id, payload=None,
           ai_provider=None, ai_model=None, prompt_version=None) -> AuditLog:
    """Add an audit row to the session. The caller commits."""
    entry = AuditLog(
        company_id=company_id, actor_user_id=actor_user_id, action=action,
        target_type=target_type, target_id=target_id, payload=payload or {},
        ai_provider=ai_provider, ai_model=ai_model, prompt_version=prompt_version,
    )
    db.add(entry)
    return entry
