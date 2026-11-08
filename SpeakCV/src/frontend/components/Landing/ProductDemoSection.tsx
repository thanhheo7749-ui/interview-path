"use client";

import React, { useState } from "react";
import {
  ArrowUpRight,
  BookOpen,
  Calendar,
  CheckCircle2,
  FileText,
  GitBranch,
  Layers,
  Mic,
  Quote,
  RotateCw,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from "lucide-react";

type DemoTabId = "questions" | "session" | "evidence";

interface QuestionCardData {
  id: string;
  code: string;
  typeLabel: string;
  question: string;
  skill: string;
  source: string;
  difficulty: string;
  rubric: string;
  approver: string;
  version: string;
}

const DEMO_QUESTION_CARDS: QuestionCardData[] = [
  {
    id: "fe-core-01",
    code: "FE-Q01 · Câu hỏi cá nhân hóa theo dự án CV & JD",
    typeLabel: "Truy xuất Đồ thị tri thức + Đối chiếu dự án React trong CV",
    question: "Bạn đã đo và cải thiện hiệu năng dự án này như thế nào?",
    skill: "React Rendering · Tối ưu hiệu năng · Đo lường thực nghiệm",
    source:
      "FE_Performance_Playbook_v2.pdf (Mục 3.2, Trang 14) · Nút đồ thị: React Render Pipeline",
    difficulty: "Trung cấp – Nâng cao (Mid/Senior Frontend)",
    rubric:
      "Nêu rõ công cụ đo (React DevTools Profiler / Web Vitals), xác định đúng nguyên nhân gây nghẽn, giải pháp thay đổi cụ thể và số liệu/cách kiểm tra lại sau tối ưu.",
    approver: "Quản lý chuyên môn duyệt nội dung · HR duyệt quy trình",
    version: "Bộ đề v1.2 · Đã duyệt",
  },
  {
    id: "fe-core-02",
    code: "FE-Q02 · Câu hỏi cốt lõi từ tài liệu chuyên môn",
    typeLabel: "Sinh từ Tài liệu chuyên môn & Đồ thị tri thức",
    question:
      "Khi bảng dữ liệu cập nhật liên tục theo thời gian thực, bạn tách trạng thái (state) và kiểm soát việc render lại của các hàng con theo nguyên tắc nào?",
    skill: "State Colocation · Memoization · Danh sách lớn",
    source: "Web_Client_Architecture_2026.md (Mục 4.1) · Phiên bản v2.0",
    difficulty: "Trung cấp (Mid-level)",
    rubric:
      "Giải thích được lý do không đặt state tìm kiếm/lọc ở nút gốc và cách cô lập phạm vi cập nhật component.",
    approver: "Quản lý chuyên môn duyệt nội dung · HR duyệt quy trình",
    version: "Bộ đề v1.2 · Đã duyệt",
  },
  {
    id: "fe-core-03",
    code: "FE-Q03 · Câu hỏi chuẩn hóa từ ngân hàng câu hỏi",
    typeLabel: "Trích xuất & chuẩn hóa từ Ngân hàng câu hỏi có sẵn",
    question:
      "Bạn thiết lập quy trình kiểm tra hồi quy hiệu năng giao diện trước khi phát hành bản cập nhật mới như thế nào?",
    skill: "Web Vitals · Kiểm thử hiệu năng · CI/CD",
    source: "Frontend_Question_Bank.xlsx (Mã gốc QB-19) · Đã chuẩn hóa rubric",
    difficulty: "Trung cấp (Mid-level)",
    rubric:
      "Trình bày được tiêu chí so sánh trước/sau trên cùng kịch bản dữ liệu và thiết bị thử nghiệm.",
    approver: "Quản lý chuyên môn duyệt nội dung · HR duyệt quy trình",
    version: "Bộ đề v1.2 · Đã duyệt",
  },
];

export default function ProductDemoSection() {
  const [activeTab, setActiveTab] = useState<DemoTabId>("questions");
  const [selectedQuestionId, setSelectedQuestionId] = useState<string>("fe-core-01");
  const [flippedCardIds, setFlippedCardIds] = useState<Record<string, boolean>>({
    "fe-core-01": false,
  });
  const [activeEvidenceKey, setActiveEvidenceKey] = useState<
    "measure" | "change" | "verify"
  >("measure");
  const [evidenceOpen, setEvidenceOpen] = useState<boolean>(true);

  const selectedCard =
    DEMO_QUESTION_CARDS.find((c) => c.id === selectedQuestionId) ??
    DEMO_QUESTION_CARDS[0];

  const isSelectedFlipped = Boolean(flippedCardIds[selectedCard.id]);

  const toggleCardFlip = (id: string) => {
    setFlippedCardIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="rounded-3xl border border-[#DEE5ED] bg-white shadow-[0_18px_50px_rgba(24,49,83,0.07)] overflow-hidden">
      {/* Top Accent Bar */}
      <div
        aria-hidden="true"
        className="h-1.5 w-full bg-gradient-to-r from-[#7963BE] via-[#087F78] to-[#387BC1]"
      />

      {/* Demo Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#DEE5ED] bg-[#F7F8FA] px-5 py-4 sm:px-8">
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#087F78]/30 bg-[#087F78]/10 px-3 py-1 text-xs font-bold text-[#087F78]">
            <Layers className="h-3.5 w-3.5" />
            Vị trí xuyên suốt: Frontend Developer
          </span>
          <span className="text-xs font-medium text-[#586779]">
            JD yêu cầu React &amp; tối ưu hiệu năng · CV ứng viên có dự án React Dashboard
          </span>
        </div>

        {/* Explicit Required Label: Dữ liệu minh họa */}
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[#AD661B]/35 bg-[#AD661B]/10 px-3.5 py-1 text-xs font-bold text-[#AD661B]">
          <span className="h-2 w-2 rounded-full bg-[#AD661B]" />
          Dữ liệu minh họa
        </span>
      </div>

      {/* 3-Tab Switcher */}
      <div className="border-b border-[#DEE5ED] bg-white px-5 pt-4 sm:px-8">
        <div
          role="tablist"
          aria-label="Ba giai đoạn trong phiên phỏng vấn mẫu Frontend Developer"
          className="flex flex-wrap gap-2.5 pb-4"
        >
          <button
            type="button"
            role="tab"
            id="demo-tab-questions"
            aria-selected={activeTab === "questions"}
            aria-controls="demo-panel-questions"
            onClick={() => setActiveTab("questions")}
            className={`inline-flex items-center gap-2.5 rounded-xl px-4 py-2.5 text-sm font-bold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78] ${
              activeTab === "questions"
                ? "bg-[#087F78] text-white shadow-sm"
                : "border border-[#DEE5ED] bg-[#F7F8FA] text-[#586779] hover:border-[#183153]/30 hover:text-[#183153]"
            }`}
          >
            <span
              className={`inline-flex h-5 w-5 items-center justify-center rounded-md text-xs font-extrabold ${
                activeTab === "questions"
                  ? "bg-white/20 text-white"
                  : "bg-[#7963BE]/15 text-[#7963BE]"
              }`}
            >
              1
            </span>
            <span>Bộ câu hỏi</span>
          </button>

          <button
            type="button"
            role="tab"
            id="demo-tab-session"
            aria-selected={activeTab === "session"}
            aria-controls="demo-panel-session"
            onClick={() => setActiveTab("session")}
            className={`inline-flex items-center gap-2.5 rounded-xl px-4 py-2.5 text-sm font-bold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78] ${
              activeTab === "session"
                ? "bg-[#087F78] text-white shadow-sm"
                : "border border-[#DEE5ED] bg-[#F7F8FA] text-[#586779] hover:border-[#183153]/30 hover:text-[#183153]"
            }`}
          >
            <span
              className={`inline-flex h-5 w-5 items-center justify-center rounded-md text-xs font-extrabold ${
                activeTab === "session"
                  ? "bg-white/20 text-white"
                  : "bg-[#087F78]/15 text-[#087F78]"
              }`}
            >
              2
            </span>
            <span>Phiên phỏng vấn</span>
          </button>

          <button
            type="button"
            role="tab"
            id="demo-tab-evidence"
            aria-selected={activeTab === "evidence"}
            aria-controls="demo-panel-evidence"
            onClick={() => setActiveTab("evidence")}
            className={`inline-flex items-center gap-2.5 rounded-xl px-4 py-2.5 text-sm font-bold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78] ${
              activeTab === "evidence"
                ? "bg-[#087F78] text-white shadow-sm"
                : "border border-[#DEE5ED] bg-[#F7F8FA] text-[#586779] hover:border-[#183153]/30 hover:text-[#183153]"
            }`}
          >
            <span
              className={`inline-flex h-5 w-5 items-center justify-center rounded-md text-xs font-extrabold ${
                activeTab === "evidence"
                  ? "bg-white/20 text-white"
                  : "bg-[#287A55]/15 text-[#287A55]"
              }`}
            >
              3
            </span>
            <span>Nhận xét &amp; bằng chứng</span>
          </button>
        </div>
      </div>

      {/* ============================================================
          TAB 1: BỘ CÂU HỎI (Kèm tương tác lật thẻ xem Nguồn & Tiêu chí)
         ============================================================ */}
      {activeTab === "questions" && (
        <div
          id="demo-panel-questions"
          role="tabpanel"
          aria-labelledby="demo-tab-questions"
          className="p-5 sm:p-8"
        >
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left List: 3 Question Cards */}
            <div className="space-y-3 lg:col-span-5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold uppercase tracking-wider text-[#586779]">
                  Bộ đề đã duyệt cho JD Frontend Developer
                </p>
                <span className="rounded-full bg-[#287A55]/12 px-2.5 py-0.5 text-xs font-bold text-[#287A55]">
                  v1.2 · Đã duyệt
                </span>
              </div>

              {DEMO_QUESTION_CARDS.map((card) => {
                const isSelected = card.id === selectedCard.id;
                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() => setSelectedQuestionId(card.id)}
                    className={`w-full rounded-2xl border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78] ${
                      isSelected
                        ? "border-[#087F78] bg-[#F2F9F8] shadow-sm"
                        : "border-[#DEE5ED] bg-[#F7F8FA] hover:border-[#183153]/30 hover:bg-white"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-bold text-[#7963BE]">
                        {card.code}
                      </span>
                      <span className="inline-flex items-center gap-1 rounded-full bg-[#287A55]/12 px-2 py-0.5 text-[11px] font-bold text-[#287A55]">
                        <CheckCircle2 className="h-3 w-3" />
                        Đã duyệt
                      </span>
                    </div>
                    <p className="mt-2 text-sm font-bold leading-relaxed text-[#183153]">
                      “{card.question}”
                    </p>
                    <p className="mt-1.5 text-xs text-[#586779]">{card.typeLabel}</p>
                  </button>
                );
              })}
            </div>

            {/* Right Interactive Flip Card (Mặt trước: Câu hỏi / Mặt sau: Kỹ năng, Nguồn, Độ khó, Tiêu chí chấm) */}
            <div className="lg:col-span-7">
              <div className="flex h-full flex-col justify-between rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-6 sm:p-7">
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#DEE5ED] pb-4">
                    <div className="flex items-center gap-2">
                      <span className="rounded-lg bg-[#7963BE]/15 px-2.5 py-1 text-xs font-bold text-[#7963BE]">
                        {isSelectedFlipped
                          ? "MẶT SAU THẺ CÂU HỎI · CĂN CỨ & RUBRIC"
                          : "MẶT TRƯỚC THẺ CÂU HỎI · NỘI DUNG HỎI"}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => toggleCardFlip(selectedCard.id)}
                      aria-pressed={isSelectedFlipped}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-[#087F78] px-3.5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#066660] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183153]"
                    >
                      <RotateCw className="h-3.5 w-3.5" />
                      <span>
                        {isSelectedFlipped
                          ? "Lật lại mặt trước câu hỏi"
                          : "Bấm lật thẻ xem nguồn & tiêu chí chấm"}
                      </span>
                    </button>
                  </div>

                  {!isSelectedFlipped ? (
                    <div className="mt-5 space-y-4">
                      <div className="rounded-2xl border border-[#DEE5ED] bg-white p-5 shadow-sm">
                        <p className="text-xs font-bold uppercase tracking-wider text-[#7963BE]">
                          {selectedCard.code}
                        </p>
                        <h3 className="mt-2 text-xl font-extrabold leading-relaxed text-[#183153] sm:text-2xl">
                          “{selectedCard.question}”
                        </h3>
                        <p className="mt-3 text-xs leading-relaxed text-[#586779]">
                          Câu hỏi này kết hợp yêu cầu <strong>React &amp; tối ưu hiệu năng</strong> trong JD với <strong>dự án React</strong> có trong hồ sơ SpeakCV của ứng viên.
                        </p>
                      </div>

                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div className="rounded-xl border border-[#DEE5ED] bg-white p-4">
                          <p className="text-xs font-bold uppercase tracking-wider text-[#586779]">
                            Kỹ năng cần đánh giá
                          </p>
                          <p className="mt-1.5 text-sm font-bold text-[#183153]">
                            {selectedCard.skill}
                          </p>
                        </div>
                        <div className="rounded-xl border border-[#DEE5ED] bg-white p-4">
                          <p className="text-xs font-bold uppercase tracking-wider text-[#586779]">
                            Người phụ trách duyệt
                          </p>
                          <p className="mt-1.5 text-sm font-bold text-[#287A55]">
                            {selectedCard.approver}
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-5 grid grid-cols-1 gap-3.5 sm:grid-cols-2">
                      <div className="rounded-xl border border-[#7963BE]/30 bg-white p-4">
                        <p className="text-xs font-bold uppercase tracking-wider text-[#7963BE]">
                          1. Kỹ năng cần đánh giá
                        </p>
                        <p className="mt-1.5 text-sm font-bold text-[#183153]">
                          {selectedCard.skill}
                        </p>
                      </div>

                      <div className="rounded-xl border border-[#7963BE]/30 bg-white p-4">
                        <p className="text-xs font-bold uppercase tracking-wider text-[#7963BE]">
                          2. Nguồn tài liệu &amp; Đồ thị
                        </p>
                        <p className="mt-1.5 text-xs font-semibold leading-relaxed text-[#183153]">
                          {selectedCard.source}
                        </p>
                      </div>

                      <div className="rounded-xl border border-[#087F78]/30 bg-white p-4">
                        <p className="text-xs font-bold uppercase tracking-wider text-[#087F78]">
                          3. Độ khó &amp; Cấp độ
                        </p>
                        <p className="mt-1.5 text-sm font-bold text-[#183153]">
                          {selectedCard.difficulty}
                        </p>
                      </div>

                      <div className="rounded-xl border border-[#287A55]/30 bg-white p-4">
                        <p className="text-xs font-bold uppercase tracking-wider text-[#287A55]">
                          4. Tiêu chí chấm (Rubric)
                        </p>
                        <p className="mt-1.5 text-xs leading-relaxed text-[#183153]">
                          {selectedCard.rubric}
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-[#DEE5ED] pt-4">
                  <span className="text-xs text-[#586779]">
                    Chính sách tuyển dụng ràng buộc thời lượng &amp; quy tắc hỏi tiếp; kiến thức chuyên môn làm căn cứ tạo câu hỏi.
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveTab("session")}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-[#183153] px-4 py-2 text-xs font-bold text-white transition hover:bg-[#244673]"
                  >
                    <span>Xem Phiên phỏng vấn</span>
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================
          TAB 2: PHIÊN PHỎNG VẤN (Ghép Hồ sơ + JD + Bộ đề trên bàn phỏng vấn)
         ============================================================ */}
      {activeTab === "session" && (
        <div
          id="demo-panel-session"
          role="tabpanel"
          aria-labelledby="demo-tab-session"
          className="p-5 sm:p-8"
        >
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left Context Column: 3 Connected Inputs */}
            <div className="space-y-3.5 lg:col-span-4">
              <div className="rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-[#087F78]">
                  3 đầu vào ghép ngữ cảnh phiên
                </p>
                <h3 className="mt-1 text-base font-extrabold text-[#183153]">
                  Mỗi phiên gắn đúng đơn ứng tuyển
                </h3>

                <div className="mt-4 space-y-3">
                  <div className="rounded-xl border border-[#387BC1]/30 bg-white p-3.5">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#387BC1]">
                      <UserCheck className="h-4 w-4" />
                      <span>1. Hồ sơ SpeakCV (Đã xác nhận)</span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-[#586779]">
                      Dự án trong CV: <strong>Hệ thống Dashboard Quản lý Giao dịch React</strong> (2.000+ dòng dữ liệu thời gian thực).
                    </p>
                  </div>

                  <div className="rounded-xl border border-[#183153]/20 bg-white p-3.5">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#183153]">
                      <FileText className="h-4 w-4 text-[#087F78]" />
                      <span>2. JD đúng đơn ứng tuyển</span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-[#586779]">
                      Vị trí <strong>Frontend Developer (JD-FE-2026)</strong> · Yêu cầu trọng tâm: React &amp; tối ưu hiệu năng.
                    </p>
                  </div>

                  <div className="rounded-xl border border-[#7963BE]/30 bg-white p-3.5">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#7963BE]">
                      <BookOpen className="h-4 w-4" />
                      <span>3. Bộ đề đã duyệt (v1.2)</span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-[#586779]">
                      Câu cốt lõi + phạm vi cá nhân hóa theo dự án React + quy tắc hỏi tiếp đã được Quản lý &amp; HR duyệt.
                    </p>
                  </div>

                  <div className="rounded-xl border border-[#287A55]/30 bg-[#287A55]/8 p-3.5">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#287A55]">
                      <Calendar className="h-4 w-4" />
                      <span>Lịch hẹn đã xác nhận: 10:00 (GMT+7)</span>
                    </div>
                    <p className="mt-1 text-xs text-[#586779]">
                      Đã thông báo hình thức ghi nhận trước khi bắt đầu phiên.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Conversation Transcript on SpeakCV Table */}
            <div className="lg:col-span-8">
              <div className="rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-5 sm:p-6">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#DEE5ED] pb-4">
                  <div className="flex items-center gap-2.5">
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#087F78] text-white">
                      <Mic className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-sm font-extrabold text-[#183153]">
                        Hội thoại phỏng vấn trên SpeakCV (Dữ liệu minh họa)
                      </p>
                      <p className="text-xs text-[#586779]">
                        Không tự phát âm thanh hay xin quyền microphone trên trang giới thiệu
                      </p>
                    </div>
                  </div>
                  <span className="rounded-full border border-[#287A55]/30 bg-[#287A55]/10 px-3 py-1 text-xs font-bold text-[#287A55]">
                    Lưu phiên &amp; phiên bản đề v1.2
                  </span>
                </div>

                <div className="mt-5 space-y-4">
                  {/* Turn 1: Main Question */}
                  <div className="rounded-2xl border border-[#7963BE]/30 bg-white p-4 shadow-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-[#7963BE]">
                        Hệ thống phỏng vấn SpeakCV · Câu hỏi chính (FE-Q01)
                      </span>
                      <span className="font-mono text-xs text-[#586779]">03:15</span>
                    </div>
                    <p className="mt-2 text-base font-bold leading-relaxed text-[#183153]">
                      “Bạn đã đo và cải thiện hiệu năng dự án này như thế nào?”
                    </p>
                  </div>

                  {/* Turn 2: Candidate Answer */}
                  <div className="rounded-2xl border border-[#387BC1]/35 bg-white p-4 shadow-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-[#387BC1]">
                        Ứng viên trả lời · Mô tả cách đo, thay đổi và kiểm tra
                      </span>
                      <span className="font-mono text-xs text-[#586779]">03:48</span>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-[#183153]">
                      “Trong dự án Dashboard React có bảng 2.000 dòng giao dịch, đầu tiên mình dùng{" "}
                      <strong>React DevTools Profiler</strong> và phép đo{" "}
                      <strong>Interaction to Next Paint (INP)</strong> để ghi lại thao tác lọc nhanh, phát hiện ô tìm kiếm đặt state ở component cha làm toàn bộ 2.000 dòng render lại mất ~280ms mỗi lần gõ. Sau đó mình{" "}
                      <strong>tách state ô tìm kiếm xuống component riêng</strong>, kết hợp{" "}
                      <strong>useDeferredValue</strong> và{" "}
                      <strong>ảo hóa danh sách bằng @tanstack/react-virtual</strong>. Khi kiểm tra lại trên cùng tập dữ liệu 2.000 dòng, số component render lại giảm xuống chỉ còn 18 dòng hiển thị trên khung nhìn và thời gian phản hồi phím gõ giảm còn ~35ms.”
                    </p>
                  </div>

                  {/* Turn 3: Contextual Follow-up */}
                  <div className="rounded-2xl border border-[#087F78]/35 bg-[#F2F9F8] p-4 shadow-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#087F78]">
                        <Sparkles className="h-3.5 w-3.5" />
                        Câu hỏi tiếp nối trong phạm vi đã duyệt (Làm rõ cách so sánh)
                      </span>
                      <span className="font-mono text-xs text-[#586779]">04:40</span>
                    </div>
                    <p className="mt-2 text-sm font-semibold leading-relaxed text-[#183153]">
                      “Để đảm bảo con số giảm từ 280ms xuống 35ms là khách quan, bạn đã thiết lập môi trường đo (CPU throttling, bản build production hay development) và so sánh trước/sau như thế nào?”
                    </p>
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-[#DEE5ED] pt-4">
                  <span className="text-xs text-[#586779]">
                    Toàn bộ câu hỏi, câu trả lời và phiên bản rubric được lưu lại để trích dẫn bằng chứng.
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("evidence");
                      setEvidenceOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-[#087F78] px-4 py-2 text-xs font-bold text-white transition hover:bg-[#066660]"
                  >
                    <span>Xem Nhận xét &amp; bằng chứng</span>
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================
          TAB 3: NHẬN XÉT & BẰNG CHỨNG (Bấm nhận xét để làm nổi bật đoạn trả lời)
         ============================================================ */}
      {activeTab === "evidence" && (
        <div
          id="demo-panel-evidence"
          role="tabpanel"
          aria-labelledby="demo-tab-evidence"
          className="p-5 sm:p-8"
        >
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left Column: AI Proposed Assessment Notes (Clickable to highlight evidence) */}
            <div className="space-y-4 lg:col-span-5">
              <div className="rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#087F78]">
                    AI đề xuất nhận xét theo tiêu chí
                  </span>
                  <span className="rounded-full bg-[#287A55]/12 px-2.5 py-0.5 text-[11px] font-bold text-[#287A55]">
                    Có bằng chứng
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-[#586779]">
                  Bấm vào từng nhận xét bên dưới để làm nổi bật đúng đoạn trả lời nguyên văn tương ứng ở cột bên phải:
                </p>

                <div className="mt-4 space-y-2.5">
                  <button
                    type="button"
                    onClick={() => {
                      setActiveEvidenceKey("measure");
                      setEvidenceOpen(true);
                    }}
                    className={`w-full rounded-xl border p-3.5 text-left transition ${
                      evidenceOpen && activeEvidenceKey === "measure"
                        ? "border-[#087F78] bg-white shadow-sm"
                        : "border-[#DEE5ED] bg-white/70 hover:border-[#183153]/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#087F78]">
                        Nhận xét 1 · Cách đo lường &amp; chẩn đoán
                      </span>
                      <Quote className="h-3.5 w-3.5 text-[#087F78]" />
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-[#183153]">
                      Xác định đúng nút cổ chai bằng React DevTools Profiler và chỉ số INP trước khi can thiệp mã nguồn.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setActiveEvidenceKey("change");
                      setEvidenceOpen(true);
                    }}
                    className={`w-full rounded-xl border p-3.5 text-left transition ${
                      evidenceOpen && activeEvidenceKey === "change"
                        ? "border-[#7963BE] bg-white shadow-sm"
                        : "border-[#DEE5ED] bg-white/70 hover:border-[#183153]/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#7963BE]">
                        Nhận xét 2 · Giải pháp thay đổi kiến trúc
                      </span>
                      <Quote className="h-3.5 w-3.5 text-[#7963BE]" />
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-[#183153]">
                      Áp dụng đúng kỹ thuật tách state cục bộ kết hợp useDeferredValue và ảo hóa danh sách.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setActiveEvidenceKey("verify");
                      setEvidenceOpen(true);
                    }}
                    className={`w-full rounded-xl border p-3.5 text-left transition ${
                      evidenceOpen && activeEvidenceKey === "verify"
                        ? "border-[#287A55] bg-white shadow-sm"
                        : "border-[#DEE5ED] bg-white/70 hover:border-[#183153]/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#287A55]">
                        Nhận xét 3 · Kiểm chứng kết quả trước/sau
                      </span>
                      <Quote className="h-3.5 w-3.5 text-[#287A55]" />
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-[#183153]">
                      Đối chiếu trên cùng tập 2.000 dòng dữ liệu, giảm số hàng render lại và cải thiện độ trễ từ ~280ms xuống ~35ms.
                    </p>
                  </button>
                </div>

                <div className="mt-4 rounded-xl border border-[#DEE5ED] bg-white p-3.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#183153]">
                    <ShieldCheck className="h-4 w-4 text-[#087F78]" />
                    <span>Nguyên tắc đánh giá minh bạch</span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-[#586779]">
                    Không suy diễn cảm xúc hoặc năng lực từ giọng nói. HR có thể chỉnh sửa nhận định của AI; Quản lý là người ra quyết định cuối cùng.
                  </p>
                </div>
              </div>
            </div>

            {/* Right Column: Highlighted Verbatim Answer Excerpt & HR Review Frame */}
            <div className="lg:col-span-7">
              <div className="flex h-full flex-col justify-between rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-6">
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#DEE5ED] pb-4">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-[#087F78]">
                        Bằng chứng trích dẫn từ phiên phỏng vấn (Mốc 03:48)
                      </p>
                      <h4 className="mt-1 text-base font-extrabold text-[#183153]">
                        Đoạn trả lời nguyên văn gắn với câu hỏi FE-Q01
                      </h4>
                    </div>

                    <button
                      type="button"
                      onClick={() => setEvidenceOpen((prev) => !prev)}
                      aria-pressed={evidenceOpen}
                      className="rounded-xl border border-[#087F78] bg-white px-3 py-1.5 text-xs font-bold text-[#087F78] transition hover:bg-[#087F78] hover:text-white"
                    >
                      {evidenceOpen ? "Đang bật làm nổi bật bằng chứng" : "Làm nổi bật bằng chứng"}
                    </button>
                  </div>

                  <div className="mt-5 rounded-2xl border border-[#DEE5ED] bg-white p-5 text-sm leading-loose text-[#183153] shadow-sm">
                    <p className="mb-2 font-mono text-xs text-[#586779]">
                      [Bản chép lời ứng viên · Phiên bản bộ đề v1.2 · Đã lưu vết]
                    </p>
                    <p className="leading-relaxed">
                      “Trong dự án Dashboard React có bảng 2.000 dòng giao dịch, đầu tiên{" "}
                      <span
                        className={`rounded-md px-1.5 py-0.5 transition-all ${
                          evidenceOpen && activeEvidenceKey === "measure"
                            ? "border border-[#087F78] bg-[#087F78]/15 font-bold text-[#183153]"
                            : ""
                        }`}
                      >
                        mình dùng React DevTools Profiler và phép đo Interaction to Next Paint (INP) để ghi lại thao tác lọc nhanh, phát hiện ô tìm kiếm đặt state ở component cha làm toàn bộ 2.000 dòng render lại mất ~280ms mỗi lần gõ
                      </span>
                      . Sau đó mình{" "}
                      <span
                        className={`rounded-md px-1.5 py-0.5 transition-all ${
                          evidenceOpen && activeEvidenceKey === "change"
                            ? "border border-[#7963BE] bg-[#7963BE]/15 font-bold text-[#183153]"
                            : ""
                        }`}
                      >
                        tách state ô tìm kiếm xuống component riêng, kết hợp useDeferredValue và ảo hóa danh sách bằng @tanstack/react-virtual
                      </span>
                      .{" "}
                      <span
                        className={`rounded-md px-1.5 py-0.5 transition-all ${
                          evidenceOpen && activeEvidenceKey === "verify"
                            ? "border border-[#287A55] bg-[#287A55]/15 font-bold text-[#183153]"
                            : ""
                        }`}
                      >
                        Khi kiểm tra lại trên cùng tập dữ liệu 2.000 dòng, số component render lại giảm xuống chỉ còn 18 dòng hiển thị trên khung nhìn và thời gian phản hồi phím gõ giảm còn ~35ms
                      </span>
                      .”
                    </p>
                  </div>

                  {/* HR Review & Next Step Box */}
                  <div className="mt-4 rounded-2xl border border-[#287A55]/30 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#287A55]">
                        <GitBranch className="h-4 w-4" />
                        Khung xem xét của HR &amp; Bước tiếp theo
                      </span>
                      <span className="rounded-full bg-[#287A55]/12 px-2.5 py-0.5 text-[11px] font-bold text-[#287A55]">
                        HR duyệt chuyển vòng cuối
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-[#586779]">
                      HR kiểm tra bằng chứng trả lời, có thể ghi chú hoặc chỉnh sửa nhận định, sau đó mở lịch hẹn vòng cuối để ứng viên gặp trực tiếp Quản lý chuyên môn.
                    </p>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-[#DEE5ED] pt-4 text-xs text-[#586779]">
                  <span>
                    Mã vị trí: <strong className="text-[#183153]">JD-FE-2026</strong> · Nguồn câu hỏi: <strong className="text-[#7963BE]">FE_Performance_Playbook_v2.pdf</strong>
                  </span>
                  <span className="font-bold text-[#287A55]">
                    AI đề xuất · HR xem xét · Quản lý quyết định
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
