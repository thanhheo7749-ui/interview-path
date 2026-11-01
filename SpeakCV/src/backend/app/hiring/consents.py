from dataclasses import dataclass
from datetime import datetime, timezone

from app.database.sql_models import Consent

VERSION = "2026-11-01"
DEFAULT_RETENTION_DAYS = 90


@dataclass(frozen=True)
class ConsentText:
    version: str
    text: str


# PROPOSED WORDING. This text has not had legal review and makes no claim of legal compliance.
CONSENT_TEXTS = {
    ("cv_processing", "en"): (
        "The company named in the job receives your application. Your CV is processed by AI to compare it with "
        "the job's requirements. One AI step reads your original CV to remove identifying details; all later "
        "steps see only the masked version. Your data is deleted after the retention period, and you can delete "
        "it yourself at any time from My data."
    ),
    ("cv_processing", "vi"): (
        "Công ty nêu trong tin tuyển dụng sẽ nhận được hồ sơ của bạn. CV của bạn được AI xử lý để đối chiếu với "
        "yêu cầu công việc. Một bước AI đọc CV gốc của bạn để xóa các thông tin nhận dạng; các bước sau chỉ thấy "
        "bản đã che. Dữ liệu sẽ bị xóa sau thời hạn lưu trữ, và bạn có thể tự xóa bất cứ lúc nào trong mục Dữ liệu của tôi."
    ),
    ("recording_screening", "en"): (
        "Your answers will be recorded as audio and transcribed. The purpose is to help HR review your "
        "application. HR at this company can read the transcript and listen to the audio. AI analyses the "
        "transcript, and a person makes the decision. There is no video and no analysis of your voice tone. "
        "Recordings are kept for {retention_days} days."
    ),
    ("recording_screening", "vi"): (
        "Câu trả lời của bạn sẽ được ghi âm và chuyển thành văn bản. Mục đích là hỗ trợ HR xem xét hồ sơ của "
        "bạn. HR của công ty này có thể đọc bản ghi và nghe âm thanh. AI phân tích bản ghi, và quyết định do "
        "con người đưa ra. Không có video và không phân tích giọng điệu của bạn. Bản ghi được lưu trong "
        "{retention_days} ngày."
    ),
}
PURPOSES = tuple(sorted({purpose for purpose, _ in CONSENT_TEXTS}))


def current_text(purpose: str, language: str, retention_days: int = DEFAULT_RETENTION_DAYS) -> ConsentText:
    if purpose not in PURPOSES:
        raise ValueError(f"Unknown consent purpose: {purpose}")
    template = CONSENT_TEXTS.get((purpose, language)) or CONSENT_TEXTS[(purpose, "en")]
    return ConsentText(version=VERSION, text=template.format(retention_days=retention_days))


def record(db, user_id, company_id, application_id, purpose, text_version, language=None) -> Consent:
    if purpose not in PURPOSES:
        raise ValueError(f"Unknown consent purpose: {purpose}")
    consent = Consent(user_id=user_id, company_id=company_id, application_id=application_id,
                      purpose=purpose, text_version=text_version, language=language)
    db.add(consent)
    db.flush()
    return consent


def has_active(db, user_id, purpose, application_id=None, company_id=None) -> bool:
    query = db.query(Consent.id).filter(
        Consent.user_id == user_id, Consent.purpose == purpose, Consent.withdrawn_at.is_(None),
    )
    if application_id is not None:
        query = query.filter(Consent.application_id == application_id)
    if company_id is not None:
        query = query.filter(Consent.company_id == company_id)
    return query.first() is not None


def withdraw(db, consent_id, user_id) -> Consent:
    consent = db.get(Consent, consent_id)
    if consent is None:
        raise LookupError("Consent not found")
    if consent.user_id != user_id:
        raise PermissionError("Not your consent")
    if consent.withdrawn_at is None:
        consent.withdrawn_at = datetime.now(timezone.utc)
        db.flush()
    return consent
