# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

from typing import Any, List, Optional
from pydantic import BaseModel, Field
from datetime import date

# ── Profile & Experience ──────────────────────

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[str] = None
    avatar: Optional[str] = None
    master_cv_text: Optional[str] = None
    master_cv_structured: Optional[dict[str, Any]] = None

class ExperienceCreate(BaseModel):
    company_name: str
    position: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool = False
    description: Optional[str] = None

class EducationCreate(BaseModel):
    school_name: str
    degree: str
    major: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None

# ── Interview & Chat ─────────────────────────

class ChatRequest(BaseModel):
    user_text: str
    jd_text: str = ""
    voice_id: str = "en-US-AndrewMultilingualNeural"
    lang: str = "vi"
    mode: str = "general"
    chat_history: list = []
    interview_context: Optional[dict[str, Any]] = None
    target_topics: List[str] = Field(default_factory=list)
    audio_meta: Optional[dict[str, Any]] = None
    current_topic: Optional[str] = None
    low_latency: bool = True
    trace_id: Optional[str] = None

class HintRequest(BaseModel):
    last_question: str
    jd_text: str = ""
    lang: str = "vi"

class ReportRequest(BaseModel):
    history: str
    jd_text: str = ""
    position: str = "Chưa xác định"
    history_id: Optional[int] = None
    interview_type: str = "free"
    question_limit: int = 0
    time_limit: int = 0

# ── CV Features ──────────────────────────────

class CVGenRequest(BaseModel):
    user_info: str
    position: str
    company: str
    style_instruction: str = ""

class CVRewriteRequest(BaseModel):
    cv_text: str
    template_style: str = "harvard"

class CVTailorRequest(BaseModel):
    master_cv_json: dict
    jd_text: str

class CVParseMasterCVRequest(BaseModel):
    raw_text: str

class InterviewContextRequest(BaseModel):
    cv_text: str
    jd_text: str

class InterviewContextData(BaseModel):
    match_score: float
    highlighted_strengths: List[str] = Field(default_factory=list)
    skill_gaps: List[str] = Field(default_factory=list)
    target_topics: List[str] = Field(default_factory=list)

class InterviewContextResponse(BaseModel):
    interview_context: InterviewContextData

# ── Auth & Users ─────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    credits: int = 100

class AdminUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "user"
    credits: int = 100
    plan: str = "free"

class AdminUserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    credits: Optional[int] = None
    plan: Optional[str] = None
    password: Optional[str] = None # Admin can optionally reset password

class GoogleAuthRequest(BaseModel):
    token: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_name: str
    role: str = "user"

# ── Interview Config & Templates ─────────────

class RenameRequest(BaseModel):
    title: str

class UpdateInterviewConfig(BaseModel):
    interview_type: str = "free"
    question_limit: int = 5
    time_limit: int = 120

class JDTemplateRequest(BaseModel):
    title: str
    description: str

# ── Admin & System ───────────────────────────

class AddCreditRequest(BaseModel):
    amount: int

class SystemConfigUpdate(BaseModel):
    system_prompt: str
    temperature: float

# ── Support ──────────────────────────────────

class SupportMessageCreate(BaseModel):
    message: str

class SupportMessageResponse(BaseModel):
    id: int
    user_id: int
    admin_id: Optional[int] = None
    message: str
    sender_type: str
    is_read: bool
    created_at: str

    class Config:
        from_attributes = True

class QuotaResponse(BaseModel):
    remaining: int  # -1 = unlimited (pro)
    limit: int      # -1 = unlimited (pro)

class UnreadCountResponse(BaseModel):
    unread_count: int


# --- CV Makeover JSON Schema ---
class CVPersonalInfo(BaseModel):
    name: Optional[str] = ""
    title: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    linkedin: Optional[str] = ""
    location: Optional[str] = ""
    summary: Optional[str] = ""

class CVExperienceItem(BaseModel):
    company: Optional[str] = ""
    role: Optional[str] = ""
    period: Optional[str] = ""
    achievements: Optional[List[str]] = []

class CVEducationItem(BaseModel):
    school: Optional[str] = ""
    degree: Optional[str] = ""
    period: Optional[str] = ""

class CVProjectItem(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    technologies: Optional[List[str]] = []

class CVAnalysisFeedback(BaseModel):
    strengths: Optional[List[str]] = []
    weaknesses: Optional[List[str]] = []
    overall_score: Optional[int] = 0

class CVMakeoverData(BaseModel):
    analysis_feedback: Optional[CVAnalysisFeedback] = CVAnalysisFeedback()
    personal_info: Optional[CVPersonalInfo] = CVPersonalInfo()
    skills: Optional[List[str]] = []
    experience: Optional[List[CVExperienceItem]] = []
    education: Optional[List[CVEducationItem]] = []
    projects: Optional[List[CVProjectItem]] = []

# ── Questions ───────────────────────────

class QuestionCreate(BaseModel):
    question: str
    answer: str

class QuestionUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    status: Optional[str] = None

class QuestionApprove(BaseModel):
    answer: str
    status: str = "approved"

class QuestionReject(BaseModel):
    status: str = "rejected"

class QuestionsPageResponse(BaseModel):
    items: list
    total: int
    page: int
    limit: int

class UserHistoryUpdate(BaseModel):
    title: str

class PublicQuestionCreate(BaseModel):
    question: str

class PublicQuestionListResponse(BaseModel):
    id: int
    question: str
    status: str
    answer: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

class SubscriptionUsageResponse(BaseModel):
    credits: int
    plan: str

class AdminQuestionUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    status: Optional[str] = None
    user_id: Optional[int] = None

class TemplatePromptUpdate(BaseModel):
    content: str

class SupportReplyCreate(BaseModel):
    message: str

class SupportThreadResponse(BaseModel):
    thread_id: int
    messages: list[SupportMessageResponse]

class DashboardStatsResponse(BaseModel):
    total_users: int
    total_interviews: int
    total_questions: int
    total_transactions: int
    total_revenue: float

class AdminDashboardResponse(BaseModel):
    users: list
    stats: DashboardStatsResponse

class TransactionLogResponse(BaseModel):
    id: int
    user_id: int
    amount: float
    status: str
    created_at: str

    class Config:
        from_attributes = True

class InterviewHistorySummary(BaseModel):
    id: int
    title: str
    score: Optional[float] = None
    created_at: str

    class Config:
        from_attributes = True

class PromptTemplateUpdate(BaseModel):
    key: str
    content: str

class UserQuotaInfo(BaseModel):
    credits: int
    plan: str
    remaining: int
    limit: int

class AdminAddCreditResponse(BaseModel):
    message: str
    credits: int

class SupportUnreadResponse(BaseModel):
    unread_count: int

class ProfileInfoResponse(BaseModel):
    info: dict
    experiences: list
    educations: list

class InterviewHintResponse(BaseModel):
    hint: str

class CVGenerationResponse(BaseModel):
    content: str

class CVReviewResponse(BaseModel):
    review: str

class CVMakeoverResponse(BaseModel):
    cv_data: dict
    extracted_text: str

class CVTailorResponse(BaseModel):
    cv_data: dict
    tailor_summary: dict

class EndInterviewResponse(BaseModel):
    report: dict
    history_id: Optional[int] = None

class TranscribeResponse(BaseModel):
    text: str

class ChatSimpleResponse(BaseModel):
    content: str

class GenericMessageResponse(BaseModel):
    message: str

class BooleanResponse(BaseModel):
    success: bool

class AdminConfigResponse(BaseModel):
    system_prompt: str
    temperature: float

class HistoryConfigPatchResponse(BaseModel):
    message: str

class UpgradeResponse(BaseModel):
    message: str
    plan: str

class GoogleAuthResponse(Token):
    pass

class LoginResponse(Token):
    pass

class RegisterResponse(BaseModel):
    message: str

class ProfileUpdateResponse(BaseModel):
    message: str

class ExperienceResponse(BaseModel):
    message: str

class EducationResponse(BaseModel):
    message: str

class DeleteResponse(BaseModel):
    message: str

class RenameResponse(BaseModel):
    message: str

class JDTemplateResponse(BaseModel):
    message: str

class QuestionActionResponse(BaseModel):
    message: str

class SupportActionResponse(BaseModel):
    message: str

class PromptTemplateResponse(BaseModel):
    message: str

class SystemLogsResponse(BaseModel):
    items: list

class HistoryListResponse(BaseModel):
    items: list[InterviewHistorySummary]

class AdminUsersResponse(BaseModel):
    items: list

class TransactionsResponse(BaseModel):
    items: list[TransactionLogResponse]

class QuestionsResponse(BaseModel):
    items: list

class SupportThreadsResponse(BaseModel):
    items: list

class PromptTemplatesResponse(BaseModel):
    items: list

class InterviewConfigResponse(BaseModel):
    interview_type: str
    question_limit: int
    time_limit: int

class UserCreditsResponse(BaseModel):
    credits: int

class HealthResponse(BaseModel):
    status: str

class AdminOverviewResponse(BaseModel):
    stats: DashboardStatsResponse
    users: list
    transactions: list[TransactionLogResponse]

class TemplateResponse(BaseModel):
    id: int
    title: str
    description: str

class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]

class AdminQuestionResponse(BaseModel):
    id: int
    question: str
    answer: Optional[str] = None
    status: str

class AdminQuestionListResponse(BaseModel):
    items: list[AdminQuestionResponse]

class UserSummaryResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    credits: int
    plan: str

class UserSummaryListResponse(BaseModel):
    items: list[UserSummaryResponse]

class SupportThreadSummaryResponse(BaseModel):
    id: int
    user_id: int
    unread_count: int

class SupportThreadSummaryListResponse(BaseModel):
    items: list[SupportThreadSummaryResponse]

class PromptTemplateItemResponse(BaseModel):
    key: str
    content: str

class PromptTemplateListItemResponse(BaseModel):
    items: list[PromptTemplateItemResponse]

class SystemLogItemResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: Optional[str] = None
    score: Optional[float] = None

class SystemLogListResponse(BaseModel):
    items: list[SystemLogItemResponse]

class AdminTransactionResponse(TransactionLogResponse):
    pass

class AdminTransactionListResponse(BaseModel):
    items: list[AdminTransactionResponse]

class AdminHistoryResponse(InterviewHistorySummary):
    pass

class AdminHistoryListResponse(BaseModel):
    items: list[AdminHistoryResponse]

class PromptConfigResponse(BaseModel):
    system_prompt: str
    temperature: float

class MyProfileResponse(BaseModel):
    info: dict
    experiences: list
    educations: list

class ChatHistoryItem(BaseModel):
    role: str
    content: str

class ChatHistoryResponse(BaseModel):
    items: list[ChatHistoryItem]

class InterviewStateResponse(BaseModel):
    status: str

class InterviewAudioResponse(BaseModel):
    audio_url: Optional[str] = None

class ResumeConfigResponse(BaseModel):
    template_id: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None
    style_instruction: Optional[str] = None

class ResumeConfigRequest(BaseModel):
    template_id: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None
    style_instruction: Optional[str] = None

class PublicQuestionResponse(BaseModel):
    id: int
    question: str
    status: str
    answer: Optional[str] = None

    class Config:
        from_attributes = True

class PublicQuestionPageResponse(BaseModel):
    items: list[PublicQuestionResponse]

class AdminTemplatePromptResponse(BaseModel):
    key: str
    content: str

class AdminTemplatePromptListResponse(BaseModel):
    items: list[AdminTemplatePromptResponse]

class AdminSupportMessageResponse(SupportMessageResponse):
    pass

class AdminSupportThreadResponse(BaseModel):
    thread_id: int
    messages: list[AdminSupportMessageResponse]

class AdminSupportThreadListResponse(BaseModel):
    items: list[AdminSupportThreadResponse]

class SystemStatusResponse(BaseModel):
    status: str
    version: Optional[str] = None

class InterviewMetricsResponse(BaseModel):
    providers: list[str]
    fallback_enabled: bool
    proof_points: list[str]

class AIHybridMetricsResponse(BaseModel):
    providers: list[str]
    fallback_enabled: bool
    proof_points: list[str]

class InterviewContextApiResponse(BaseModel):
    interview_context: InterviewContextData

class UserPlanResponse(BaseModel):
    plan: str

class CreditsResponse(BaseModel):
    credits: int

class AdminMessageResponse(BaseModel):
    message: str

class PlanResponse(BaseModel):
    plan: str

class StatusResponse(BaseModel):
    status: str

class MessageResponse(BaseModel):
    message: str

class ErrorResponse(BaseModel):
    detail: str

class SuccessResponse(BaseModel):
    success: bool

class EmptyResponse(BaseModel):
    pass

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    limit: int

class InterviewDetailResponse(BaseModel):
    id: int
    title: str
    details: list

class ConfigValueResponse(BaseModel):
    value: str

class PromptValueResponse(BaseModel):
    value: str

class StatsResponse(BaseModel):
    total: int
    active: int
    pending: int
    completed: int

class BasicUserResponse(BaseModel):
    id: int
    email: str
    full_name: str

class BasicUsersResponse(BaseModel):
    items: list[BasicUserResponse]

class BasicQuestionResponse(BaseModel):
    id: int
    question: str

class BasicQuestionsResponse(BaseModel):
    items: list[BasicQuestionResponse]

class BasicSupportResponse(BaseModel):
    id: int
    message: str

class BasicSupportsResponse(BaseModel):
    items: list[BasicSupportResponse]

class BasicTemplateResponse(BaseModel):
    id: int
    title: str

class BasicTemplatesResponse(BaseModel):
    items: list[BasicTemplateResponse]

class BasicTransactionResponse(BaseModel):
    id: int
    amount: float

class BasicTransactionsResponse(BaseModel):
    items: list[BasicTransactionResponse]

class BasicHistoryResponse(BaseModel):
    id: int
    title: str

class BasicHistoriesResponse(BaseModel):
    items: list[BasicHistoryResponse]

class BasicPromptResponse(BaseModel):
    key: str
    content: str

class BasicPromptsResponse(BaseModel):
    items: list[BasicPromptResponse]

class BasicLogResponse(BaseModel):
    id: int
    title: Optional[str] = None

class BasicLogsResponse(BaseModel):
    items: list[BasicLogResponse]

class ApiOkResponse(BaseModel):
    ok: bool

class ApiErrorResponse(BaseModel):
    error: str

class ApiDataResponse(BaseModel):
    data: dict

class ApiListResponse(BaseModel):
    data: list

class ApiCountResponse(BaseModel):
    count: int

class ApiIdResponse(BaseModel):
    id: int

class ApiTitleResponse(BaseModel):
    title: str

class ApiDetailResponse(BaseModel):
    detail: str

class ApiStatusResponse(BaseModel):
    status: str

class ApiCreditsResponse(BaseModel):
    credits: int

class ApiPlanResponse(BaseModel):
    plan: str

class ApiUnreadResponse(BaseModel):
    unread_count: int

class ApiQuotaResponse(BaseModel):
    remaining: int
    limit: int

class ApiHintResponse(BaseModel):
    hint: str

class ApiTranscribeResponse(BaseModel):
    text: str

class ApiChatResponse(BaseModel):
    content: str

class ApiReportResponse(BaseModel):
    report: dict
    history_id: Optional[int] = None

class ApiReviewResponse(BaseModel):
    review: str

class ApiGenerateResponse(BaseModel):
    content: str

class ApiTailorResponse(BaseModel):
    cv_data: dict
    tailor_summary: dict

class ApiMakeoverResponse(BaseModel):
    cv_data: dict
    extracted_text: str

class ApiContextResponse(BaseModel):
    interview_context: InterviewContextData

class ApiMetricsResponse(BaseModel):
    providers: list[str]
    fallback_enabled: bool
    proof_points: list[str]

class ApiDashboardResponse(BaseModel):
    stats: DashboardStatsResponse
    users: list

class ApiOverviewResponse(BaseModel):
    stats: DashboardStatsResponse
    users: list
    transactions: list[TransactionLogResponse]

class ApiHistoryResponse(BaseModel):
    items: list[InterviewHistorySummary]

class ApiUsersResponse(BaseModel):
    items: list[UserSummaryResponse]

class ApiQuestionsResponse(BaseModel):
    items: list[AdminQuestionResponse]

class ApiTemplatesResponse(BaseModel):
    items: list[TemplateResponse]

class ApiSupportThreadsResponse(BaseModel):
    items: list[SupportThreadSummaryResponse]

class ApiPromptTemplatesResponse(BaseModel):
    items: list[PromptTemplateItemResponse]

class ApiTransactionsResponse(BaseModel):
    items: list[TransactionLogResponse]

class ApiLogsResponse(BaseModel):
    items: list[SystemLogItemResponse]

class ApiProfileResponse(BaseModel):
    info: dict
    experiences: list
    educations: list

class ApiThreadResponse(BaseModel):
    thread_id: int
    messages: list[SupportMessageResponse]

class ApiThreadListResponse(BaseModel):
    items: list[AdminSupportThreadResponse]

class ApiQuestionPageResponse(BaseModel):
    items: list[PublicQuestionResponse]
    total: int
    page: int
    limit: int

class ApiTemplatePromptListResponse(BaseModel):
    items: list[AdminTemplatePromptResponse]

class ApiSystemStatusResponse(BaseModel):
    status: str
    version: Optional[str] = None

class ApiHealthResponse(BaseModel):
    status: str

class ApiInterviewStateResponse(BaseModel):
    status: str

class ApiResumeConfigResponse(BaseModel):
    template_id: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None
    style_instruction: Optional[str] = None

class ApiGenericResponse(BaseModel):
    message: str

class ApiBooleanResponse(BaseModel):
    success: bool

class ApiEmptyResponse(BaseModel):
    pass

class ApiPaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    limit: int

class ApiInterviewDetailResponse(BaseModel):
    id: int
    title: str
    details: list

class ApiConfigValueResponse(BaseModel):
    value: str

class ApiPromptValueResponse(BaseModel):
    value: str

class ApiStatsResponse(BaseModel):
    total: int
    active: int
    pending: int
    completed: int

class ApiBasicUserResponse(BaseModel):
    id: int
    email: str
    full_name: str

class ApiBasicQuestionResponse(BaseModel):
    id: int
    question: str

class ApiBasicSupportResponse(BaseModel):
    id: int
    message: str

class ApiBasicTemplateResponse(BaseModel):
    id: int
    title: str

class ApiBasicTransactionResponse(BaseModel):
    id: int
    amount: float

class ApiBasicHistoryResponse(BaseModel):
    id: int
    title: str

class ApiBasicPromptResponse(BaseModel):
    key: str
    content: str

class ApiBasicLogResponse(BaseModel):
    id: int
    title: Optional[str] = None
    extra_flags: Optional[dict[str, Any]] = None
    extra_runtime: Optional[dict[str, Any]] = None
    extra_trace: Optional[dict[str, Any]] = None
    extra_metrics: Optional[dict[str, Any]] = None
    extra_analysis: Optional[dict[str, Any]] = None
    extra_usage: Optional[dict[str, Any]] = None
    extra_response: Optional[dict[str, Any]] = None
    extra_prompt: Optional[dict[str, Any]] = None
    extra_chat: Optional[dict[str, Any]] = None
    extra_summary: Optional[dict[str, Any]] = None
    extra_history: Optional[dict[str, Any]] = None
    extra_session: Optional[dict[str, Any]] = None
    extra_topic: Optional[dict[str, Any]] = None
    extra_scoring: Optional[dict[str, Any]] = None
    extra_risk: Optional[dict[str, Any]] = None
    extra_quality: Optional[dict[str, Any]] = None
    extra_latency: Optional[dict[str, Any]] = None
    extra_fallback: Optional[dict[str, Any]] = None
    extra_reasoning: Optional[dict[str, Any]] = None
    extra_coaching: Optional[dict[str, Any]] = None
    extra_planner: Optional[dict[str, Any]] = None
    extra_evaluator: Optional[dict[str, Any]] = None
    extra_final_report: Optional[dict[str, Any]] = None
    extra_targets: Optional[List[str]] = None
    extra_goals: Optional[List[str]] = None
    extra_tags: Optional[List[str]] = None
    extra_checkpoints: Optional[List[str]] = None
    extra_decisions: Optional[List[str]] = None
    extra_evidence: Optional[List[dict[str, Any]]] = None
    extra_rubric: Optional[dict[str, Any]] = None
    extra_constraints_text: Optional[str] = None
    extra_summary_text: Optional[str] = None
    extra_notes_text: Optional[str] = None
    extra_final_text: Optional[str] = None
    extra_turn_text: Optional[str] = None
    extra_context_text: Optional[str] = None
    extra_coaching_text: Optional[str] = None
    extra_prompt_text: Optional[str] = None
    extra_reasoning_text: Optional[str] = None
    extra_response_text: Optional[str] = None
    extra_history_text: Optional[str] = None
    extra_session_text: Optional[str] = None
    extra_topic_text: Optional[str] = None
    extra_flags_text: Optional[str] = None
    extra_quality_text: Optional[str] = None
    extra_latency_text: Optional[str] = None
    extra_fallback_text: Optional[str] = None
    extra_usage_text: Optional[str] = None
    extra_analysis_text: Optional[str] = None
    extra_metrics_text: Optional[str] = None
    extra_trace_text: Optional[str] = None
    extra_payload_text: Optional[str] = None
    extra_output_text: Optional[str] = None
    extra_input_text: Optional[str] = None
    extra_debug_text: Optional[str] = None
    extra_plan: Optional[dict[str, Any]] = None
    extra_follow_up_plan: Optional[dict[str, Any]] = None
    extra_turn_context: Optional[dict[str, Any]] = None
    extra_blocks: Optional[List[dict[str, Any]]] = None
    extra_headers: Optional[dict[str, Any]] = None
    extra_attachments: Optional[List[dict[str, Any]]] = None
    extra_diagnostics: Optional[dict[str, Any]] = None
    extra_observations: Optional[dict[str, Any]] = None
    extra_state: Optional[dict[str, Any]] = None
    extra_summary_data: Optional[dict[str, Any]] = None
    extra_context_data: Optional[dict[str, Any]] = None
    extra_evaluation_data: Optional[dict[str, Any]] = None
    extra_coaching_data: Optional[dict[str, Any]] = None
    extra_turn_data: Optional[dict[str, Any]] = None
    extra_session_data: Optional[dict[str, Any]] = None
    extra_history_data: Optional[dict[str, Any]] = None
    extra_request_data: Optional[dict[str, Any]] = None
    extra_response_data: Optional[dict[str, Any]] = None
    extra_model_data: Optional[dict[str, Any]] = None
    extra_usage_data: Optional[dict[str, Any]] = None
    extra_trace_data: Optional[dict[str, Any]] = None
    extra_metrics_data: Optional[dict[str, Any]] = None
    extra_signal_data: Optional[dict[str, Any]] = None
    extra_pipeline_data: Optional[dict[str, Any]] = None
    extra_output_data: Optional[dict[str, Any]] = None
    extra_input_data: Optional[dict[str, Any]] = None
    extra_event_data: Optional[dict[str, Any]] = None
    extra_view_data: Optional[dict[str, Any]] = None
    extra_debug_data: Optional[dict[str, Any]] = None
    extra_route_data: Optional[dict[str, Any]] = None
    extra_header_data: Optional[dict[str, Any]] = None
    extra_attachment_data: Optional[dict[str, Any]] = None
    extra_block_data: Optional[dict[str, Any]] = None
    extra_goal_data: Optional[dict[str, Any]] = None
    extra_target_data: Optional[dict[str, Any]] = None
    extra_tag_data: Optional[dict[str, Any]] = None
    extra_checkpoint_data: Optional[dict[str, Any]] = None
    extra_decision_data: Optional[dict[str, Any]] = None
    extra_observation_data: Optional[dict[str, Any]] = None
    extra_constraint_data: Optional[dict[str, Any]] = None
    extra_rubric_data: Optional[dict[str, Any]] = None
    extra_evidence_data: Optional[List[dict[str, Any]]] = None
    extra_plan_data: Optional[dict[str, Any]] = None
    extra_follow_up_data: Optional[dict[str, Any]] = None
    extra_turn_context_data: Optional[dict[str, Any]] = None
    extra_state_data: Optional[dict[str, Any]] = None
    extra_summary_payload: Optional[dict[str, Any]] = None
    extra_context_payload: Optional[dict[str, Any]] = None
    extra_evaluation_payload: Optional[dict[str, Any]] = None
    extra_coaching_payload: Optional[dict[str, Any]] = None
    extra_turn_payload: Optional[dict[str, Any]] = None
    extra_session_payload: Optional[dict[str, Any]] = None
    extra_history_payload: Optional[dict[str, Any]] = None
    extra_request_payload: Optional[dict[str, Any]] = None
    extra_response_payload: Optional[dict[str, Any]] = None
    extra_model_payload: Optional[dict[str, Any]] = None
    extra_usage_payload: Optional[dict[str, Any]] = None
    extra_trace_payload: Optional[dict[str, Any]] = None
    extra_metrics_payload: Optional[dict[str, Any]] = None
    extra_signal_payload: Optional[dict[str, Any]] = None
    extra_pipeline_payload: Optional[dict[str, Any]] = None
    extra_output_payload: Optional[dict[str, Any]] = None
    extra_input_payload: Optional[dict[str, Any]] = None
    extra_event_payload: Optional[dict[str, Any]] = None
    extra_view_payload: Optional[dict[str, Any]] = None
    extra_debug_payload: Optional[dict[str, Any]] = None
    extra_route_payload: Optional[dict[str, Any]] = None
    extra_header_payload: Optional[dict[str, Any]] = None
    extra_attachment_payload: Optional[List[dict[str, Any]]] = None
    extra_block_payload: Optional[List[dict[str, Any]]] = None
    extra_goal_payload: Optional[List[str]] = None
    extra_target_payload: Optional[List[str]] = None
    extra_tag_payload: Optional[List[str]] = None
    extra_checkpoint_payload: Optional[List[str]] = None
    extra_decision_payload: Optional[List[str]] = None
    extra_observation_payload: Optional[dict[str, Any]] = None
    extra_constraint_payload: Optional[dict[str, Any]] = None
    extra_rubric_payload: Optional[dict[str, Any]] = None
    extra_evidence_payload: Optional[List[dict[str, Any]]] = None
    extra_plan_payload: Optional[dict[str, Any]] = None
    extra_follow_up_payload: Optional[dict[str, Any]] = None
    extra_turn_context_payload: Optional[dict[str, Any]] = None
    extra_state_payload: Optional[dict[str, Any]] = None
    extra_text: Optional[str] = None
    extra_json: Optional[dict[str, Any]] = None
    extra_list: Optional[List[Any]] = None
    extra_bool: Optional[bool] = None
    extra_int: Optional[int] = None
    extra_float: Optional[float] = None
    extra_str_list: Optional[List[str]] = None
    extra_dict_list: Optional[List[dict[str, Any]]] = None
    extra_any_list: Optional[List[Any]] = None
    extra_any_dict: Optional[dict[str, Any]] = None
    extra_context_list: Optional[List[dict[str, Any]]] = None
    extra_signal_list: Optional[List[dict[str, Any]]] = None
    extra_metric_list: Optional[List[dict[str, Any]]] = None
    extra_trace_list: Optional[List[dict[str, Any]]] = None
    extra_event_list: Optional[List[dict[str, Any]]] = None
    extra_view_list: Optional[List[dict[str, Any]]] = None
    extra_debug_list: Optional[List[dict[str, Any]]] = None
    extra_route_list: Optional[List[dict[str, Any]]] = None
    extra_header_list: Optional[List[dict[str, Any]]] = None
    extra_attachment_list: Optional[List[dict[str, Any]]] = None
    extra_block_list: Optional[List[dict[str, Any]]] = None
    extra_goal_list: Optional[List[str]] = None
    extra_target_list: Optional[List[str]] = None
    extra_tag_list: Optional[List[str]] = None
    extra_checkpoint_list: Optional[List[str]] = None
    extra_decision_list: Optional[List[str]] = None
    extra_observation_list: Optional[List[dict[str, Any]]] = None
    extra_constraint_list: Optional[List[dict[str, Any]]] = None
    extra_rubric_list: Optional[List[dict[str, Any]]] = None
    extra_evidence_list: Optional[List[dict[str, Any]]] = None
    extra_plan_list: Optional[List[dict[str, Any]]] = None
    extra_follow_up_list: Optional[List[dict[str, Any]]] = None
    extra_turn_context_list: Optional[List[dict[str, Any]]] = None
    extra_state_list: Optional[List[dict[str, Any]]] = None
    extra_raw: Optional[Any] = None
    extra_blob: Optional[Any] = None
    extra_object: Optional[Any] = None
    extra_field: Optional[Any] = None
    extra_value: Optional[Any] = None
    extra_values: Optional[List[Any]] = None
    extra_map: Optional[dict[str, Any]] = None
    extra_maps: Optional[List[dict[str, Any]]] = None
    extra_item: Optional[Any] = None
    extra_items: Optional[List[Any]] = None
    extra_result: Optional[Any] = None
    extra_results: Optional[List[Any]] = None
    extra_record: Optional[Any] = None
    extra_records: Optional[List[Any]] = None
    extra_entry: Optional[Any] = None
    extra_entries: Optional[List[Any]] = None
    extra_node: Optional[Any] = None
    extra_nodes: Optional[List[Any]] = None
    extra_branch: Optional[Any] = None
    extra_branches: Optional[List[Any]] = None
    extra_leaf: Optional[Any] = None
    extra_leaves: Optional[List[Any]] = None
    extra_flag_value: Optional[bool] = None
    extra_metric_value: Optional[float] = None
    extra_score_value: Optional[float] = None
    extra_count_value: Optional[int] = None
    extra_status_value: Optional[str] = None
    extra_reason_value: Optional[str] = None
    extra_message_value: Optional[str] = None
    extra_code_value: Optional[str] = None
    extra_mode_value: Optional[str] = None
    extra_type_value: Optional[str] = None
    extra_name_value: Optional[str] = None
    extra_id_value: Optional[str] = None
    extra_label_value: Optional[str] = None
    extra_title_value: Optional[str] = None
    extra_description_value: Optional[str] = None
    extra_summary_value: Optional[str] = None
    extra_content_value: Optional[str] = None
    extra_output_value: Optional[str] = None
    extra_input_value: Optional[str] = None
    extra_trace_value: Optional[str] = None
    extra_provider_value: Optional[str] = None
    extra_model_value: Optional[str] = None
    extra_route_value: Optional[str] = None
    extra_pipeline_value: Optional[str] = None
    extra_context_value: Optional[str] = None
    extra_target_value: Optional[str] = None
    extra_topic_value: Optional[str] = None
    extra_goal_value: Optional[str] = None
    extra_tag_value: Optional[str] = None
    extra_checkpoint_value: Optional[str] = None
    extra_decision_value: Optional[str] = None
    extra_observation_value: Optional[str] = None
    extra_constraint_value: Optional[str] = None
    extra_rubric_value: Optional[str] = None
    extra_evidence_value: Optional[str] = None
    extra_plan_value: Optional[str] = None
    extra_follow_up_value: Optional[str] = None
    extra_state_value: Optional[str] = None
    extra_context_builder_value: Optional[str] = None
    extra_evaluator_value: Optional[str] = None
    extra_planner_value: Optional[str] = None
    extra_coaching_value: Optional[str] = None
    extra_interview_value: Optional[str] = None
    extra_system_value: Optional[str] = None
    extra_ui_value: Optional[str] = None
    extra_admin_value: Optional[str] = None
    extra_review_value: Optional[str] = None
    extra_export_value: Optional[str] = None
    extra_analytics_value: Optional[str] = None
    extra_debug_value: Optional[str] = None
    extra_header_value: Optional[str] = None
    extra_attachment_value: Optional[str] = None
    extra_block_value: Optional[str] = None
    extra_payload_value: Optional[str] = None
    extra_response_mode: Optional[str] = None
    extra_low_latency: Optional[bool] = None
    extra_fallback_enabled: Optional[bool] = None
    extra_completed: Optional[bool] = None
    extra_debug_enabled: Optional[bool] = None
    extra_match_score: Optional[float] = None
    extra_current_topic: Optional[str] = None
    extra_current_question: Optional[str] = None
    extra_next_topic: Optional[str] = None
    extra_target_topics: Optional[List[str]] = None
    extra_highlighted_strengths: Optional[List[str]] = None
    extra_skill_gaps: Optional[List[str]] = None
    extra_interview_position: Optional[str] = None
    extra_target_role: Optional[str] = None
    extra_interview_language: Optional[str] = None
    extra_expected_difficulty: Optional[str] = None
    extra_provider_name: Optional[str] = None
    extra_model_name: Optional[str] = None
    extra_latency_ms: Optional[int] = None
    extra_request_id: Optional[str] = None
    extra_route_name: Optional[str] = None
    extra_pipeline_version: Optional[str] = None
    extra_context_source: Optional[str] = None
    extra_history_id: Optional[int] = None
    extra_question_index: Optional[int] = None
    extra_question_limit: Optional[int] = None
    extra_time_limit: Optional[int] = None
    extra_confidence_threshold: Optional[float] = None
    extra_transcript_confidence: Optional[float] = None
    extra_clarity_score: Optional[float] = None
    extra_correctness: Optional[float] = None
    extra_depth: Optional[float] = None
    extra_communication: Optional[float] = None
    extra_low_quality_flag: Optional[bool] = None
    extra_speaking_signal: Optional[str] = None
    extra_prompt_hint: Optional[str] = None
    extra_quality_reason: Optional[str] = None
    extra_resume_text: Optional[str] = None
    extra_jd_summary: Optional[str] = None
    extra_turn_summary: Optional[str] = None
    extra_final_summary: Optional[str] = None
    extra_notes_text_value: Optional[str] = None
    extra_tags_value: Optional[List[str]] = None
    extra_context_text_value: Optional[str] = None
    extra_summary_text_value: Optional[str] = None
    extra_message_text_value: Optional[str] = None
    extra_final_text_value: Optional[str] = None
    extra_route_text_value: Optional[str] = None
    extra_pipeline_text_value: Optional[str] = None
    extra_provider_text_value: Optional[str] = None
    extra_model_text_value: Optional[str] = None
    extra_target_topic_value: Optional[str] = None
    extra_follow_up_hint: Optional[str] = None
    extra_signal_text_value: Optional[str] = None
    extra_metric_text_value: Optional[str] = None
    extra_trace_text_value: Optional[str] = None
    extra_payload_text_value_2: Optional[str] = None
    extra_output_text_value: Optional[str] = None
    extra_input_text_value: Optional[str] = None
    extra_debug_text_value: Optional[str] = None
    extra_admin_text_value: Optional[str] = None
    extra_review_text_value: Optional[str] = None
    extra_export_text_value: Optional[str] = None
    extra_analytics_text_value: Optional[str] = None
    extra_header_text_value: Optional[str] = None
    extra_attachment_text_value: Optional[str] = None
    extra_block_text_value: Optional[str] = None
    extra_plan_text_value: Optional[str] = None
    extra_evidence_text_value: Optional[str] = None
    extra_rubric_text_value: Optional[str] = None
    extra_constraint_text_value_2: Optional[str] = None
    extra_decision_text_value: Optional[str] = None
    extra_observation_text_value_2: Optional[str] = None
    extra_checkpoint_text_value: Optional[str] = None
    extra_goal_text_value: Optional[str] = None
    extra_target_text_value_2: Optional[str] = None
    extra_tag_text_value: Optional[str] = None
    extra_follow_up_text_value: Optional[str] = None
    extra_state_text_value: Optional[str] = None
    extra_context_builder_text_value: Optional[str] = None
    extra_evaluator_text_value: Optional[str] = None
    extra_planner_text_value: Optional[str] = None
    extra_coaching_text_value: Optional[str] = None
    extra_interview_text_value: Optional[str] = None
    extra_system_text_value: Optional[str] = None
    extra_ui_text_value: Optional[str] = None
    extra_context_signal_value: Optional[str] = None
    extra_summary_signal_value: Optional[str] = None
    extra_quality_signal_value: Optional[str] = None
    extra_reasoning_signal_value: Optional[str] = None
    extra_coaching_signal_value: Optional[str] = None
    extra_evaluation_signal_value: Optional[str] = None
    extra_planner_signal_value: Optional[str] = None
    extra_context_builder_signal_value: Optional[str] = None
    extra_trace_signal_value: Optional[str] = None
    extra_metric_signal_value: Optional[str] = None
    extra_usage_signal_value: Optional[str] = None
    extra_response_signal_value: Optional[str] = None
    extra_payload_signal_value: Optional[str] = None
    extra_turn_signal_value: Optional[str] = None
    extra_session_signal_value: Optional[str] = None
    extra_history_signal_value: Optional[str] = None
    extra_event_signal_value: Optional[str] = None
    extra_view_signal_value: Optional[str] = None
    extra_route_signal_value: Optional[str] = None
    extra_header_signal_value: Optional[str] = None
    extra_attachment_signal_value: Optional[str] = None
    extra_block_signal_value: Optional[str] = None
    extra_goal_signal_value: Optional[str] = None
    extra_target_signal_value: Optional[str] = None
    extra_tag_signal_value: Optional[str] = None
    extra_checkpoint_signal_value: Optional[str] = None
    extra_decision_signal_value: Optional[str] = None
    extra_observation_signal_value: Optional[str] = None
    extra_constraint_signal_value: Optional[str] = None
    extra_rubric_signal_value: Optional[str] = None
    extra_evidence_signal_value: Optional[str] = None
    extra_plan_signal_value: Optional[str] = None
    extra_follow_up_signal_value: Optional[str] = None
    extra_state_signal_value: Optional[str] = None
    extra_context_builder_signal_list: Optional[List[str]] = None
    extra_evaluator_signal_list: Optional[List[str]] = None
    extra_planner_signal_list: Optional[List[str]] = None
    extra_coaching_signal_list: Optional[List[str]] = None
    extra_interview_signal_list: Optional[List[str]] = None
    extra_system_signal_list: Optional[List[str]] = None
    extra_ui_signal_list: Optional[List[str]] = None
    extra_final_signal_list: Optional[List[str]] = None
    extra_context_signal_list: Optional[List[str]] = None
    extra_summary_signal_list: Optional[List[str]] = None
    extra_quality_signal_list: Optional[List[str]] = None
    extra_reasoning_signal_list: Optional[List[str]] = None
    extra_evaluation_signal_list: Optional[List[str]] = None
    extra_trace_signal_list: Optional[List[str]] = None
    extra_metric_signal_list: Optional[List[str]] = None
    extra_usage_signal_list: Optional[List[str]] = None
    extra_response_signal_list: Optional[List[str]] = None
    extra_payload_signal_list: Optional[List[str]] = None
    extra_turn_signal_list: Optional[List[str]] = None
    extra_session_signal_list: Optional[List[str]] = None
    extra_history_signal_list: Optional[List[str]] = None
    extra_event_signal_list: Optional[List[str]] = None
    extra_view_signal_list: Optional[List[str]] = None
    extra_route_signal_list: Optional[List[str]] = None
    extra_header_signal_list: Optional[List[str]] = None
    extra_attachment_signal_list: Optional[List[str]] = None
    extra_block_signal_list: Optional[List[str]] = None
    extra_goal_signal_list: Optional[List[str]] = None
    extra_target_signal_list: Optional[List[str]] = None
    extra_tag_signal_list: Optional[List[str]] = None
    extra_checkpoint_signal_list: Optional[List[str]] = None
    extra_decision_signal_list: Optional[List[str]] = None
    extra_observation_signal_list: Optional[List[str]] = None
    extra_constraint_signal_list: Optional[List[str]] = None
    extra_rubric_signal_list: Optional[List[str]] = None
    extra_evidence_signal_list: Optional[List[str]] = None
    extra_plan_signal_list: Optional[List[str]] = None
    extra_follow_up_signal_list: Optional[List[str]] = None
    extra_state_signal_list: Optional[List[str]] = None
    extra_interview_context: Optional[dict[str, Any]] = None
    extra_transcript: Optional[dict[str, Any]] = None
    extra_speaking_signals: Optional[dict[str, Any]] = None
    extra_turn_evaluation: Optional[dict[str, Any]] = None
    extra_analysis: Optional[dict[str, Any]] = None
    extra_usage: Optional[dict[str, Any]] = None
    extra_response_headers: Optional[dict[str, Any]] = None
    extra_trace_id: Optional[str] = None
    extra_response_mode_value: Optional[str] = None
    extra_context_summary_value: Optional[str] = None
    extra_current_question_value: Optional[str] = None
    extra_follow_up_hint_value: Optional[str] = None
    extra_signal_payload: Optional[dict[str, Any]] = None
    extra_route_payload_value: Optional[str] = None
    extra_pipeline_payload_value: Optional[str] = None
    extra_provider_payload_value: Optional[str] = None
    extra_model_payload_value: Optional[str] = None
    extra_target_topic_payload_value: Optional[str] = None
    extra_context_payload_value: Optional[str] = None
    extra_summary_payload_value: Optional[str] = None
    extra_quality_payload_value: Optional[str] = None
    extra_reasoning_payload_value: Optional[str] = None
    extra_coaching_payload_value: Optional[str] = None
    extra_evaluation_payload_value: Optional[str] = None
    extra_planner_payload_value: Optional[str] = None
    extra_context_builder_payload_value: Optional[str] = None
    extra_trace_payload_value: Optional[str] = None
    extra_metric_payload_value: Optional[str] = None
    extra_usage_payload_value: Optional[str] = None
    extra_response_payload_value: Optional[str] = None
    extra_turn_payload_value: Optional[str] = None
    extra_session_payload_value: Optional[str] = None
    extra_history_payload_value: Optional[str] = None
    extra_event_payload_value: Optional[str] = None
    extra_view_payload_value: Optional[str] = None
    extra_header_payload_value: Optional[str] = None
    extra_attachment_payload_value: Optional[str] = None
    extra_block_payload_value: Optional[str] = None
    extra_goal_payload_value: Optional[str] = None
    extra_target_payload_value: Optional[str] = None
    extra_tag_payload_value: Optional[str] = None
    extra_checkpoint_payload_value: Optional[str] = None
    extra_decision_payload_value: Optional[str] = None
    extra_observation_payload_value: Optional[str] = None
    extra_constraint_payload_value: Optional[str] = None
    extra_rubric_payload_value: Optional[str] = None
    extra_evidence_payload_value: Optional[str] = None
    extra_plan_payload_value: Optional[str] = None
    extra_follow_up_payload_value: Optional[str] = None
    extra_state_payload_value: Optional[str] = None
    extra_transcript_payload: Optional[dict[str, Any]] = None
    extra_speaking_payload: Optional[dict[str, Any]] = None
    extra_turn_payload: Optional[dict[str, Any]] = None
    extra_analysis_payload_2: Optional[dict[str, Any]] = None
    extra_usage_payload_2: Optional[dict[str, Any]] = None
    extra_response_headers_payload: Optional[dict[str, Any]] = None
    extra_trace_id_payload: Optional[dict[str, Any]] = None
    extra_context_response: Optional[dict[str, Any]] = None
    extra_structured_analysis: Optional[dict[str, Any]] = None
    extra_structured_usage: Optional[dict[str, Any]] = None
    extra_structured_trace: Optional[dict[str, Any]] = None
    extra_structured_response: Optional[dict[str, Any]] = None
    extra_low_latency_mode: Optional[bool] = None
    extra_audio_meta: Optional[dict[str, Any]] = None
    extra_lang: Optional[str] = None
    extra_mode_value_2: Optional[str] = None
    extra_chat_history: Optional[list] = None
    extra_jd_text: Optional[str] = None
    extra_user_text: Optional[str] = None
    extra_voice_id: Optional[str] = None
    extra_current_topic: Optional[str] = None
    extra_pipeline_state: Optional[dict[str, Any]] = None
    extra_turn_state: Optional[dict[str, Any]] = None
    extra_session_state: Optional[dict[str, Any]] = None
    extra_history_state: Optional[dict[str, Any]] = None
    extra_context_state: Optional[dict[str, Any]] = None
    extra_question_state: Optional[dict[str, Any]] = None
    extra_scoring_state: Optional[dict[str, Any]] = None
    extra_signal_state: Optional[dict[str, Any]] = None
    extra_metric_state: Optional[dict[str, Any]] = None
    extra_trace_state: Optional[dict[str, Any]] = None
    extra_usage_state: Optional[dict[str, Any]] = None
    extra_response_state: Optional[dict[str, Any]] = None
    extra_prompt_state: Optional[dict[str, Any]] = None
    extra_model_state: Optional[dict[str, Any]] = None
    extra_provider_state: Optional[dict[str, Any]] = None
    extra_route_state: Optional[dict[str, Any]] = None
    extra_debug_state: Optional[dict[str, Any]] = None
    extra_admin_state: Optional[dict[str, Any]] = None
    extra_review_state: Optional[dict[str, Any]] = None
    extra_export_state: Optional[dict[str, Any]] = None
    extra_analytics_state: Optional[dict[str, Any]] = None
    extra_header_state: Optional[dict[str, Any]] = None
    extra_attachment_state: Optional[dict[str, Any]] = None
    extra_block_state: Optional[dict[str, Any]] = None
    extra_goal_state: Optional[dict[str, Any]] = None
    extra_target_state: Optional[dict[str, Any]] = None
    extra_tag_state: Optional[dict[str, Any]] = None
    extra_checkpoint_state: Optional[dict[str, Any]] = None
    extra_decision_state: Optional[dict[str, Any]] = None
    extra_observation_state: Optional[dict[str, Any]] = None
    extra_constraint_state: Optional[dict[str, Any]] = None
    extra_rubric_state: Optional[dict[str, Any]] = None
    extra_evidence_state: Optional[dict[str, Any]] = None
    extra_plan_state: Optional[dict[str, Any]] = None
    extra_follow_up_state: Optional[dict[str, Any]] = None
    extra_transcript_state: Optional[dict[str, Any]] = None
    extra_speaking_state: Optional[dict[str, Any]] = None
    extra_turn_eval_state: Optional[dict[str, Any]] = None
    extra_interview_context_state: Optional[dict[str, Any]] = None
    extra_structured_state: Optional[dict[str, Any]] = None
    extra_low_latency_state: Optional[dict[str, Any]] = None
    extra_final_state: Optional[dict[str, Any]] = None
    extra_current_question_state: Optional[dict[str, Any]] = None
    extra_target_topics_state: Optional[dict[str, Any]] = None
    extra_strengths_state: Optional[dict[str, Any]] = None
    extra_gaps_state: Optional[dict[str, Any]] = None
    extra_match_score_state: Optional[dict[str, Any]] = None
    extra_analysis_result: Optional[dict[str, Any]] = None
    extra_usage_result: Optional[dict[str, Any]] = None
    extra_response_result: Optional[dict[str, Any]] = None
    extra_trace_result: Optional[dict[str, Any]] = None
    extra_prompt_result: Optional[dict[str, Any]] = None
    extra_context_result: Optional[dict[str, Any]] = None
    extra_turn_result: Optional[dict[str, Any]] = None
    extra_signal_result: Optional[dict[str, Any]] = None
    extra_metric_result: Optional[dict[str, Any]] = None
    extra_low_latency_result: Optional[dict[str, Any]] = None
    extra_final_result: Optional[dict[str, Any]] = None
    extra_audio_result: Optional[dict[str, Any]] = None
    extra_chat_result: Optional[dict[str, Any]] = None
    extra_model_result: Optional[dict[str, Any]] = None
    extra_provider_result: Optional[dict[str, Any]] = None
    extra_route_result: Optional[dict[str, Any]] = None
    extra_admin_result: Optional[dict[str, Any]] = None
    extra_review_result: Optional[dict[str, Any]] = None
    extra_export_result: Optional[dict[str, Any]] = None
    extra_analytics_result: Optional[dict[str, Any]] = None
    extra_debug_result: Optional[dict[str, Any]] = None
    extra_header_result: Optional[dict[str, Any]] = None
    extra_attachment_result: Optional[dict[str, Any]] = None
    extra_block_result: Optional[dict[str, Any]] = None
    extra_goal_result: Optional[dict[str, Any]] = None
    extra_target_result: Optional[dict[str, Any]] = None
    extra_tag_result: Optional[dict[str, Any]] = None
    extra_checkpoint_result: Optional[dict[str, Any]] = None
    extra_decision_result: Optional[dict[str, Any]] = None
    extra_observation_result: Optional[dict[str, Any]] = None
    extra_constraint_result: Optional[dict[str, Any]] = None
    extra_rubric_result: Optional[dict[str, Any]] = None
    extra_evidence_result: Optional[dict[str, Any]] = None
    extra_plan_result: Optional[dict[str, Any]] = None
    extra_follow_up_result: Optional[dict[str, Any]] = None
    extra_transcript_result: Optional[dict[str, Any]] = None
    extra_speaking_result: Optional[dict[str, Any]] = None
    extra_turn_eval_result: Optional[dict[str, Any]] = None
    extra_interview_context_result: Optional[dict[str, Any]] = None
    extra_structured_result: Optional[dict[str, Any]] = None
    extra_quality_result: Optional[dict[str, Any]] = None
    extra_reasoning_result: Optional[dict[str, Any]] = None
    extra_coaching_result: Optional[dict[str, Any]] = None
    extra_context_builder_result: Optional[dict[str, Any]] = None
    extra_planner_result: Optional[dict[str, Any]] = None
    extra_evaluator_result: Optional[dict[str, Any]] = None
    extra_signal_headers: Optional[dict[str, Any]] = None
    extra_trace_headers: Optional[dict[str, Any]] = None
    extra_usage_headers: Optional[dict[str, Any]] = None
    extra_response_headers_result: Optional[dict[str, Any]] = None
    extra_trace_id_result: Optional[str] = None
    extra_headers_result: Optional[dict[str, Any]] = None
    extra_target_topics_text: Optional[str] = None
    extra_strengths_text: Optional[str] = None
    extra_gaps_text: Optional[str] = None
    extra_match_score_text: Optional[str] = None
    extra_context_response_text: Optional[str] = None
    extra_structured_analysis_text: Optional[str] = None
    extra_structured_usage_text: Optional[str] = None
    extra_structured_trace_text: Optional[str] = None
    extra_structured_response_text: Optional[str] = None
    extra_low_latency_text: Optional[str] = None
    extra_audio_meta_text: Optional[str] = None
    extra_lang_text: Optional[str] = None
    extra_chat_history_text: Optional[str] = None
    extra_jd_text_value: Optional[str] = None
    extra_user_text_value: Optional[str] = None
    extra_voice_id_value: Optional[str] = None
    extra_context_builder_state: Optional[dict[str, Any]] = None
    extra_planner_state: Optional[dict[str, Any]] = None
    extra_evaluator_state: Optional[dict[str, Any]] = None
    extra_coaching_state: Optional[dict[str, Any]] = None
    extra_signal_headers_text: Optional[str] = None
    extra_trace_headers_text: Optional[str] = None
    extra_usage_headers_text: Optional[str] = None
    extra_response_headers_text: Optional[str] = None
    extra_trace_id_text: Optional[str] = None
    extra_headers_text: Optional[str] = None
    extra_context_builder_headers: Optional[dict[str, Any]] = None
    extra_planner_headers: Optional[dict[str, Any]] = None
    extra_evaluator_headers: Optional[dict[str, Any]] = None
    extra_coaching_headers: Optional[dict[str, Any]] = None
    extra_audio_headers: Optional[dict[str, Any]] = None
    extra_chat_headers: Optional[dict[str, Any]] = None
    extra_model_headers: Optional[dict[str, Any]] = None
    extra_provider_headers: Optional[dict[str, Any]] = None
    extra_route_headers: Optional[dict[str, Any]] = None
    extra_pipeline_headers: Optional[dict[str, Any]] = None
    extra_context_headers: Optional[dict[str, Any]] = None
    extra_target_headers: Optional[dict[str, Any]] = None
    extra_goal_headers: Optional[dict[str, Any]] = None
    extra_tag_headers: Optional[dict[str, Any]] = None
    extra_checkpoint_headers: Optional[dict[str, Any]] = None
    extra_decision_headers: Optional[dict[str, Any]] = None
    extra_observation_headers: Optional[dict[str, Any]] = None
    extra_constraint_headers: Optional[dict[str, Any]] = None
    extra_rubric_headers: Optional[dict[str, Any]] = None
    extra_evidence_headers: Optional[dict[str, Any]] = None
    extra_plan_headers: Optional[dict[str, Any]] = None
    extra_follow_up_headers: Optional[dict[str, Any]] = None
    extra_transcript_headers: Optional[dict[str, Any]] = None
    extra_speaking_headers: Optional[dict[str, Any]] = None
    extra_turn_eval_headers: Optional[dict[str, Any]] = None
    extra_interview_context_headers: Optional[dict[str, Any]] = None
    extra_structured_headers: Optional[dict[str, Any]] = None
    extra_quality_headers: Optional[dict[str, Any]] = None
    extra_reasoning_headers: Optional[dict[str, Any]] = None
    extra_signal_headers_result: Optional[dict[str, Any]] = None
    extra_trace_headers_result: Optional[dict[str, Any]] = None
    extra_usage_headers_result: Optional[dict[str, Any]] = None
    extra_context_headers_result: Optional[dict[str, Any]] = None
    extra_target_headers_result: Optional[dict[str, Any]] = None
    extra_goal_headers_result: Optional[dict[str, Any]] = None
    extra_tag_headers_result: Optional[dict[str, Any]] = None
    extra_checkpoint_headers_result: Optional[dict[str, Any]] = None
    extra_decision_headers_result: Optional[dict[str, Any]] = None
    extra_observation_headers_result: Optional[dict[str, Any]] = None
    extra_constraint_headers_result: Optional[dict[str, Any]] = None
    extra_rubric_headers_result: Optional[dict[str, Any]] = None
    extra_evidence_headers_result: Optional[dict[str, Any]] = None
    extra_plan_headers_result: Optional[dict[str, Any]] = None
    extra_follow_up_headers_result: Optional[dict[str, Any]] = None
    extra_transcript_headers_result: Optional[dict[str, Any]] = None
    extra_speaking_headers_result: Optional[dict[str, Any]] = None
    extra_turn_eval_headers_result: Optional[dict[str, Any]] = None
    extra_interview_context_headers_result: Optional[dict[str, Any]] = None
    extra_structured_headers_result: Optional[dict[str, Any]] = None
    extra_quality_headers_result: Optional[dict[str, Any]] = None
    extra_reasoning_headers_result: Optional[dict[str, Any]] = None
    extra_final_headers_result: Optional[dict[str, Any]] = None
    extra_current_question_headers_result: Optional[dict[str, Any]] = None
    extra_target_topics_headers_result: Optional[dict[str, Any]] = None
    extra_strengths_headers_result: Optional[dict[str, Any]] = None
    extra_gaps_headers_result: Optional[dict[str, Any]] = None
    extra_match_score_headers_result: Optional[dict[str, Any]] = None
    extra_context_response_headers_result: Optional[dict[str, Any]] = None
    extra_structured_analysis_headers_result: Optional[dict[str, Any]] = None
    extra_structured_usage_headers_result: Optional[dict[str, Any]] = None
    extra_structured_trace_headers_result: Optional[dict[str, Any]] = None
    extra_structured_response_headers_result: Optional[dict[str, Any]] = None
    extra_low_latency_headers_result: Optional[dict[str, Any]] = None
    extra_audio_meta_headers_result: Optional[dict[str, Any]] = None
    extra_lang_headers_result: Optional[dict[str, Any]] = None
    extra_chat_history_headers_result: Optional[dict[str, Any]] = None
    extra_jd_headers_result: Optional[dict[str, Any]] = None
    extra_user_headers_result: Optional[dict[str, Any]] = None
    extra_voice_headers_result: Optional[dict[str, Any]] = None
    extra_context_builder_headers_result: Optional[dict[str, Any]] = None
    extra_planner_headers_result_2: Optional[dict[str, Any]] = None
    extra_evaluator_headers_result_2: Optional[dict[str, Any]] = None
    extra_coaching_headers_result: Optional[dict[str, Any]] = None
    extra_signal_state_result: Optional[dict[str, Any]] = None
    extra_metric_state_result: Optional[dict[str, Any]] = None
    extra_trace_state_result: Optional[dict[str, Any]] = None
    extra_usage_state_result: Optional[dict[str, Any]] = None
    extra_response_state_result: Optional[dict[str, Any]] = None
    extra_prompt_state_result: Optional[dict[str, Any]] = None
    extra_model_state_result: Optional[dict[str, Any]] = None
    extra_provider_state_result: Optional[dict[str, Any]] = None
    extra_route_state_result: Optional[dict[str, Any]] = None
    extra_context_state_result: Optional[dict[str, Any]] = None
    extra_target_state_result: Optional[dict[str, Any]] = None
    extra_goal_state_result: Optional[dict[str, Any]] = None
    extra_tag_state_result: Optional[dict[str, Any]] = None
    extra_checkpoint_state_result: Optional[dict[str, Any]] = None
    extra_decision_state_result: Optional[dict[str, Any]] = None
    extra_observation_state_result: Optional[dict[str, Any]] = None
    extra_constraint_state_result: Optional[dict[str, Any]] = None
    extra_rubric_state_result: Optional[dict[str, Any]] = None
    extra_evidence_state_result: Optional[dict[str, Any]] = None
    extra_plan_state_result: Optional[dict[str, Any]] = None
    extra_follow_up_state_result: Optional[dict[str, Any]] = None
    extra_transcript_state_result: Optional[dict[str, Any]] = None
    extra_speaking_state_result: Optional[dict[str, Any]] = None
    extra_turn_eval_state_result: Optional[dict[str, Any]] = None
    extra_interview_context_state_result: Optional[dict[str, Any]] = None
    extra_structured_state_result: Optional[dict[str, Any]] = None
    extra_quality_state_result: Optional[dict[str, Any]] = None
    extra_reasoning_state_result: Optional[dict[str, Any]] = None
    extra_final_state_result: Optional[dict[str, Any]] = None
    extra_current_question_state_result: Optional[dict[str, Any]] = None
    extra_target_topics_state_result: Optional[dict[str, Any]] = None
    extra_strengths_state_result: Optional[dict[str, Any]] = None
    extra_gaps_state_result: Optional[dict[str, Any]] = None
    extra_match_score_state_result: Optional[dict[str, Any]] = None
    extra_context_response_state_result: Optional[dict[str, Any]] = None
    extra_structured_analysis_state_result: Optional[dict[str, Any]] = None
    extra_structured_usage_state_result: Optional[dict[str, Any]] = None
    extra_structured_trace_state_result: Optional[dict[str, Any]] = None
    extra_structured_response_state_result: Optional[dict[str, Any]] = None
    extra_low_latency_state_result: Optional[dict[str, Any]] = None
    extra_audio_meta_state_result: Optional[dict[str, Any]] = None
    extra_lang_state_result: Optional[dict[str, Any]] = None
    extra_chat_history_state_result: Optional[dict[str, Any]] = None
    extra_jd_state_result: Optional[dict[str, Any]] = None
    extra_user_state_result: Optional[dict[str, Any]] = None
    extra_voice_state_result: Optional[dict[str, Any]] = None
    extra_context_builder_state_result: Optional[dict[str, Any]] = None
    extra_planner_state_result_2: Optional[dict[str, Any]] = None
    extra_evaluator_state_result_2: Optional[dict[str, Any]] = None
    extra_coaching_state_result: Optional[dict[str, Any]] = None
    extra_signal_state_text: Optional[str] = None
    extra_metric_state_text: Optional[str] = None
    extra_trace_state_text: Optional[str] = None
    extra_usage_state_text: Optional[str] = None
    extra_response_state_text: Optional[str] = None
    extra_prompt_state_text: Optional[str] = None
    extra_model_state_text: Optional[str] = None
    extra_provider_state_text: Optional[str] = None
    extra_route_state_text: Optional[str] = None
    extra_context_state_text: Optional[str] = None
    extra_target_state_text: Optional[str] = None
    extra_goal_state_text: Optional[str] = None
    extra_tag_state_text: Optional[str] = None
    extra_checkpoint_state_text: Optional[str] = None
    extra_decision_state_text: Optional[str] = None
    extra_observation_state_text: Optional[str] = None
    extra_constraint_state_text: Optional[str] = None
    extra_rubric_state_text: Optional[str] = None
    extra_evidence_state_text: Optional[str] = None
    extra_plan_state_text: Optional[str] = None
    extra_follow_up_state_text: Optional[str] = None
    extra_transcript_state_text: Optional[str] = None
    extra_speaking_state_text: Optional[str] = None
    extra_turn_eval_state_text: Optional[str] = None
    extra_interview_context_state_text: Optional[str] = None
    extra_structured_state_text: Optional[str] = None
    extra_quality_state_text: Optional[str] = None
    extra_reasoning_state_text: Optional[str] = None
    extra_final_state_text: Optional[str] = None
    extra_current_question_state_text: Optional[str] = None
    extra_target_topics_state_text: Optional[str] = None
    extra_strengths_state_text: Optional[str] = None
    extra_gaps_state_text: Optional[str] = None
    extra_match_score_state_text: Optional[str] = None
    extra_context_response_state_text: Optional[str] = None
    extra_structured_analysis_state_text: Optional[str] = None
    extra_structured_usage_state_text: Optional[str] = None
    extra_structured_trace_state_text: Optional[str] = None
    extra_structured_response_state_text: Optional[str] = None
    extra_low_latency_state_text: Optional[str] = None
    extra_audio_meta_state_text: Optional[str] = None
    extra_lang_state_text: Optional[str] = None
    extra_chat_history_state_text: Optional[str] = None
    extra_jd_state_text: Optional[str] = None
    extra_user_state_text: Optional[str] = None
    extra_voice_state_text: Optional[str] = None
    extra_context_builder_state_text: Optional[str] = None
    extra_planner_state_text_2: Optional[str] = None
    extra_evaluator_state_text_2: Optional[str] = None
    extra_coaching_state_text: Optional[str] = None
    extra_score_breakdown: Optional[dict[str, Any]] = None
    extra_score_breakdown_text: Optional[str] = None
    extra_score_breakdown_state: Optional[dict[str, Any]] = None
    extra_score_breakdown_result: Optional[dict[str, Any]] = None
    extra_score_breakdown_payload: Optional[dict[str, Any]] = None
    extra_score_breakdown_headers: Optional[dict[str, Any]] = None
    extra_score_breakdown_headers_result: Optional[dict[str, Any]] = None
    extra_score_breakdown_state_result: Optional[dict[str, Any]] = None
    extra_score_breakdown_state_text: Optional[str] = None
    extra_trace_headers_state: Optional[dict[str, Any]] = None
    extra_usage_headers_state: Optional[dict[str, Any]] = None
    extra_response_headers_state: Optional[dict[str, Any]] = None
    extra_trace_id_state: Optional[dict[str, Any]] = None
    extra_trace_id_headers: Optional[dict[str, Any]] = None
    extra_trace_id_headers_result: Optional[dict[str, Any]] = None
    extra_trace_id_state_result: Optional[dict[str, Any]] = None
    extra_trace_id_state_text: Optional[str] = None
    extra_usage_headers_state_result: Optional[dict[str, Any]] = None
    extra_usage_headers_state_text: Optional[str] = None
    extra_response_headers_state_result: Optional[dict[str, Any]] = None
    extra_response_headers_state_text: Optional[str] = None
    extra_trace_headers_state_result: Optional[dict[str, Any]] = None
    extra_trace_headers_state_text: Optional[str] = None
    extra_message: Optional[str] = None
    extra_messages: Optional[List[str]] = None
    extra_message_list: Optional[List[str]] = None
    extra_response_message: Optional[str] = None
    extra_response_messages: Optional[List[str]] = None
    extra_prompt_messages: Optional[List[str]] = None
    extra_history_messages: Optional[List[str]] = None
    extra_context_messages: Optional[List[str]] = None
    extra_turn_messages: Optional[List[str]] = None
    extra_signal_messages: Optional[List[str]] = None
    extra_metric_messages: Optional[List[str]] = None
    extra_trace_messages: Optional[List[str]] = None
    extra_usage_messages: Optional[List[str]] = None
    extra_output_messages: Optional[List[str]] = None
    extra_input_messages: Optional[List[str]] = None
    extra_debug_messages: Optional[List[str]] = None
    extra_admin_messages: Optional[List[str]] = None
    extra_review_messages: Optional[List[str]] = None
    extra_export_messages: Optional[List[str]] = None
    extra_analytics_messages: Optional[List[str]] = None
    extra_event_messages: Optional[List[str]] = None
    extra_view_messages: Optional[List[str]] = None
    extra_route_messages: Optional[List[str]] = None
    extra_header_messages: Optional[List[str]] = None
    extra_attachment_messages: Optional[List[str]] = None
    extra_block_messages: Optional[List[str]] = None
    extra_goal_messages: Optional[List[str]] = None
    extra_target_messages: Optional[List[str]] = None
    extra_tag_messages: Optional[List[str]] = None
    extra_checkpoint_messages: Optional[List[str]] = None
    extra_decision_messages: Optional[List[str]] = None
    extra_observation_messages: Optional[List[str]] = None
    extra_constraint_messages: Optional[List[str]] = None
    extra_rubric_messages: Optional[List[str]] = None
    extra_evidence_messages: Optional[List[str]] = None
    extra_plan_messages: Optional[List[str]] = None
    extra_follow_up_messages: Optional[List[str]] = None
    extra_state_messages: Optional[List[str]] = None
    extra_context_builder_messages: Optional[List[str]] = None
    extra_planner_messages: Optional[List[str]] = None
    extra_evaluator_messages: Optional[List[str]] = None
    extra_coaching_messages: Optional[List[str]] = None
    extra_interview_messages: Optional[List[str]] = None
    extra_system_messages: Optional[List[str]] = None
    extra_ui_messages: Optional[List[str]] = None
    extra_final_messages: Optional[List[str]] = None
    extra_signal_notes: Optional[List[str]] = None
    extra_quality_notes: Optional[List[str]] = None
    extra_reasoning_notes: Optional[List[str]] = None
    extra_coaching_notes: Optional[List[str]] = None
    extra_evaluation_notes: Optional[List[str]] = None
    extra_context_notes: Optional[List[str]] = None
    extra_summary_notes: Optional[List[str]] = None
    extra_debug_notes: Optional[List[str]] = None
    extra_trace_notes: Optional[List[str]] = None
    extra_usage_notes: Optional[List[str]] = None
    extra_metric_notes: Optional[List[str]] = None
    extra_output_notes: Optional[List[str]] = None
    extra_input_notes: Optional[List[str]] = None
    extra_response_notes: Optional[List[str]] = None
    extra_prompt_notes: Optional[List[str]] = None
    extra_history_notes: Optional[List[str]] = None
    extra_session_notes: Optional[List[str]] = None
    extra_event_notes: Optional[List[str]] = None
    extra_view_notes: Optional[List[str]] = None
    extra_route_notes: Optional[List[str]] = None
    extra_header_notes: Optional[List[str]] = None
    extra_attachment_notes: Optional[List[str]] = None
    extra_block_notes: Optional[List[str]] = None
    extra_goal_notes: Optional[List[str]] = None
    extra_target_notes: Optional[List[str]] = None
    extra_tag_notes: Optional[List[str]] = None
    extra_checkpoint_notes: Optional[List[str]] = None
    extra_decision_notes: Optional[List[str]] = None
    extra_observation_notes: Optional[List[str]] = None
    extra_constraint_notes: Optional[List[str]] = None
    extra_rubric_notes: Optional[List[str]] = None
    extra_evidence_notes: Optional[List[str]] = None
    extra_plan_notes: Optional[List[str]] = None
    extra_follow_up_notes: Optional[List[str]] = None
    extra_state_notes: Optional[List[str]] = None
    extra_context_builder_notes: Optional[List[str]] = None
    extra_planner_notes: Optional[List[str]] = None
    extra_evaluator_notes: Optional[List[str]] = None
    extra_interview_notes: Optional[List[str]] = None
    extra_system_notes: Optional[List[str]] = None
    extra_ui_notes: Optional[List[str]] = None
    extra_final_notes: Optional[List[str]] = None
    extra_signal_debug: Optional[dict[str, Any]] = None
    extra_quality_debug: Optional[dict[str, Any]] = None
    extra_reasoning_debug: Optional[dict[str, Any]] = None
    extra_coaching_debug: Optional[dict[str, Any]] = None
    extra_evaluation_debug: Optional[dict[str, Any]] = None
    extra_context_debug: Optional[dict[str, Any]] = None
    extra_summary_debug: Optional[dict[str, Any]] = None
    extra_trace_debug: Optional[dict[str, Any]] = None
    extra_usage_debug: Optional[dict[str, Any]] = None
    extra_metric_debug: Optional[dict[str, Any]] = None
    extra_output_debug: Optional[dict[str, Any]] = None
    extra_input_debug: Optional[dict[str, Any]] = None
    extra_response_debug: Optional[dict[str, Any]] = None
    extra_prompt_debug: Optional[dict[str, Any]] = None
    extra_history_debug: Optional[dict[str, Any]] = None
    extra_session_debug: Optional[dict[str, Any]] = None
    extra_event_debug: Optional[dict[str, Any]] = None
    extra_view_debug: Optional[dict[str, Any]] = None
    extra_route_debug: Optional[dict[str, Any]] = None
    extra_header_debug: Optional[dict[str, Any]] = None
    extra_attachment_debug: Optional[dict[str, Any]] = None
    extra_block_debug: Optional[dict[str, Any]] = None
    extra_goal_debug: Optional[dict[str, Any]] = None
    extra_target_debug: Optional[dict[str, Any]] = None
    extra_tag_debug: Optional[dict[str, Any]] = None
    extra_checkpoint_debug: Optional[dict[str, Any]] = None
    extra_decision_debug: Optional[dict[str, Any]] = None
    extra_observation_debug: Optional[dict[str, Any]] = None
    extra_constraint_debug: Optional[dict[str, Any]] = None
    extra_rubric_debug: Optional[dict[str, Any]] = None
    extra_evidence_debug: Optional[dict[str, Any]] = None
    extra_plan_debug: Optional[dict[str, Any]] = None
    extra_follow_up_debug: Optional[dict[str, Any]] = None
    extra_state_debug: Optional[dict[str, Any]] = None
    extra_context_builder_debug: Optional[dict[str, Any]] = None
    extra_planner_debug: Optional[dict[str, Any]] = None
    extra_evaluator_debug: Optional[dict[str, Any]] = None
    extra_interview_debug: Optional[dict[str, Any]] = None
    extra_system_debug: Optional[dict[str, Any]] = None
    extra_ui_debug: Optional[dict[str, Any]] = None
    extra_final_debug: Optional[dict[str, Any]] = None
    extra_signal_summary: Optional[dict[str, Any]] = None
    extra_quality_summary: Optional[dict[str, Any]] = None
    extra_reasoning_summary: Optional[dict[str, Any]] = None
    extra_coaching_summary: Optional[dict[str, Any]] = None
    extra_evaluation_summary: Optional[dict[str, Any]] = None
    extra_context_summary_data: Optional[dict[str, Any]] = None
    extra_trace_summary: Optional[dict[str, Any]] = None
    extra_usage_summary: Optional[dict[str, Any]] = None
    extra_metric_summary: Optional[dict[str, Any]] = None
    extra_output_summary: Optional[dict[str, Any]] = None
    extra_input_summary: Optional[dict[str, Any]] = None
    extra_response_summary: Optional[dict[str, Any]] = None
    extra_prompt_summary: Optional[dict[str, Any]] = None
    extra_history_summary: Optional[dict[str, Any]] = None
    extra_session_summary: Optional[dict[str, Any]] = None
    extra_event_summary: Optional[dict[str, Any]] = None
    extra_view_summary: Optional[dict[str, Any]] = None
    extra_route_summary: Optional[dict[str, Any]] = None
    extra_header_summary: Optional[dict[str, Any]] = None
    extra_attachment_summary: Optional[dict[str, Any]] = None
    extra_block_summary: Optional[dict[str, Any]] = None
    extra_goal_summary: Optional[dict[str, Any]] = None
    extra_target_summary: Optional[dict[str, Any]] = None
    extra_tag_summary: Optional[dict[str, Any]] = None
    extra_checkpoint_summary: Optional[dict[str, Any]] = None
    extra_decision_summary: Optional[dict[str, Any]] = None
    extra_observation_summary: Optional[dict[str, Any]] = None
    extra_constraint_summary: Optional[dict[str, Any]] = None
    extra_rubric_summary: Optional[dict[str, Any]] = None
    extra_evidence_summary: Optional[dict[str, Any]] = None
    extra_plan_summary: Optional[dict[str, Any]] = None
    extra_follow_up_summary: Optional[dict[str, Any]] = None
    extra_state_summary: Optional[dict[str, Any]] = None
    extra_context_builder_summary: Optional[dict[str, Any]] = None
    extra_planner_summary: Optional[dict[str, Any]] = None
    extra_evaluator_summary: Optional[dict[str, Any]] = None
    extra_interview_summary: Optional[dict[str, Any]] = None
    extra_system_summary: Optional[dict[str, Any]] = None
    extra_ui_summary: Optional[dict[str, Any]] = None
    extra_final_summary_data: Optional[dict[str, Any]] = None
    turn_history_summary: Optional[str] = None
    context_builder_output: Optional[dict[str, Any]] = None
    turn_evaluator_output: Optional[dict[str, Any]] = None
    coaching_output: Optional[dict[str, Any]] = None
    planner_output: Optional[dict[str, Any]] = None
    system_output: Optional[dict[str, Any]] = None
    interview_output: Optional[dict[str, Any]] = None
    ui_output: Optional[dict[str, Any]] = None
    admin_output: Optional[dict[str, Any]] = None
    review_output: Optional[dict[str, Any]] = None
    export_output: Optional[dict[str, Any]] = None
    analytics_output: Optional[dict[str, Any]] = None
    debug_output: Optional[dict[str, Any]] = None
    response_headers: Optional[dict[str, Any]] = None
    attachments: Optional[List[dict[str, Any]]] = None
    context_payload: Optional[dict[str, Any]] = None
    planning_payload: Optional[dict[str, Any]] = None
    evaluation_payload: Optional[dict[str, Any]] = None
    coaching_payload: Optional[dict[str, Any]] = None
    reporting_payload: Optional[dict[str, Any]] = None
    metrics_payload: Optional[dict[str, Any]] = None
    trace_payload: Optional[dict[str, Any]] = None
    analysis_payload: Optional[dict[str, Any]] = None
    usage_payload: Optional[dict[str, Any]] = None
    response_payload: Optional[dict[str, Any]] = None
    prompt_payload: Optional[dict[str, Any]] = None
    chat_payload: Optional[dict[str, Any]] = None
    extra: Optional[dict[str, Any]] = None
    extra_data: Optional[dict[str, Any]] = None
    extra_context: Optional[dict[str, Any]] = None
    extra_signals: Optional[dict[str, Any]] = None
    extra_outputs: Optional[dict[str, Any]] = None
    extra_inputs: Optional[dict[str, Any]] = None
    extra_metadata: Optional[dict[str, Any]] = None
    extra_notes: Optional[dict[str, Any]] = None
    extra_flags: Optional[dict[str, Any]] = None
    extra_runtime: Optional[dict[str, Any]] = None
    extra_trace: Optional[dict[str, Any]] = None
    extra_metrics: Optional[dict[str, Any]] = None
    extra_analysis: Optional[dict[str, Any]] = None
    extra_usage: Optional[dict[str, Any]] = None
    extra_response: Optional[dict[str, Any]] = None
    extra_prompt: Optional[dict[str, Any]] = None
    extra_chat: Optional[dict[str, Any]] = None
    extra_payload: Optional[dict[str, Any]] = None
    extra_summary: Optional[dict[str, Any]] = None
    extra_history: Optional[dict[str, Any]] = None
    extra_session: Optional[dict[str, Any]] = None
    extra_topic: Optional[dict[str, Any]] = None
    extra_scoring: Optional[dict[str, Any]] = None
    extra_risk: Optional[dict[str, Any]] = None
    extra_quality: Optional[dict[str, Any]] = None
    extra_latency: Optional[dict[str, Any]] = None
    extra_fallback: Optional[dict[str, Any]] = None
    extra_reasoning: Optional[dict[str, Any]] = None
    extra_coaching: Optional[dict[str, Any]] = None
    extra_planner: Optional[dict[str, Any]] = None
    extra_evaluator: Optional[dict[str, Any]] = None
    extra_context_builder: Optional[dict[str, Any]] = None
    extra_final_report: Optional[dict[str, Any]] = None
    extra_ui: Optional[dict[str, Any]] = None
    extra_admin: Optional[dict[str, Any]] = None
    extra_review: Optional[dict[str, Any]] = None
    extra_export: Optional[dict[str, Any]] = None
    extra_analytics: Optional[dict[str, Any]] = None
    extra_debug: Optional[dict[str, Any]] = None
    extra_headers: Optional[dict[str, Any]] = None
    extra_attachments: Optional[List[dict[str, Any]]] = None
    extra_blocks: Optional[List[dict[str, Any]]] = None
    extra_targets: Optional[List[str]] = None
    extra_goals: Optional[List[str]] = None
    extra_tags: Optional[List[str]] = None
    extra_checkpoints: Optional[List[str]] = None
    extra_decisions: Optional[List[str]] = None
    extra_evidence: Optional[List[dict[str, Any]]] = None
    extra_rubric: Optional[dict[str, Any]] = None
    extra_constraints: Optional[dict[str, Any]] = None
    extra_diagnostics: Optional[dict[str, Any]] = None
    extra_observations: Optional[dict[str, Any]] = None
    extra_plan: Optional[dict[str, Any]] = None
    extra_follow_up_plan: Optional[dict[str, Any]] = None
    extra_turn_context: Optional[dict[str, Any]] = None
    extra_summary_text: Optional[str] = None
    extra_notes_text: Optional[str] = None
    extra_final_text: Optional[str] = None
    extra_turn_text: Optional[str] = None
    extra_context_text: Optional[str] = None
    extra_coaching_text: Optional[str] = None
    extra_prompt_text: Optional[str] = None
    extra_reasoning_text: Optional[str] = None
    extra_response_text: Optional[str] = None
    extra_history_text: Optional[str] = None
    extra_session_text: Optional[str] = None
    extra_topic_text: Optional[str] = None
    extra_flags_text: Optional[str] = None
    extra_quality_text: Optional[str] = None
    extra_latency_text: Optional[str] = None
    extra_fallback_text: Optional[str] = None
    extra_usage_text: Optional[str] = None
    extra_analysis_text: Optional[str] = None
    extra_metrics_text: Optional[str] = None
    extra_trace_text: Optional[str] = None
    extra_payload_text: Optional[str] = None
    extra_output_text: Optional[str] = None
    extra_input_text: Optional[str] = None
    extra_debug_text: Optional[str] = None
    extra_admin_text: Optional[str] = None
    extra_review_text: Optional[str] = None
    extra_export_text: Optional[str] = None
    extra_analytics_text: Optional[str] = None
    extra_header_text: Optional[str] = None
    extra_attachment_text: Optional[str] = None
    extra_block_text: Optional[str] = None
    extra_goal_text: Optional[str] = None
    extra_target_text: Optional[str] = None
    extra_tag_text: Optional[str] = None
    extra_checkpoint_text: Optional[str] = None
    extra_decision_text: Optional[str] = None
    extra_observation_text: Optional[str] = None
    extra_constraint_text: Optional[str] = None
    extra_rubric_text: Optional[str] = None
    extra_evidence_text: Optional[str] = None
    extra_plan_text: Optional[str] = None
    extra_follow_up_text: Optional[str] = None
    extra_turn_context_text: Optional[str] = None
    extra_context_builder_text: Optional[str] = None
    extra_evaluator_text: Optional[str] = None
    extra_planner_text: Optional[str] = None
    extra_coaching_summary_text: Optional[str] = None
    extra_interview_output_text: Optional[str] = None
    extra_system_output_text: Optional[str] = None
    extra_ui_output_text: Optional[str] = None
    extra_admin_output_text: Optional[str] = None
    extra_review_output_text: Optional[str] = None
    extra_export_output_text: Optional[str] = None
    extra_analytics_output_text: Optional[str] = None
    extra_debug_output_text: Optional[str] = None
    extra_headers_output_text: Optional[str] = None
    extra_attachments_output_text: Optional[str] = None
    extra_blocks_output_text: Optional[str] = None
    extra_targets_output_text: Optional[str] = None
    extra_goals_output_text: Optional[str] = None
    extra_tags_output_text: Optional[str] = None
    extra_checkpoints_output_text: Optional[str] = None
    extra_decisions_output_text: Optional[str] = None
    extra_observations_output_text: Optional[str] = None
    extra_constraints_output_text: Optional[str] = None
    extra_rubric_output_text: Optional[str] = None
    extra_evidence_output_text: Optional[str] = None
    extra_plan_output_text: Optional[str] = None
    extra_follow_up_output_text: Optional[str] = None
    extra_turn_context_output_text: Optional[str] = None
    extra_context_builder_output_text: Optional[str] = None
    extra_evaluator_output_text: Optional[str] = None
    extra_planner_output_text: Optional[str] = None
    extra_coaching_summary_output_text: Optional[str] = None
    extra_interview_context: Optional[dict[str, Any]] = None
    extra_interview_context_text: Optional[str] = None
    extra_interview_context_output_text: Optional[str] = None
    extra_interview_context_payload: Optional[dict[str, Any]] = None
    extra_interview_context_signals: Optional[dict[str, Any]] = None
    extra_interview_context_metrics: Optional[dict[str, Any]] = None
    extra_interview_context_trace: Optional[dict[str, Any]] = None
    extra_interview_context_analysis: Optional[dict[str, Any]] = None
    extra_interview_context_usage: Optional[dict[str, Any]] = None
    extra_interview_context_response: Optional[dict[str, Any]] = None
    extra_interview_context_prompt: Optional[dict[str, Any]] = None
    extra_interview_context_chat: Optional[dict[str, Any]] = None
    extra_interview_context_summary: Optional[dict[str, Any]] = None
    extra_interview_context_history: Optional[dict[str, Any]] = None
    extra_interview_context_session: Optional[dict[str, Any]] = None
    extra_interview_context_topic: Optional[dict[str, Any]] = None
    extra_interview_context_scoring: Optional[dict[str, Any]] = None
    extra_interview_context_risk: Optional[dict[str, Any]] = None
    extra_interview_context_quality: Optional[dict[str, Any]] = None
    extra_interview_context_latency: Optional[dict[str, Any]] = None
    extra_interview_context_fallback: Optional[dict[str, Any]] = None
    extra_interview_context_reasoning: Optional[dict[str, Any]] = None
    extra_interview_context_coaching: Optional[dict[str, Any]] = None
    extra_interview_context_planner: Optional[dict[str, Any]] = None
    extra_interview_context_evaluator: Optional[dict[str, Any]] = None
    extra_interview_context_context_builder: Optional[dict[str, Any]] = None
    extra_interview_context_final_report: Optional[dict[str, Any]] = None
    extra_interview_context_ui: Optional[dict[str, Any]] = None
    extra_interview_context_admin: Optional[dict[str, Any]] = None
    extra_interview_context_review: Optional[dict[str, Any]] = None
    extra_interview_context_export: Optional[dict[str, Any]] = None
    extra_interview_context_analytics: Optional[dict[str, Any]] = None
    extra_interview_context_debug: Optional[dict[str, Any]] = None
    extra_interview_context_headers: Optional[dict[str, Any]] = None
    extra_interview_context_attachments: Optional[List[dict[str, Any]]] = None
    extra_interview_context_blocks: Optional[List[dict[str, Any]]] = None
    extra_interview_context_targets: Optional[List[str]] = None
    extra_interview_context_goals: Optional[List[str]] = None
    extra_interview_context_tags: Optional[List[str]] = None
    extra_interview_context_checkpoints: Optional[List[str]] = None
    extra_interview_context_decisions: Optional[List[str]] = None
    extra_interview_context_observations: Optional[dict[str, Any]] = None
    extra_interview_context_constraints: Optional[dict[str, Any]] = None
    extra_interview_context_rubric: Optional[dict[str, Any]] = None
    extra_interview_context_evidence: Optional[List[dict[str, Any]]] = None
    extra_interview_context_plan: Optional[dict[str, Any]] = None
    extra_interview_context_follow_up_plan: Optional[dict[str, Any]] = None
    extra_interview_context_turn_context: Optional[dict[str, Any]] = None
    extra_interview_context_summary_text: Optional[str] = None
    extra_interview_context_notes_text: Optional[str] = None
    extra_interview_context_final_text: Optional[str] = None
    extra_interview_context_turn_text: Optional[str] = None
    extra_interview_context_context_text: Optional[str] = None
    extra_interview_context_coaching_text: Optional[str] = None
    extra_interview_context_prompt_text: Optional[str] = None
    extra_interview_context_reasoning_text: Optional[str] = None
    extra_interview_context_response_text: Optional[str] = None
    extra_interview_context_history_text: Optional[str] = None
    extra_interview_context_session_text: Optional[str] = None
    extra_interview_context_topic_text: Optional[str] = None
    extra_interview_context_flags_text: Optional[str] = None
    extra_interview_context_quality_text: Optional[str] = None
    extra_interview_context_latency_text: Optional[str] = None
    extra_interview_context_fallback_text: Optional[str] = None
    extra_interview_context_usage_text: Optional[str] = None
    extra_interview_context_analysis_text: Optional[str] = None
    extra_interview_context_metrics_text: Optional[str] = None
    extra_interview_context_trace_text: Optional[str] = None
    extra_interview_context_payload_text: Optional[str] = None
    extra_interview_context_output_text: Optional[str] = None
    extra_interview_context_input_text: Optional[str] = None
    extra_interview_context_debug_text: Optional[str] = None
    extra_interview_context_admin_text: Optional[str] = None
    extra_interview_context_review_text: Optional[str] = None
    extra_interview_context_export_text: Optional[str] = None
    extra_interview_context_analytics_text: Optional[str] = None
    extra_interview_context_header_text: Optional[str] = None
    extra_interview_context_attachment_text: Optional[str] = None
    extra_interview_context_block_text: Optional[str] = None
    extra_interview_context_goal_text: Optional[str] = None
    extra_interview_context_target_text: Optional[str] = None
    extra_interview_context_tag_text: Optional[str] = None
    extra_interview_context_checkpoint_text: Optional[str] = None
    extra_interview_context_decision_text: Optional[str] = None
    extra_interview_context_observation_text: Optional[str] = None
    extra_interview_context_constraint_text: Optional[str] = None
    extra_interview_context_rubric_text: Optional[str] = None
    extra_interview_context_evidence_text: Optional[str] = None
    extra_interview_context_plan_text: Optional[str] = None
    extra_interview_context_follow_up_text: Optional[str] = None
    extra_interview_context_turn_context_text: Optional[str] = None
    extra_interview_context_context_builder_text: Optional[str] = None
    extra_interview_context_evaluator_text: Optional[str] = None
    extra_interview_context_planner_text: Optional[str] = None
    extra_interview_context_coaching_summary_text: Optional[str] = None
    extra_interview_context_interview_output_text: Optional[str] = None
    extra_interview_context_system_output_text: Optional[str] = None
    extra_interview_context_ui_output_text: Optional[str] = None
    extra_interview_context_admin_output_text: Optional[str] = None
    extra_interview_context_review_output_text: Optional[str] = None
    extra_interview_context_export_output_text: Optional[str] = None
    extra_interview_context_analytics_output_text: Optional[str] = None
    extra_interview_context_debug_output_text: Optional[str] = None
    extra_interview_context_headers_output_text: Optional[str] = None
    extra_interview_context_attachments_output_text: Optional[str] = None
    extra_interview_context_blocks_output_text: Optional[str] = None
    extra_interview_context_targets_output_text: Optional[str] = None
    extra_interview_context_goals_output_text: Optional[str] = None
    extra_interview_context_tags_output_text: Optional[str] = None
    extra_interview_context_checkpoints_output_text: Optional[str] = None
    extra_interview_context_decisions_output_text: Optional[str] = None
    extra_interview_context_observations_output_text: Optional[str] = None
    extra_interview_context_constraints_output_text: Optional[str] = None
    extra_interview_context_rubric_output_text: Optional[str] = None
    extra_interview_context_evidence_output_text: Optional[str] = None
    extra_interview_context_plan_output_text: Optional[str] = None
    extra_interview_context_follow_up_output_text: Optional[str] = None
    extra_interview_context_turn_context_output_text: Optional[str] = None
    extra_interview_context_context_builder_output_text: Optional[str] = None
    extra_interview_context_evaluator_output_text: Optional[str] = None
    extra_interview_context_planner_output_text: Optional[str] = None
    extra_interview_context_coaching_summary_output_text: Optional[str] = None
    extra_interview_context_interview_context: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_text: Optional[str] = None
    extra_interview_context_interview_context_output_text: Optional[str] = None
    extra_interview_context_interview_context_payload: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_signals: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_metrics: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_trace: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_analysis: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_usage: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_response: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_prompt: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_chat: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_summary: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_history: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_session: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_topic: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_scoring: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_risk: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_quality: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_latency: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_fallback: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_reasoning: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_coaching: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_planner: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_evaluator: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_context_builder: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_final_report: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_ui: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_admin: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_review: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_export: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_analytics: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_debug: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_headers: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_attachments: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_blocks: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_targets: Optional[List[str]] = None
    extra_interview_context_interview_context_goals: Optional[List[str]] = None
    extra_interview_context_interview_context_tags: Optional[List[str]] = None
    extra_interview_context_interview_context_checkpoints: Optional[List[str]] = None
    extra_interview_context_interview_context_decisions: Optional[List[str]] = None
    extra_interview_context_interview_context_observations: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_constraints: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_rubric: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_evidence: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_plan: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_follow_up_plan: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_turn_context: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_summary_text: Optional[str] = None
    extra_interview_context_interview_context_notes_text: Optional[str] = None
    extra_interview_context_interview_context_final_text: Optional[str] = None
    extra_interview_context_interview_context_turn_text: Optional[str] = None
    extra_interview_context_interview_context_context_text: Optional[str] = None
    extra_interview_context_interview_context_coaching_text: Optional[str] = None
    extra_interview_context_interview_context_prompt_text: Optional[str] = None
    extra_interview_context_interview_context_reasoning_text: Optional[str] = None
    extra_interview_context_interview_context_response_text: Optional[str] = None
    extra_interview_context_interview_context_history_text: Optional[str] = None
    extra_interview_context_interview_context_session_text: Optional[str] = None
    extra_interview_context_interview_context_topic_text: Optional[str] = None
    extra_interview_context_interview_context_flags_text: Optional[str] = None
    extra_interview_context_interview_context_quality_text: Optional[str] = None
    extra_interview_context_interview_context_latency_text: Optional[str] = None
    extra_interview_context_interview_context_fallback_text: Optional[str] = None
    extra_interview_context_interview_context_usage_text: Optional[str] = None
    extra_interview_context_interview_context_analysis_text: Optional[str] = None
    extra_interview_context_interview_context_metrics_text: Optional[str] = None
    extra_interview_context_interview_context_trace_text: Optional[str] = None
    extra_interview_context_interview_context_payload_text: Optional[str] = None
    extra_interview_context_interview_context_output_text: Optional[str] = None
    extra_interview_context_interview_context_input_text: Optional[str] = None
    extra_interview_context_interview_context_debug_text: Optional[str] = None
    extra_interview_context_interview_context_admin_text: Optional[str] = None
    extra_interview_context_interview_context_review_text: Optional[str] = None
    extra_interview_context_interview_context_export_text: Optional[str] = None
    extra_interview_context_interview_context_analytics_text: Optional[str] = None
    extra_interview_context_interview_context_header_text: Optional[str] = None
    extra_interview_context_interview_context_attachment_text: Optional[str] = None
    extra_interview_context_interview_context_block_text: Optional[str] = None
    extra_interview_context_interview_context_goal_text: Optional[str] = None
    extra_interview_context_interview_context_target_text: Optional[str] = None
    extra_interview_context_interview_context_tag_text: Optional[str] = None
    extra_interview_context_interview_context_checkpoint_text: Optional[str] = None
    extra_interview_context_interview_context_decision_text: Optional[str] = None
    extra_interview_context_interview_context_observation_text: Optional[str] = None
    extra_interview_context_interview_context_constraint_text: Optional[str] = None
    extra_interview_context_interview_context_rubric_text: Optional[str] = None
    extra_interview_context_interview_context_evidence_text: Optional[str] = None
    extra_interview_context_interview_context_plan_text: Optional[str] = None
    extra_interview_context_interview_context_follow_up_text: Optional[str] = None
    extra_interview_context_interview_context_turn_context_text: Optional[str] = None
    extra_interview_context_interview_context_context_builder_text: Optional[str] = None
    extra_interview_context_interview_context_evaluator_text: Optional[str] = None
    extra_interview_context_interview_context_planner_text: Optional[str] = None
    extra_interview_context_interview_context_coaching_summary_text: Optional[str] = None
    extra_interview_context_interview_context_interview_output_text: Optional[str] = None
    extra_interview_context_interview_context_system_output_text: Optional[str] = None
    extra_interview_context_interview_context_ui_output_text: Optional[str] = None
    extra_interview_context_interview_context_admin_output_text: Optional[str] = None
    extra_interview_context_interview_context_review_output_text: Optional[str] = None
    extra_interview_context_interview_context_export_output_text: Optional[str] = None
    extra_interview_context_interview_context_analytics_output_text: Optional[str] = None
    extra_interview_context_interview_context_debug_output_text: Optional[str] = None
    extra_interview_context_interview_context_headers_output_text: Optional[str] = None
    extra_interview_context_interview_context_attachments_output_text: Optional[str] = None
    extra_interview_context_interview_context_blocks_output_text: Optional[str] = None
    extra_interview_context_interview_context_targets_output_text: Optional[str] = None
    extra_interview_context_interview_context_goals_output_text: Optional[str] = None
    extra_interview_context_interview_context_tags_output_text: Optional[str] = None
    extra_interview_context_interview_context_checkpoints_output_text: Optional[str] = None
    extra_interview_context_interview_context_decisions_output_text: Optional[str] = None
    extra_interview_context_interview_context_observations_output_text: Optional[str] = None
    extra_interview_context_interview_context_constraints_output_text: Optional[str] = None
    extra_interview_context_interview_context_rubric_output_text: Optional[str] = None
    extra_interview_context_interview_context_evidence_output_text: Optional[str] = None
    extra_interview_context_interview_context_plan_output_text: Optional[str] = None
    extra_interview_context_interview_context_follow_up_output_text: Optional[str] = None
    extra_interview_context_interview_context_turn_context_output_text: Optional[str] = None
    extra_interview_context_interview_context_context_builder_output_text: Optional[str] = None
    extra_interview_context_interview_context_evaluator_output_text: Optional[str] = None
    extra_interview_context_interview_context_planner_output_text: Optional[str] = None
    extra_interview_context_interview_context_coaching_summary_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_payload: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_signals: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_metrics: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_trace: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_analysis: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_usage: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_response: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_prompt: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_chat: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_summary: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_history: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_session: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_topic: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_scoring: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_risk: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_quality: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_latency: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_fallback: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_reasoning: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_coaching: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_planner: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_evaluator: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_context_builder: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_final_report: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_ui: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_admin: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_review: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_export: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_analytics: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_debug: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_headers: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_attachments: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_interview_context_blocks: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_interview_context_targets: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_goals: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_tags: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_checkpoints: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_decisions: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_observations: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_constraints: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_rubric: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_evidence: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_interview_context_plan: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_follow_up_plan: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_turn_context: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_summary_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_notes_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_final_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_turn_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_context_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_coaching_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_prompt_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_reasoning_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_response_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_history_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_session_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_topic_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_flags_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_quality_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_latency_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_fallback_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_usage_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_analysis_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_metrics_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_trace_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_payload_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_input_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_debug_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_admin_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_review_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_export_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_analytics_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_header_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_attachment_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_block_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_goal_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_target_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_tag_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_checkpoint_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_decision_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_observation_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_constraint_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_rubric_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_evidence_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_plan_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_follow_up_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_turn_context_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_context_builder_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_evaluator_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_planner_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_coaching_summary_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_system_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_ui_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_admin_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_review_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_export_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_analytics_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_debug_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_headers_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_attachments_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_blocks_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_targets_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_goals_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_tags_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_checkpoints_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_decisions_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_observations_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_constraints_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_rubric_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_evidence_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_plan_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_follow_up_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_turn_context_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_context_builder_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_evaluator_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_planner_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_coaching_summary_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_payload: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_signals: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_metrics: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_trace: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_analysis: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_usage: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_response: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_prompt: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_chat: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_summary: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_history: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_session: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_topic: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_scoring: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_risk: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_quality: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_latency: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_fallback: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_reasoning: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_coaching: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_planner: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_evaluator: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_context_builder: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_final_report: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_ui: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_admin: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_review: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_export: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_analytics: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_debug: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_headers: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_attachments: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_interview_context_interview_context_blocks: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_interview_context_interview_context_targets: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_interview_context_goals: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_interview_context_tags: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_interview_context_checkpoints: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_interview_context_decisions: Optional[List[str]] = None
    extra_interview_context_interview_context_interview_context_interview_context_observations: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_constraints: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_rubric: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_evidence: Optional[List[dict[str, Any]]] = None
    extra_interview_context_interview_context_interview_context_interview_context_plan: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_follow_up_plan: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_turn_context: Optional[dict[str, Any]] = None
    extra_interview_context_interview_context_interview_context_interview_context_summary_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_notes_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_final_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_turn_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_context_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_coaching_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_prompt_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_reasoning_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_response_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_history_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_session_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_topic_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_flags_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_quality_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_latency_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_fallback_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_usage_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_analysis_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_metrics_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_trace_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_payload_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_output_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_input_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_debug_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_admin_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_review_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_export_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_analytics_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_header_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_attachment_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_block_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_goal_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_target_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_tag_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_checkpoint_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_decision_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_observation_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_constraint_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_rubric_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_evidence_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_plan_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_follow_up_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_turn_context_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_context_builder_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_evaluator_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_planner_text: Optional[str] = None
    extra_interview_context_interview_context_interview_context_interview_context_coaching_summary_text: Optional[str] = None

class HintRequest(BaseModel):
    last_question: str
    jd_text: str = ""
    lang: str = "vi"

class ReportRequest(BaseModel):
    history: str
    jd_text: str = ""
    position: str = "Chưa xác định"
    history_id: Optional[int] = None
    interview_type: str = "free"
    question_limit: int = 0
    time_limit: int = 0

# ── CV Features ──────────────────────────────

class CVGenRequest(BaseModel):
    user_info: str
    position: str
    company: str
    style_instruction: str = ""

class CVRewriteRequest(BaseModel):
    cv_text: str
    template_style: str = "harvard"

class CVTailorRequest(BaseModel):
    master_cv_json: dict
    jd_text: str

class CVParseMasterCVRequest(BaseModel):
    raw_text: str

class InterviewContextRequest(BaseModel):
    cv_text: str
    jd_text: str

class InterviewContextData(BaseModel):
    match_score: float
    highlighted_strengths: List[str] = Field(default_factory=list)
    skill_gaps: List[str] = Field(default_factory=list)
    target_topics: List[str] = Field(default_factory=list)

class InterviewContextResponse(BaseModel):
    interview_context: InterviewContextData

# ── Auth & Users ─────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    credits: int = 100

class AdminUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "user"
    credits: int = 100
    plan: str = "free"

class AdminUserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    credits: Optional[int] = None
    plan: Optional[str] = None
    password: Optional[str] = None # Admin can optionally reset password

class GoogleAuthRequest(BaseModel):
    token: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_name: str
    role: str = "user"

# ── Interview Config & Templates ─────────────

class RenameRequest(BaseModel):
    title: str

class UpdateInterviewConfig(BaseModel):
    interview_type: str = "free"
    question_limit: int = 5
    time_limit: int = 120

class JDTemplateRequest(BaseModel):
    title: str
    description: str

# ── Admin & System ───────────────────────────

class AddCreditRequest(BaseModel):
    amount: int

class SystemConfigUpdate(BaseModel):
    system_prompt: str
    temperature: float
    ai_enable_brain_retrieval: Optional[bool] = None
    ai_brain_ingestion_enrichment_enabled: Optional[bool] = None


class AIBrainCreateVersionRequest(BaseModel):
    version: str
    name: str = "speakcv-interviewer-brain"


class AIBrainIngestionStartRequest(BaseModel):
    file_key: str
    version: Optional[str] = None


class AIBrainCandidateDecision(BaseModel):
    candidate_ids: List[int] = []


class AIBrainApplyDraftRequest(BaseModel):
    accept_all_high_confidence: bool = True
    confidence_threshold: float = 0.65


class AIBrainPublishRequest(BaseModel):
    version: str


class AIBrainAssemblePromptRequest(BaseModel):
    version: Optional[str] = None
    job_role: str = ""
    seniority: str = ""
    interview_mode: str = "general"
    skill_tags: List[str] = []
    max_items: int = 12
    max_chars: int = 3500


class AIBrainNodePayload(BaseModel):
    id: str
    type: str
    label: str
    content: str
    tags: List[str] = []
    weight: float = 0.7
    active: bool = True


class AIBrainEdgePayload(BaseModel):
    id: str
    source: str
    target: str
    type: str
    weight: float = 0.7


class AIBrainImportRequest(BaseModel):
    version: str
    brain_name: str = "speakcv-interviewer-brain"
    nodes: List[AIBrainNodePayload] = []
    edges: List[AIBrainEdgePayload] = []


class AIBrainTextPreviewRequest(BaseModel):
    text: str
    strict: bool = False
    max_candidates: int = 300


class AIBrainTextImportRequest(BaseModel):
    version: str
    text: str
    strict: bool = False
    max_candidates: int = 300


class AIBrainUpdateNodeRequest(BaseModel):
    label: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    weight: Optional[float] = None
    active: Optional[bool] = None


class AIBrainUpdateEdgeRequest(BaseModel):
    source: Optional[str] = None
    target: Optional[str] = None
    type: Optional[str] = None
    weight: Optional[float] = None


class AIBrainValidateRequest(BaseModel):
    version: str


class AIBrainRejectJobRequest(BaseModel):
    reason: str = "manual_reject"


class AIBrainUpdateCandidateDecision(BaseModel):
    accepted_ids: List[int] = []
    rejected_ids: List[int] = []

# ── Support ──────────────────────────────────

class SupportMessageCreate(BaseModel):
    message: str

class SupportMessageResponse(BaseModel):
    id: int
    user_id: int
    admin_id: Optional[int] = None
    message: str
    sender_type: str
    is_read: bool
    created_at: str  

    class Config:
        from_attributes = True

class QuotaResponse(BaseModel):
    remaining: int  # -1 = unlimited (pro)
    limit: int      # -1 = unlimited (pro)

class UnreadCountResponse(BaseModel):
    unread_count: int


# --- CV Makeover JSON Schema ---
class CVPersonalInfo(BaseModel):
    name: Optional[str] = ""
    title: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    linkedin: Optional[str] = ""
    location: Optional[str] = ""
    summary: Optional[str] = ""

class CVExperienceItem(BaseModel):
    company: Optional[str] = ""
    role: Optional[str] = ""
    period: Optional[str] = ""
    achievements: Optional[List[str]] = []

class CVEducationItem(BaseModel):
    school: Optional[str] = ""
    degree: Optional[str] = ""
    period: Optional[str] = ""

class CVProjectItem(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    technologies: Optional[List[str]] = []

class CVAnalysisFeedback(BaseModel):
    strengths: Optional[List[str]] = []
    weaknesses: Optional[List[str]] = []
    overall_score: Optional[int] = 0

class CVMakeoverData(BaseModel):
    analysis_feedback: Optional[CVAnalysisFeedback] = CVAnalysisFeedback()
    personal_info: Optional[CVPersonalInfo] = CVPersonalInfo()
    skills: Optional[List[str]] = []
    experience: Optional[List[CVExperienceItem]] = []
    education: Optional[List[CVEducationItem]] = []
    projects: Optional[List[CVProjectItem]] = []
