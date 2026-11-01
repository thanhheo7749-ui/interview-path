"use client";

import { useCallback, useEffect, useState } from "react";

export type Lang = "en" | "vi";
const STORAGE_KEY = "speakcv_lang";

// English first, Vietnamese second. Keep both objects in the same key order.
const en = {
  language: "Language",
  loading: "Loading...",
  cancel: "Cancel",
  confirm: "Confirm",
  back: "Back",
  myApplications: "My applications",
  myData: "My data",
  sampleTitle: "Sample company",
  sampleBody: "This is a demo company used to show how SpeakCV works. No real hiring decision is made here.",
  jobNotFound: "We could not find this job.",
  jobClosed: "This job is no longer accepting applications.",
  requirements: "What the role asks for",
  mustHave: "Required",
  niceToHave: "Nice to have",
  apply: "Apply",
  loginToApply: "Log in to apply",
  applyTitle: "Apply with your CV",
  cvFile: "Your CV (PDF or DOCX)",
  cvTooBig: "This file is larger than 20 MB. Please choose a smaller one.",
  cvWrongType: "Only PDF and DOCX files are accepted.",
  cvRequired: "Please choose your CV file.",
  consentHeading: "How we use your CV",
  consentAgree: "I have read this and agree to it.",
  consentLoadError: "We could not load the consent text. Please try again.",
  submitApplication: "Send my application",
  sending: "Sending...",
  alreadyApplied: "You have already applied to this job.",
  reapplyAfter: "You can apply again after {date}.",
  tooLarge: "This file is too large. Please choose a smaller one.",
  unsupportedType: "Only PDF and DOCX files are accepted.",
  cvTooLong: "This CV is too long to read. Please shorten it and try again.",
  rateLimited: "Too many uploads. Please wait a while and try again.",
  consentChanged: "The consent text has changed. Please read it again and confirm.",
  genericError: "Something went wrong. Please try again.",
  appsTitle: "My applications",
  appsEmpty: "You have not applied to any job yet.",
  sampleTag: "Sample company",
  statusReading: "Reading your CV",
  statusUnreadable: "We could not read your CV",
  statusInvited: "Next: see how you fit",
  statusInterview: "Interview in progress: continue",
  statusWithHr: "With HR for review",
  statusWithdrawn: "Withdrawn",
  reuploadCv: "Upload a new CV",
  uploading: "Uploading...",
  seeFit: "See how you fit",
  continueInterview: "Continue interview",
  fitTitle: "Fit Compass",
  fitIntro: "How your CV lines up with what the role asks for. This is a guide for you, not a decision.",
  fitMatches: "Matches",
  fitPartly: "Partly",
  fitNotSeen: "Not seen in your CV",
  fitNotReady: "We are still reading your CV. This page will be ready shortly.",
  teamStyle: "How the team works",
  teamStyleEmpty: "The company has not shared its working style yet.",
  startInterview: "Continue to the interview",
  withdraw: "Withdraw application",
  withdrawTitle: "Withdraw your application?",
  withdrawBody: "HR will see that you withdrew. You can add a reason if you like.",
  withdrawReason: "Reason (optional)",
  withdrawing: "Withdrawing...",
  askTitle: "Ask the company",
  askHint: "Ask about the team, the role or company policy. Answers come from the company's own documents.",
  askPlaceholder: "Type your question",
  ask: "Ask",
  asking: "Asking...",
  askSources: "Sources",
  askSharedLabel: "Company document",
  askPage: "page {n}",
  askNotFound: "We could not find this in the company's documents. Your question has been passed to HR.",
  askConflict: "Two company sources differ on this. HR is confirming which applies.",
  askRate: "You have asked a lot of questions. Please try again later.",
  askUnavailable: "Answers are not available right now. Please try again later.",
  myDataTitle: "My data",
  myDataIntro: "See what you have shared and take it back at any time.",
  consentsHeading: "Consents",
  consentsEmpty: "No consents to show yet.",
  consentsUnavailable: "The list of consents is not available yet.",
  consentGranted: "Given {date}",
  consentWithdrawnOn: "Withdrawn {date}",
  withdrawConsent: "Withdraw consent",
  applicationsHeading: "Applications",
  deleteApplication: "Delete my application",
  deleteTitle: "Delete this application?",
  deleteBody:
    "We will delete your CV, the recording and transcript, and the answers tied to this application. HR will no longer be able to see them. This cannot be undone.",
  deleting: "Deleting...",
  withdrawConsentTitle: "Withdraw this consent?",
  withdrawConsentBody: "We will stop using your data for this purpose.",
  loginNeeded: "Please log in to see this page.",
  logIn: "Log in",
} as const;

export type Strings = { [K in keyof typeof en]: string };

const vi: Strings = {
  language: "Ngôn ngữ",
  loading: "Đang tải...",
  cancel: "Hủy",
  confirm: "Xác nhận",
  back: "Quay lại",
  myApplications: "Hồ sơ của tôi",
  myData: "Dữ liệu của tôi",
  sampleTitle: "Công ty mẫu",
  sampleBody: "Đây là công ty minh họa để cho thấy SpeakCV hoạt động thế nào. Không có quyết định tuyển dụng thật nào ở đây.",
  jobNotFound: "Chúng tôi không tìm thấy vị trí này.",
  jobClosed: "Vị trí này không còn nhận hồ sơ.",
  requirements: "Vị trí này yêu cầu",
  mustHave: "Bắt buộc",
  niceToHave: "Là lợi thế",
  apply: "Ứng tuyển",
  loginToApply: "Đăng nhập để ứng tuyển",
  applyTitle: "Ứng tuyển bằng CV của bạn",
  cvFile: "CV của bạn (PDF hoặc DOCX)",
  cvTooBig: "Tệp lớn hơn 20 MB. Vui lòng chọn tệp nhỏ hơn.",
  cvWrongType: "Chỉ nhận tệp PDF và DOCX.",
  cvRequired: "Vui lòng chọn tệp CV của bạn.",
  consentHeading: "Cách chúng tôi dùng CV của bạn",
  consentAgree: "Tôi đã đọc và đồng ý.",
  consentLoadError: "Không tải được nội dung đồng ý. Vui lòng thử lại.",
  submitApplication: "Gửi hồ sơ",
  sending: "Đang gửi...",
  alreadyApplied: "Bạn đã ứng tuyển vị trí này.",
  reapplyAfter: "Bạn có thể ứng tuyển lại sau {date}.",
  tooLarge: "Tệp quá lớn. Vui lòng chọn tệp nhỏ hơn.",
  unsupportedType: "Chỉ nhận tệp PDF và DOCX.",
  cvTooLong: "CV quá dài để đọc. Vui lòng rút gọn rồi thử lại.",
  rateLimited: "Bạn đã tải lên quá nhiều lần. Vui lòng chờ một lúc rồi thử lại.",
  consentChanged: "Nội dung đồng ý đã thay đổi. Vui lòng đọc lại và xác nhận.",
  genericError: "Đã có lỗi. Vui lòng thử lại.",
  appsTitle: "Hồ sơ của tôi",
  appsEmpty: "Bạn chưa ứng tuyển vị trí nào.",
  sampleTag: "Công ty mẫu",
  statusReading: "Đang đọc CV của bạn",
  statusUnreadable: "Chúng tôi không đọc được CV của bạn",
  statusInvited: "Tiếp theo: xem mức phù hợp của bạn",
  statusInterview: "Buổi phỏng vấn đang diễn ra: tiếp tục",
  statusWithHr: "Đang chờ nhân sự xem xét",
  statusWithdrawn: "Đã rút hồ sơ",
  reuploadCv: "Tải CV mới",
  uploading: "Đang tải lên...",
  seeFit: "Xem mức phù hợp",
  continueInterview: "Tiếp tục phỏng vấn",
  fitTitle: "La bàn phù hợp",
  fitIntro: "CV của bạn khớp với yêu cầu của vị trí đến đâu. Đây là gợi ý cho bạn, không phải quyết định.",
  fitMatches: "Phù hợp",
  fitPartly: "Một phần",
  fitNotSeen: "Chưa thấy trong CV của bạn",
  fitNotReady: "Chúng tôi vẫn đang đọc CV của bạn. Trang này sẽ sẵn sàng sớm.",
  teamStyle: "Cách đội ngũ làm việc",
  teamStyleEmpty: "Công ty chưa chia sẻ phong cách làm việc.",
  startInterview: "Tiếp tục tới buổi phỏng vấn",
  withdraw: "Rút hồ sơ",
  withdrawTitle: "Rút hồ sơ ứng tuyển?",
  withdrawBody: "Nhân sự sẽ thấy bạn đã rút hồ sơ. Bạn có thể ghi lý do nếu muốn.",
  withdrawReason: "Lý do (không bắt buộc)",
  withdrawing: "Đang rút...",
  askTitle: "Hỏi công ty",
  askHint: "Hỏi về đội ngũ, vị trí hoặc chính sách công ty. Câu trả lời lấy từ tài liệu của chính công ty.",
  askPlaceholder: "Nhập câu hỏi của bạn",
  ask: "Hỏi",
  asking: "Đang hỏi...",
  askSources: "Nguồn",
  askSharedLabel: "Tài liệu công ty",
  askPage: "trang {n}",
  askNotFound: "Chúng tôi không tìm thấy nội dung này trong tài liệu của công ty. Câu hỏi của bạn đã được chuyển cho bộ phận nhân sự.",
  askConflict: "Hai nguồn tài liệu của công ty đang khác nhau về nội dung này. Bộ phận nhân sự đang xác nhận.",
  askRate: "Bạn đã hỏi khá nhiều câu. Vui lòng thử lại sau.",
  askUnavailable: "Hiện chưa trả lời được. Vui lòng thử lại sau.",
  myDataTitle: "Dữ liệu của tôi",
  myDataIntro: "Xem những gì bạn đã chia sẻ và thu hồi bất cứ lúc nào.",
  consentsHeading: "Các đồng ý",
  consentsEmpty: "Chưa có đồng ý nào.",
  consentsUnavailable: "Danh sách đồng ý chưa khả dụng.",
  consentGranted: "Đồng ý ngày {date}",
  consentWithdrawnOn: "Đã rút ngày {date}",
  withdrawConsent: "Rút đồng ý",
  applicationsHeading: "Hồ sơ ứng tuyển",
  deleteApplication: "Xóa hồ sơ của tôi",
  deleteTitle: "Xóa hồ sơ này?",
  deleteBody:
    "Chúng tôi sẽ xóa CV, bản ghi âm và bản ghi lời thoại, cùng các câu trả lời gắn với hồ sơ này. Nhân sự sẽ không xem được nữa. Không thể hoàn tác.",
  deleting: "Đang xóa...",
  withdrawConsentTitle: "Rút đồng ý này?",
  withdrawConsentBody: "Chúng tôi sẽ ngừng dùng dữ liệu của bạn cho mục đích này.",
  loginNeeded: "Vui lòng đăng nhập để xem trang này.",
  logIn: "Đăng nhập",
};

export const STRINGS: Record<Lang, Strings> = { en, vi };

export function format(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? ""));
}

/** Current language, read from localStorage after mount, plus a setter that stores the choice. */
export function useLang(): { lang: Lang; t: Strings; setLang: (lang: Lang) => void } {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    const read = () => {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "en" || stored === "vi") setLangState(stored);
    };
    read();
    window.addEventListener("speakcv-lang", read);
    return () => window.removeEventListener("speakcv-lang", read);
  }, []);

  const setLang = useCallback((next: Lang) => {
    localStorage.setItem(STORAGE_KEY, next);
    window.dispatchEvent(new Event("speakcv-lang"));
  }, []);

  return { lang, t: STRINGS[lang], setLang };
}

// Strings for the recorded interview.
export type Locale = "en" | "vi";

export function detectLocale(): Locale {
  if (typeof localStorage !== "undefined") {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "vi") return stored;
  }
  if (typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("vi")) return "vi";
  return "en";
}

const screeningEn = {
  loading: "Loading your interview...",
  title: "Recorded interview",
  unsupported: "This browser cannot record audio. Please use a recent version of Chrome, Edge, Firefox or Safari.",
  micDenied: "Microphone access was blocked. Allow the microphone in your browser settings and try again.",
  micMissing: "No microphone was found. Connect one and try again.",
  micTitle: "Check your microphone",
  micHelp: "Say a few words. The bar should move when you speak.",
  micStart: "Test microphone",
  micHeard: "We can hear you.",
  micQuiet: "We do not hear anything yet.",
  languageLabel: "Interview language",
  languageHint: "If this language is not offered for the job, you will be told and can pick another.",
  consentTitle: "Recording consent",
  consentCheckbox: "I agree that my answers are recorded and transcribed as described above.",
  consentOnly: "Audio and transcript only. There is no video.",
  start: "Start the interview",
  starting: "Starting...",
  decline: "Decline recording",
  declineWarn:
    "If you decline, your application still goes to HR, but without any interview evidence. This may weaken it. This cannot be undone.",
  declineConfirm: "Yes, decline recording",
  declineCancel: "Go back",
  declined: "You declined recording. Your application has been sent to HR without an interview.",
  recordingOn: "Recording: this answer is being recorded",
  recordingSession: "This interview is recorded (audio and transcript)",
  questionOf: (n: number, total: number) => `Question ${n} of ${total}`,
  timeLeft: "Time left",
  why: "Why we ask this",
  followup: "Follow-up",
  record: "Record answer",
  stop: "Stop and send",
  recordingAuto: "Answers stop automatically after 3 minutes.",
  uploading: "Sending your answer...",
  uploadFailed: "We could not send your answer. Check your connection and try again.",
  retrySend: "Send again",
  repeat: "We did not hear an answer. Please try again when you are ready.",
  retry: "We could not process that recording. Please record your answer again.",
  paused:
    "The interview is paused because of repeated problems. Please try again. If it keeps happening, contact the company's HR team.",
  closing: "The interview is wrapping up. This is the last answer we will take.",
  completed: "Thank you. Your interview is complete and has been sent to HR. A person will review it and make the decision.",
  expired: "This interview session has expired. Your application has been passed to HR.",
  notInvited: "This application has no interview waiting right now.",
  withHr: "Your application is with HR.",
  notFound: "We could not find this application.",
  back: "Back to my applications",
  playQuestion: "Play question",
  genericError: "Something went wrong. Please try again.",
  recordError: "The recording failed. Please try again.",
};

const screeningVi: typeof screeningEn = {
  loading: "Đang tải buổi phỏng vấn...",
  title: "Phỏng vấn có ghi âm",
  unsupported: "Trình duyệt này không thể ghi âm. Vui lòng dùng phiên bản Chrome, Edge, Firefox hoặc Safari mới.",
  micDenied: "Quyền dùng micro đã bị chặn. Hãy cho phép micro trong cài đặt trình duyệt rồi thử lại.",
  micMissing: "Không tìm thấy micro. Hãy kết nối micro rồi thử lại.",
  micTitle: "Kiểm tra micro",
  micHelp: "Hãy nói vài từ. Thanh sẽ chuyển động khi bạn nói.",
  micStart: "Kiểm tra micro",
  micHeard: "Chúng tôi nghe được bạn.",
  micQuiet: "Chúng tôi chưa nghe thấy gì.",
  languageLabel: "Ngôn ngữ phỏng vấn",
  languageHint: "Nếu vị trí không hỗ trợ ngôn ngữ này, bạn sẽ được báo và có thể chọn ngôn ngữ khác.",
  consentTitle: "Đồng ý ghi âm",
  consentCheckbox: "Tôi đồng ý để câu trả lời của mình được ghi âm và chuyển thành văn bản như mô tả ở trên.",
  consentOnly: "Chỉ có âm thanh và văn bản. Không có video.",
  start: "Bắt đầu phỏng vấn",
  starting: "Đang bắt đầu...",
  decline: "Từ chối ghi âm",
  declineWarn:
    "Nếu từ chối, hồ sơ của bạn vẫn được chuyển cho HR nhưng không có bằng chứng phỏng vấn, điều này có thể làm hồ sơ yếu hơn. Không thể hoàn tác.",
  declineConfirm: "Có, từ chối ghi âm",
  declineCancel: "Quay lại",
  declined: "Bạn đã từ chối ghi âm. Hồ sơ của bạn đã được chuyển cho HR mà không có phỏng vấn.",
  recordingOn: "Đang ghi âm: câu trả lời này đang được ghi",
  recordingSession: "Buổi phỏng vấn này được ghi lại (âm thanh và văn bản)",
  questionOf: (n: number, total: number) => `Câu hỏi ${n} trên ${total}`,
  timeLeft: "Thời gian còn lại",
  why: "Vì sao chúng tôi hỏi câu này",
  followup: "Câu hỏi tiếp theo",
  record: "Ghi câu trả lời",
  stop: "Dừng và gửi",
  recordingAuto: "Mỗi câu trả lời tự dừng sau 3 phút.",
  uploading: "Đang gửi câu trả lời...",
  uploadFailed: "Chúng tôi không gửi được câu trả lời. Hãy kiểm tra kết nối và thử lại.",
  retrySend: "Gửi lại",
  repeat: "Chúng tôi chưa nghe thấy câu trả lời. Hãy thử lại khi bạn sẵn sàng.",
  retry: "Chúng tôi không xử lý được bản ghi đó. Vui lòng ghi âm lại câu trả lời.",
  paused: "Buổi phỏng vấn tạm dừng vì gặp sự cố liên tục. Vui lòng thử lại. Nếu vẫn lỗi, hãy liên hệ HR của công ty.",
  closing: "Buổi phỏng vấn sắp kết thúc. Đây là câu trả lời cuối cùng chúng tôi nhận.",
  completed: "Cảm ơn bạn. Buổi phỏng vấn đã hoàn tất và được gửi cho HR. Một người sẽ xem xét và đưa ra quyết định.",
  expired: "Phiên phỏng vấn đã hết hạn. Hồ sơ của bạn đã được chuyển cho HR.",
  notInvited: "Hồ sơ này hiện chưa có buổi phỏng vấn nào đang chờ.",
  withHr: "Hồ sơ của bạn đang ở chỗ HR.",
  notFound: "Chúng tôi không tìm thấy hồ sơ này.",
  back: "Về danh sách hồ sơ",
  playQuestion: "Nghe câu hỏi",
  genericError: "Đã có lỗi. Vui lòng thử lại.",
  recordError: "Ghi âm thất bại. Vui lòng thử lại.",
};

export const screeningText = { en: screeningEn, vi: screeningVi };
export type ScreeningText = typeof screeningEn;
