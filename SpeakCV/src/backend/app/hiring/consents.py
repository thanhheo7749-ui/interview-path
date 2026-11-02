from dataclasses import dataclass
from datetime import datetime, timezone

from app.database.sql_models import Consent

VERSION = "2026-11-02"
DEFAULT_RETENTION_DAYS = 90
UNDECIDED_RETENTION_DAYS = 180
REAPPLY_DAYS = 90
# Sent to the candidate app in a 409, which shows its own message and offers no retry.
RECORDING_CONSENT_WITHDRAWN = "recording_consent_withdrawn"
CV_CONSENT_WITHDRAWN = "cv_consent_withdrawn"


@dataclass(frozen=True)
class ConsentText:
    version: str
    language: str  # the language of `text`, which may not be the one asked for
    text: str


# PROPOSED WORDING. This text has not had legal review and makes no claim of legal compliance.
# The Korean text is a draft too, and stays flagged for legal and native review.
CONSENT_TEXTS = {
    ("cv_processing", "en"): (
        "The company named in the job receives your application. Your CV is processed by AI to compare it with "
        "the job's requirements. One AI step reads your original CV to remove identifying details; all later "
        "steps see only the masked version. Your data is deleted after the retention period, and you can delete "
        "it yourself at any time from My data. If you delete an application after an interview has started or a "
        "decision was made, we keep a one-way code made from your account and this job, with the date you applied, "
        "for up to {reapply_days} days. It is used only to apply the limit of one application per job every "
        "{reapply_days} days, and it holds nothing else about you."
    ),
    ("cv_processing", "vi"): (
        "Công ty nêu trong tin tuyển dụng sẽ nhận được hồ sơ của bạn. CV của bạn được AI xử lý để đối chiếu với "
        "yêu cầu công việc. Một bước AI đọc CV gốc của bạn để xóa các thông tin nhận dạng; các bước sau chỉ thấy "
        "bản đã che. Dữ liệu sẽ bị xóa sau thời hạn lưu trữ, và bạn có thể tự xóa bất cứ lúc nào trong mục Dữ liệu của tôi. "
        "Nếu bạn xóa hồ sơ sau khi buổi phỏng vấn đã bắt đầu hoặc đã có quyết định, chúng tôi giữ một mã một chiều tạo "
        "từ tài khoản của bạn và vị trí này, kèm ngày ứng tuyển, trong tối đa {reapply_days} ngày. Mã này chỉ dùng để áp "
        "dụng giới hạn một lần ứng tuyển cho mỗi vị trí trong {reapply_days} ngày và không chứa thông tin nào khác về bạn."
    ),
    ("cv_processing", "ko"): (
        "채용 공고에 명시된 회사가 귀하의 지원서를 받습니다. 귀하의 이력서는 직무 요건과 비교하기 위해 AI로 처리됩니다. "
        "한 AI 단계가 식별 정보를 제거하기 위해 이력서 원본을 읽으며, 이후 단계에서는 가려진 버전만 사용합니다. 데이터는 "
        "보관 기간이 지나면 삭제되며, 내 데이터에서 언제든지 직접 삭제할 수 있습니다. 면접을 시작했거나 결정이 내려진 후 "
        "지원서를 삭제하면, 계정과 이 채용 공고로 만든 단방향 코드와 지원 날짜를 최대 {reapply_days}일 동안 보관합니다. "
        "이 코드는 채용 공고당 {reapply_days}일에 한 번 지원할 수 있다는 제한을 적용하는 데에만 사용되며, 그 외 귀하에 관한 "
        "정보는 담고 있지 않습니다."
    ),
    ("recording_screening", "en"): (
        "Your answers will be recorded as audio and transcribed. The purpose is to help HR review your "
        "application. HR at this company can read the transcript and listen to the audio. AI analyses the "
        "transcript, and a person makes the decision. There is no video and no analysis of your voice tone. "
        "Recordings are kept for {retention_days} days after the decision, or {undecided_days} days after you applied "
        "if no decision is made."
    ),
    ("recording_screening", "vi"): (
        "Câu trả lời của bạn sẽ được ghi âm và chuyển thành văn bản. Mục đích là hỗ trợ HR xem xét hồ sơ của "
        "bạn. HR của công ty này có thể đọc bản ghi và nghe âm thanh. AI phân tích bản ghi, và quyết định do "
        "con người đưa ra. Không có video và không phân tích giọng điệu của bạn. Bản ghi được lưu trong "
        "{retention_days} ngày sau khi có quyết định, hoặc {undecided_days} ngày sau khi bạn ứng tuyển nếu không có quyết định."
    ),
    ("recording_screening", "ko"): (
        "귀하의 답변은 음성으로 녹음되고 텍스트로 변환됩니다. 목적은 HR이 귀하의 지원서를 검토하도록 돕는 것입니다. 이 회사의 "
        "HR은 녹취록을 읽고 음성을 들을 수 있습니다. AI가 녹취록을 분석하고, 결정은 사람이 내립니다. 영상은 없으며 목소리 톤을 "
        "분석하지 않습니다. 녹음은 결정 후 {retention_days}일 동안 보관되며, 결정이 내려지지 않으면 지원 후 {undecided_days}일 "
        "동안 보관됩니다."
    ),
}
PURPOSES = tuple(sorted({purpose for purpose, _ in CONSENT_TEXTS}))
FALLBACK_LANGUAGE = "en"


def text_language(language: str | None) -> str:
    """The language a text comes back in: the one asked for if a text exists in it, otherwise English."""
    return language if (PURPOSES[0], language) in CONSENT_TEXTS else FALLBACK_LANGUAGE


def current_text(purpose: str, language: str, retention_days: int = DEFAULT_RETENTION_DAYS) -> ConsentText:
    if purpose not in PURPOSES:
        raise ValueError(f"Unknown consent purpose: {purpose}")
    used = text_language(language)
    text = CONSENT_TEXTS[(purpose, used)].format(
        retention_days=retention_days, undecided_days=UNDECIDED_RETENTION_DAYS, reapply_days=REAPPLY_DAYS,
    )
    return ConsentText(version=VERSION, language=used, text=text)


def record(db, user_id, company_id, application_id, purpose, text_version, language=None) -> Consent:
    if purpose not in PURPOSES:
        raise ValueError(f"Unknown consent purpose: {purpose}")
    consent = Consent(user_id=user_id, company_id=company_id, application_id=application_id,
                      purpose=purpose, text_version=text_version, language=text_language(language) if language else None)
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


def was_withdrawn(db, application_id, purpose) -> bool:
    """Not the same as "not active": an application with no consent row at all has withdrawn nothing."""
    query = db.query(Consent.id).filter(
        Consent.application_id == application_id, Consent.purpose == purpose, Consent.withdrawn_at.isnot(None),
    )
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
