"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import PortalScene3D, {
  StaticPortalFallback,
  type ExceptionBranchId,
  type JourneyStage,
} from "@/components/Landing/PortalScene3D";
import ProductDemoSection from "@/components/Landing/ProductDemoSection";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  GitBranch,
  Menu,
  RotateCcw,
  RotateCw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

interface SubStepItem {
  name: string;
  actor: string;
  detail: string;
}

interface JourneyStageConfig {
  stage: Exclude<JourneyStage, 0>;
  num: string;
  laneTitle: string;
  title: string;
  summary: string;
  sceneCaption: string;
  statusTag: string;
  statusType: "approved" | "knowledge" | "candidate" | "action";
  roles: {
    ai: string;
    human: string;
    candidate: string;
  };
  transitionCondition: string;
  subSteps: SubStepItem[];
  expandedNotes: string[];
}

const JOURNEY_STAGES: JourneyStageConfig[] = [
  {
    stage: 1,
    num: "01",
    laneTitle: "Chặng 01 · Quản lý & HR chốt vị trí",
    title: "Chốt nhu cầu tuyển dụng",
    summary:
      "Quản lý nêu yêu cầu; AI hỗ trợ soạn JD; quản lý và HR duyệt; chuẩn bị bài đăng và khung giờ.",
    sceneCaption:
      "Các thẻ “Vai trò”, “Kỹ năng”, “Cấp độ” ghép thành JD. Hiện trạng thái chờ duyệt; sau xác nhận, JD mở thành bài đăng và lịch mở khung giờ.",
    statusTag: "Quản lý duyệt · HR xác nhận",
    statusType: "approved",
    roles: {
      ai: "Soạn bản nháp JD, đề xuất kỹ năng, cấp độ, trọng số và thời lượng từ nhu cầu quản lý.",
      human: "Quản lý xác nhận năng lực cần tuyển; HR xác nhận điều kiện tuyển, duyệt bài đăng và mở khung giờ.",
      candidate: "Xem bài đăng tuyển dụng (Việt/Anh/Hàn) qua link ứng tuyển gắn đúng vị trí.",
    },
    transitionCondition:
      "Chốt mã vị trí và phiên bản JD đã được Quản lý & HR xác nhận trước khi dùng để sinh bộ đề.",
    subSteps: [
      {
        name: "1. Nêu yêu cầu tuyển",
        actor: "Quản lý",
        detail: "Nêu vai trò, lĩnh vực và năng lực cần tuyển bằng tiếng Việt, Hàn hoặc Anh.",
      },
      {
        name: "2. Soạn JD & tiêu chí",
        actor: "AI hỗ trợ",
        detail: "Đề xuất mô tả công việc, kỹ năng, cấp độ và tiêu chí đánh giá đối chiếu chính sách.",
      },
      {
        name: "3. Chốt JD & tiêu chí",
        actor: "Quản lý & HR",
        detail: "Kiểm tra chỗ thiếu hoặc mâu thuẫn; nếu cần sửa sẽ quay lại bước soạn JD.",
      },
      {
        name: "4. Tạo bài đăng & HR mở khung giờ",
        actor: "HR phụ trách",
        detail: "Duyệt bài đăng đa ngôn ngữ kèm link ứng tuyển và mở khung giờ phỏng vấn theo đợt.",
      },
    ],
    expandedNotes: [
      "Có thể soạn nội dung Việt/Anh/Hàn.",
      "Link ứng tuyển gắn đúng vị trí.",
      "Có thể nhận CV trong lúc chuẩn bị bộ đề.",
      "Mở khung giờ không đồng nghĩa đã xác nhận lịch của ứng viên.",
    ],
  },
  {
    stage: 2,
    num: "02",
    laneTitle: "Chặng 02 · Kho tài liệu doanh nghiệp",
    title: "Chuẩn bị tri thức",
    summary: "Phân loại nội dung tài liệu theo mục đích sử dụng.",
    sceneCaption:
      "Tập tài liệu mở trang, tách vào 3 nhóm: Chính sách (bảng điều kiện), Kiến thức chuyên môn (đồ thị tri thức) và Câu hỏi có sẵn (ngân hàng câu hỏi).",
    statusTag: "Phân loại tới từng phần nội dung",
    statusType: "knowledge",
    roles: {
      ai: "Gợi ý tách đoạn nội dung, trích xuất khái niệm/thuật ngữ chuyên môn và chuẩn hóa câu hỏi mẫu.",
      human: "Kiểm tra phần mơ hồ, hết hiệu lực hoặc mâu thuẫn; xác nhận phạm vi tài liệu được phép dùng.",
      candidate: "Không bị hỏi kiến thức nội bộ chưa được cung cấp hoặc ngoài phạm vi vị trí.",
    },
    transitionCondition:
      "Mỗi phần nội dung giữ nguyên liên kết tới file, trang/mục và phiên bản; phần mâu thuẫn phải được người phụ trách xác nhận.",
    subSteps: [
      {
        name: "1. Kho tài liệu đầu vào & Phân loại từng phần",
        actor: "AI gợi ý · Người kiểm tra",
        detail: "Tiếp nhận sổ tay, tài liệu kỹ thuật, đề mẫu; tách từng phần theo đúng mục đích sử dụng.",
      },
      {
        name: "2. Nhánh Quy định & chính sách → Ràng buộc quy trình",
        actor: "HR xác nhận",
        detail: "Chuẩn hóa thời lượng, số vòng, điều kiện thi lại thành bảng điều kiện kiểm tra quy trình.",
      },
      {
        name: "3. Nhánh Tài liệu chuyên môn → Đồ thị tri thức",
        actor: "Quản lý chuyên môn",
        detail: "Trích xuất khái niệm (Vai trò → Kỹ năng → Khái niệm) kèm đoạn nguồn để làm căn cứ tạo câu hỏi.",
      },
      {
        name: "4. Nhánh Câu hỏi đã có sẵn → Ngân hàng câu hỏi",
        actor: "AI & Người duyệt",
        detail: "Trích xuất câu hỏi có sẵn, loại trùng và gắn kỹ năng, cấp độ, tiêu chí chấm.",
      },
    ],
    expandedNotes: [
      "Một tài liệu có thể chứa nhiều loại nội dung.",
      "Mỗi phần giữ nguồn, trang/mục và phiên bản.",
      "Phần mơ hồ hoặc mâu thuẫn cần người phụ trách kiểm tra.",
      "Chính sách chỉ được coi là kiến thức nghiệp vụ để hỏi khi phù hợp vị trí và đã được xác nhận.",
    ],
  },
  {
    stage: 3,
    num: "03",
    laneTitle: "Chặng 03 · Có nguồn và người duyệt",
    title: "Chuẩn bị bộ phỏng vấn",
    summary:
      "Dựa vào JD để chọn hoặc tạo câu hỏi có nguồn và tiêu chí chấm; người phụ trách duyệt trước khi sử dụng.",
    sceneCaption:
      "JD đứng cạnh đồ thị và ngân hàng câu hỏi. Lật một thẻ câu hỏi sẽ thấy: Kỹ năng cần đánh giá, Nguồn, Độ khó và Tiêu chí chấm.",
    statusTag: "Hoàn thành trước khi xác nhận lịch",
    statusType: "approved",
    roles: {
      ai: "Truy xuất đồ thị tri thức và ngân hàng câu hỏi đã chuẩn hóa để đề xuất câu hỏi kèm rubric.",
      human: "Quản lý duyệt độ đúng chuyên môn & tiêu chí chấm; HR duyệt quy trình và chốt phiên bản sử dụng.",
      candidate: "Tham gia phỏng vấn với bộ đề đã được kiểm duyệt và có tiêu chí rõ ràng.",
    },
    transitionCondition:
      "Chỉ phiên bản bộ đề đã được Quản lý & HR duyệt mới cho phép xác nhận lịch phỏng vấn của ứng viên.",
    subSteps: [
      {
        name: "1. Tạo / chọn bộ câu hỏi",
        actor: "AI hỗ trợ từ nguồn chuẩn",
        detail: "Kết hợp JD + đồ thị tri thức + ngân hàng câu hỏi đã chuẩn hóa (CV chưa tham gia bước tạo bộ đề chung này).",
      },
      {
        name: "2. Kiểm tra theo chính sách",
        actor: "Hệ thống & HR",
        detail: "Đối chiếu số câu, thời lượng, phạm vi và rubric với các quy định có hiệu lực.",
      },
      {
        name: "3. Duyệt bộ phỏng vấn",
        actor: "Quản lý & HR",
        detail: "Quản lý duyệt chuyên môn; HR duyệt quy trình; nếu chưa đạt sẽ quay lại bổ sung nguồn.",
      },
      {
        name: "4. Chốt phiên bản sử dụng",
        actor: "Hệ thống lưu vết",
        detail: "Khoá phiên bản câu hỏi cốt lõi, rubric chấm và phạm vi được phép hỏi tiếp.",
      },
    ],
    expandedNotes: [
      "Có câu hỏi: trích xuất và chọn.",
      "Có kiến thức: trích xuất rồi sinh.",
      "Có đồ thị: truy xuất rồi sinh.",
      "Thiếu nguồn hoặc tiêu chí thì quay lại bổ sung.",
      "Quản lý duyệt chuyên môn; HR duyệt quy trình.",
      "Chốt câu cốt lõi, phạm vi cá nhân hóa và quy tắc hỏi tiếp.",
    ],
  },
  {
    stage: 4,
    num: "04",
    laneTitle: "Chặng 04 · Ứng viên trên SpeakCV",
    title: "Hồ sơ ứng viên sẵn sàng",
    summary:
      "Ứng viên nộp CV; hệ thống tự điền hồ sơ SpeakCV; ứng viên kiểm tra và xác nhận đúng vị trí ứng tuyển.",
    sceneCaption:
      "CV chia thành “Kinh nghiệm”, “Kỹ năng”, “Dự án” di chuyển vào hồ sơ SpeakCV (không vào đồ thị tri thức chung). Chỗ thiếu được đánh dấu để bổ sung trước khi xác nhận.",
    statusTag: "Tự gắn JD theo đúng đơn ứng tuyển",
    statusType: "candidate",
    roles: {
      ai: "Đọc CV, trích xuất kỹ năng/kinh nghiệm/dự án để tự điền hồ sơ và ẩn thông tin nhận diện không cần thiết khi xét.",
      human: "HR tiếp nhận hồ sơ đã chuẩn hóa; không dùng tuổi hoặc giới tính để tính độ hợp việc.",
      candidate: "Kiểm tra nhanh dữ liệu tự điền, sửa chỗ thiếu, xem mức khớp tham khảo và xác nhận thông tin.",
    },
    transitionCondition:
      "Hồ sơ được ứng viên xác nhận và gắn đúng mã đơn ứng tuyển (application_id) cùng phiên bản JD tương ứng.",
    subSteps: [
      {
        name: "1. Ứng viên nộp CV & Đọc chuẩn hóa",
        actor: "Ứng viên & Hệ thống",
        detail: "Trích xuất thông tin có cấu trúc từ CV; ẩn thông tin nhận diện cá nhân trên màn hình xét duyệt.",
      },
      {
        name: "2. Tự điền hồ sơ SpeakCV",
        actor: "Hệ thống hỗ trợ",
        detail: "Điền vào hồ sơ tài khoản ứng viên; không tự ghi đè dữ liệu ứng viên đã xác nhận trước đó.",
      },
      {
        name: "3. Xác nhận thông tin & Gắn JD đang ứng tuyển",
        actor: "Ứng viên xác nhận",
        detail: "Bổ sung trường còn thiếu và tự động gắn đúng JD của đơn ứng tuyển (không tải lại JD).",
      },
      {
        name: "4. Xem độ hợp việc (Tham khảo)",
        actor: "Ứng viên chủ động",
        detail: "Xem điểm mạnh & khoảng thiếu để quyết định tiếp tục đặt lịch hoặc chủ động rút đơn.",
      },
    ],
    expandedNotes: [
      "Không ghi đè thông tin đã xác nhận một cách tùy tiện.",
      "Tự gắn JD theo đơn ứng tuyển.",
      "Ẩn thông tin nhận diện không cần thiết khi xét hồ sơ.",
      "Mức khớp công việc là thông tin tham khảo, không tự động loại.",
      "Ứng viên chọn tiếp tục hoặc chủ động rút đơn.",
    ],
  },
  {
    stage: 5,
    num: "05",
    laneTitle: "Chặng 05 · Phỏng vấn tuyển dụng thật",
    title: "Đặt lịch và phỏng vấn",
    summary:
      "Ứng viên chọn giờ và tham gia phiên phỏng vấn sử dụng đúng hồ sơ, JD, bộ đề đã duyệt.",
    sceneCaption:
      "Nhịp 1: Lịch mở ra, chọn ô giờ và xác nhận khi đủ điều kiện. Nhịp 2: Camera chuyển về bàn phỏng vấn; 3 thẻ Hồ sơ, JD, Bộ đề kết nối vào phiên cùng câu hỏi chính, câu trả lời và câu hỏi tiếp nối.",
    statusTag: "Câu hỏi cốt lõi + cá nhân hóa + hỏi tiếp",
    statusType: "action",
    roles: {
      ai: "Ghép ngữ cảnh (Hồ sơ + JD + Bộ đề đã duyệt) để hỏi câu cốt lõi, câu cá nhân hóa theo dự án CV và câu hỏi tiếp nối trong phạm vi cho phép.",
      human: "HR mở khung giờ và sẵn sàng tiếp nhận hỗ trợ nếu ứng viên không chọn phỏng vấn AI hoặc gặp sự cố.",
      candidate: "Chọn khung giờ phù hợp, nắm rõ thông báo ghi nhận và trả lời phỏng vấn bám sát kinh nghiệm thực tế.",
    },
    transitionCondition:
      "Chỉ xác nhận lịch khi cả 3 điều kiện đã sẵn sàng: Hồ sơ đã xác nhận + JD đúng đơn + Bộ phỏng vấn đã duyệt.",
    subSteps: [
      {
        name: "1. Đặt lịch phỏng vấn",
        actor: "Ứng viên & Hệ thống",
        detail: "Chọn giờ còn chỗ; nếu bộ đề chưa duyệt xong sẽ hiển thị trạng thái chờ thay vì tự xác nhận.",
      },
      {
        name: "2. Ghép ngữ cảnh để hỏi",
        actor: "SpeakCV",
        detail: "Kết nối Hồ sơ đã xác nhận + JD đúng đơn + Bộ câu hỏi đã duyệt (giữ riêng theo từng đơn).",
      },
      {
        name: "3. Phỏng vấn trên SpeakCV",
        actor: "SpeakCV & Ứng viên",
        detail: "Thông báo cách ghi nhận trước phiên; hỏi câu chính, lắng nghe trả lời và hỏi tiếp theo ngữ cảnh.",
      },
      {
        name: "4. Lưu phiên & bằng chứng",
        actor: "Hệ thống lưu trữ",
        detail: "Lưu bản ghi, bản chép lời, câu hỏi thực tế và phiên bản bộ đề/rubric đã dùng.",
      },
    ],
    expandedNotes: [
      "Lịch còn chỗ, có múi giờ, nhắc lịch và đổi/hủy.",
      "Nếu thiếu điều kiện, hiển thị chờ thay vì xác nhận.",
      "Thông báo hình thức ghi nhận trước phiên.",
      "Hỏi tiếp trong phạm vi đã duyệt.",
      "Có đường chuyển sang HR hỗ trợ.",
    ],
  },
  {
    stage: 6,
    num: "06",
    laneTitle: "Chặng 06 · Đối chiếu nguyên văn",
    title: "Đánh giá có bằng chứng",
    summary:
      "Lưu phiên; AI đề xuất nhận xét theo tiêu chí; HR kiểm tra bằng chứng và chọn bước tiếp.",
    sceneCaption:
      "Hội thoại thu thành báo cáo. Một nhận xét nối trực tiếp với đoạn trả lời liên quan; bấm nhận xét để làm nổi bật bằng chứng trước khi chuyển tới khung xem xét của HR.",
    statusTag: "Kèm trích dẫn câu trả lời",
    statusType: "action",
    roles: {
      ai: "Đề xuất nhận xét theo rubric đã duyệt, trích dẫn đoạn trả lời làm bằng chứng và đánh dấu chỗ chưa đủ dữ liệu.",
      human: "HR đọc bằng chứng, có quyền sửa nhận định của AI, yêu cầu đánh giá bổ sung hoặc chọn bước tiếp theo.",
      candidate: "Câu trả lời nguyên văn được giữ đúng ngữ cảnh để người phụ trách đối chiếu công bằng.",
    },
    transitionCondition:
      "Báo cáo phải giữ nguyên liên kết tới câu hỏi, câu trả lời nguyên văn và phiên bản rubric đã dùng để HR kiểm chứng.",
    subSteps: [
      {
        name: "1. AI đề xuất đánh giá",
        actor: "AI tổng hợp",
        detail: "Đối chiếu câu trả lời với rubric, đính kèm đoạn trích dẫn nguyên văn và đánh dấu nếu thiếu dữ liệu.",
      },
      {
        name: "2. HR xét hồ sơ & bằng chứng",
        actor: "HR phụ trách",
        detail: "Kiểm tra CV, nhận xét và bằng chứng trả lời; có thể chỉnh sửa nhận định và ghi rõ lý do.",
      },
    ],
    expandedNotes: [
      "Giữ câu hỏi, câu trả lời và phiên bản đã dùng.",
      "Đánh dấu khi chưa đủ dữ liệu.",
      "HR có thể sửa nhận định và yêu cầu đánh giá bổ sung.",
      "Không suy diễn cảm xúc hoặc năng lực từ giọng nói.",
    ],
  },
  {
    stage: 7,
    num: "07",
    laneTitle: "Chặng 07 · Con người ra quyết định",
    title: "Quyết định và bước tiếp theo",
    summary:
      "HR chọn bước tiếp; ứng viên đặt lịch vòng cuối; quản lý phỏng vấn và quyết định.",
    sceneCaption:
      "Lịch vòng cuối xuất hiện, tiếp đến là cuộc gặp với quản lý. Sau quyết định: nhánh phù hợp đi tới đề nghị nhận việc & kế hoạch 30/60/90 ngày; nhánh chưa phù hợp nhận phản hồi được HR duyệt.",
    statusTag: "Quản lý quyết định · Onboarding 30/60/90",
    statusType: "approved",
    roles: {
      ai: "Chuẩn bị bản tóm tắt đa ngôn ngữ (Việt/Hàn) kèm bằng chứng và gợi ý khung kế hoạch 30/60/90 ngày sau khi ứng viên nhận lời.",
      human: "HR mở lịch vòng cuối & duyệt thư phản hồi; Quản lý trực tiếp phỏng vấn vòng cuối và đưa ra quyết định tuyển dụng.",
      candidate: "Chọn lịch gặp quản lý ở vòng cuối; nhận đề nghị nhận việc và lộ trình hội nhập hoặc nhận thư phản hồi rõ ràng.",
    },
    transitionCondition:
      "Onboarding 30/60/90 ngày chỉ bắt đầu sau khi người có thẩm quyền quyết định tuyển và ứng viên chính thức nhận lời đề nghị.",
    subSteps: [
      {
        name: "1. Đặt lịch vòng cuối (Hoặc từ nhánh H1)",
        actor: "HR & Ứng viên",
        detail: "Mở lịch gặp trực tiếp quản lý chuyên môn (bao gồm cả trường hợp chuyển từ nhánh H1 không chọn AI).",
      },
      {
        name: "2. Quản lý phỏng vấn & ra quyết định",
        actor: "Quản lý chuyên môn",
        detail: "Xem bản tóm tắt (Việt/Hàn) cùng bằng chứng, phỏng vấn trực tiếp và đưa ra quyết định cuối cùng.",
      },
      {
        name: "3A. Nhánh phù hợp → Nhận việc & Onboarding",
        actor: "HR, Quản lý & Ứng viên",
        detail: "Gửi đề nghị nhận việc → ứng viên nhận lời → khởi tạo kế hoạch 30 / 60 / 90 ngày.",
      },
      {
        name: "3B. Nhánh chưa phù hợp → Phản hồi & lưu hồ sơ",
        actor: "HR duyệt",
        detail: "Gửi phản hồi đã được HR duyệt; chỉ lưu vào kho ứng viên khi có sự đồng ý và đúng thời hạn.",
      },
    ],
    expandedNotes: [
      "HR chọn bước tiếp; ứng viên đặt lịch vòng cuối; quản lý phỏng vấn và quyết định.",
      "Nhánh phù hợp: đề nghị nhận việc → ứng viên nhận lời → kế hoạch 30/60/90 ngày.",
      "Nhánh chưa phù hợp: phản hồi được HR duyệt.",
      "AI không bấm tuyển hoặc loại ứng viên.",
    ],
  },
];

interface ExceptionItem {
  id: Exclude<ExceptionBranchId, null>;
  num: string;
  title: string;
  badgeText: string;
  badgeColor: string;
  triggerStage: string;
  summary: string;
  handlingSteps: string[];
  guardrailNote: string;
  relatedStage: Exclude<JourneyStage, 0>;
}

const EXCEPTION_ITEMS: ExceptionItem[] = [
  {
    id: "needs_revision",
    num: "01",
    title: "JD hoặc bộ đề chưa đạt",
    badgeText: "Cần bổ sung",
    badgeColor: "#AD661B",
    triggerStage: "Xảy ra tại Chặng 01 (Chốt JD) hoặc Chặng 03 (Duyệt bộ phỏng vấn)",
    summary:
      "Thẻ quay về chỉnh sửa với nhãn “Cần bổ sung” khi thiếu tiêu chí, mâu thuẫn chính sách hoặc câu hỏi chưa có nguồn tài liệu rõ ràng.",
    handlingSteps: [
      "Đánh dấu cụ thể mục còn thiếu nguồn tham chiếu, độ khó hoặc tiêu chí chấm (rubric).",
      "Quay về bước soạn thảo để bổ sung tài liệu chuyên môn hoặc hiệu chỉnh JD.",
      "Chưa mở xác nhận lịch phỏng vấn cho đến khi phiên bản bộ đề được Quản lý và HR duyệt đạt.",
    ],
    guardrailNote:
      "Không dùng câu hỏi mẫu chưa xác minh nguồn hoặc chưa được duyệt để đưa vào phiên phỏng vấn thật.",
    relatedStage: 3,
  },
  {
    id: "withdrawn",
    num: "02",
    title: "Ứng viên rút đơn",
    badgeText: "Dừng ứng tuyển · Hủy lịch",
    badgeColor: "#B54747",
    triggerStage: "Xảy ra tại Chặng 04 (Sau khi xem độ hợp việc) hoặc trước phiên phỏng vấn",
    summary:
      "Hành trình dừng theo lựa chọn chủ động của ứng viên, lịch liên quan được hủy và hệ thống ngừng nhắc lịch.",
    handlingSteps: [
      "Ghi nhận trạng thái chủ động rút đơn cho đúng đơn ứng tuyển (application_id).",
      "Tự động giải phóng ô lịch phỏng vấn đã giữ chỗ (nếu có) và dừng toàn bộ thông báo nhắc lịch.",
      "Không tự động đẩy ứng viên quay lại bước đặt lịch của đơn đã rút.",
    ],
    guardrailNote:
      "Tôn trọng quyền chủ động dừng ứng tuyển của ứng viên ở mọi thời điểm.",
    relatedStage: 4,
  },
  {
    id: "human_alternative",
    num: "03",
    title: "Không chọn phỏng vấn AI",
    badgeText: "Điểm nối H1 · Đánh giá với người",
    badgeColor: "#7963BE",
    triggerStage: "Xảy ra tại Chặng 05 (Trước hoặc khi bắt đầu phiên phỏng vấn SpeakCV)",
    summary:
      "Chuyển sang HR bố trí đánh giá với người (điểm nối H1 trên sơ đồ). Không coi đây là rút đơn hoặc kém năng lực.",
    handlingSteps: [
      "Ứng viên chọn phương án không tham gia phiên phỏng vấn tự động với AI.",
      "Hệ thống chuyển luồng qua điểm nối H1 để HR liên hệ và sắp xếp buổi đánh giá trực tiếp với người.",
      "Hồ sơ đã xác nhận của ứng viên được giữ nguyên để phục vụ vòng phỏng vấn trực tiếp.",
    ],
    guardrailNote:
      "Tuyệt đối không đồng nhất việc từ chối phỏng vấn AI với việc rút đơn hay đánh giá thấp năng lực ứng viên.",
    relatedStage: 5,
  },
  {
    id: "tech_issue",
    num: "04",
    title: "Lỗi kỹ thuật",
    badgeText: "Giữ tiến độ · HR hỗ trợ",
    badgeColor: "#AD661B",
    triggerStage: "Xảy ra tại Chặng 05 (Trong quá trình diễn ra phiên phỏng vấn)",
    summary:
      "Giữ tiến độ các câu đã trả lời hợp lệ, HR hỗ trợ tiếp tục hoặc đặt lại lịch. Không tự áp dụng thời gian chờ 24 giờ.",
    handlingSteps: [
      "Bảo toàn toàn bộ phần câu trả lời hợp lệ đã được ghi nhận trước thời điểm phát sinh sự cố.",
      "Thông báo tới HR để hỗ trợ ứng viên nối tiếp phiên hoặc chọn lại khung giờ mới phù hợp.",
      "Không tự động khóa hay buộc ứng viên chờ 24 giờ do lỗi đường truyền hoặc thiết bị.",
    ],
    guardrailNote:
      "Quy định chờ (nếu có trong chính sách đợt tuyển) chỉ áp dụng theo đúng cấu hình của HR và luôn có quyền ngoại lệ do HR xử lý.",
    relatedStage: 5,
  },
  {
    id: "not_fitted",
    num: "05",
    title: "Chưa phù hợp",
    badgeText: "Phản hồi được HR duyệt",
    badgeColor: "#387BC1",
    triggerStage: "Xảy ra tại Chặng 06 (HR xét hồ sơ) hoặc Chặng 07 (Sau vòng phỏng vấn Quản lý)",
    summary:
      "Phản hồi được HR duyệt trước khi gửi. Chỉ lưu vào kho ứng viên theo sự đồng ý và thời hạn phù hợp.",
    handlingSteps: [
      "HR xem xét kết quả đánh giá và kiểm duyệt nội dung thư phản hồi lịch sự, rõ ràng cho ứng viên.",
      "Kết quả phiên phỏng vấn được gắn đúng đơn ứng tuyển và chỉ hiển thị cho người có thẩm quyền.",
      "Chỉ lưu hồ sơ vào kho ứng viên tiềm năng khi ứng viên đồng ý cho phép và trong thời hạn đã công bố.",
    ],
    guardrailNote:
      "AI không tự gửi thư từ chối và không tự ý lưu trữ hồ sơ ngoài phạm vi ứng viên đã đồng ý.",
    relatedStage: 7,
  },
];

export default function LandingPage() {
  const { user, isLoading } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeStage, setActiveStage] = useState<JourneyStage>(1);
  const [expandedStages, setExpandedStages] = useState<Record<number, boolean>>(
    {},
  );
  const [activeException, setActiveException] =
    useState<Exclude<ExceptionBranchId, null>>("needs_revision");
  const [inspectingExceptionIn3D, setInspectingExceptionIn3D] =
    useState<boolean>(false);
  const [questionCardFlipped, setQuestionCardFlipped] =
    useState<boolean>(false);
  const [evidenceHighlighted, setEvidenceHighlighted] =
    useState<boolean>(false);
  const [stage5Beat, setStage5Beat] = useState<1 | 2>(2);

  const stageCardRefs = useRef<Array<HTMLElement | null>>([]);

  // Observe the 7 journey stage cards so scrolling down or up updates the 3D scene smoothly
  useEffect(() => {
    const elements = stageCardRefs.current.filter(
      (el): el is HTMLElement => el !== null,
    );
    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const num = Number(
              entry.target.getAttribute("data-stage"),
            ) as JourneyStage;
            if (num >= 1 && num <= 7) {
              setActiveStage(num);
              setInspectingExceptionIn3D(false);
            }
          }
        });
      },
      {
        root: null,
        rootMargin: "-25% 0px -42% 0px",
        threshold: 0.15,
      },
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  const jumpToStage = (stageNum: Exclude<JourneyStage, 0>) => {
    setInspectingExceptionIn3D(false);
    setActiveStage(stageNum);
    const targetEl = document.getElementById(`chang-0${stageNum}`);
    if (targetEl) {
      targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const toggleStageDetail = (stageNum: number) => {
    setExpandedStages((prev) => ({
      ...prev,
      [stageNum]: !prev[stageNum],
    }));
  };

  const selectedExceptionObj =
    EXCEPTION_ITEMS.find((item) => item.id === activeException) ??
    EXCEPTION_ITEMS[0];

  return (
    <div className="min-h-screen bg-[#F7F8FA] text-[#183153] selection:bg-[#087F78] selection:text-white overflow-x-clip">
      {/* ============================================================
          A. THANH ĐIỀU HƯỚNG (NAVBAR)
         ============================================================ */}
      <header className="sticky top-0 z-50 border-b border-[#DEE5ED] bg-white/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1280px] items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
          {/* Brand Name: INTERVIEWPATH × SPEAKCV */}
          <Link
            href="/"
            className="inline-flex items-center gap-2.5 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78]"
          >
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#183153] text-xs font-extrabold tracking-wider text-white shadow-sm">
              IP
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-extrabold tracking-[0.1em] text-[#183153] sm:text-base">
                INTERVIEWPATH
              </span>
              <span className="rounded-md border border-[#087F78]/30 bg-[#087F78]/10 px-2 py-0.5 text-[11px] font-extrabold tracking-[0.08em] text-[#087F78]">
                × SPEAKCV
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav
            aria-label="Điều hướng chính"
            className="hidden items-center gap-5 lg:gap-6 md:flex whitespace-nowrap"
          >
            <a
              href="#giai-phap"
              className="text-sm font-semibold text-[#586779] transition hover:text-[#183153]"
            >
              Giải pháp
            </a>
            <a
              href="#quy-trinh"
              className="text-sm font-semibold text-[#586779] transition hover:text-[#183153]"
            >
              Quy trình
            </a>
            <a
              href="#phong-van-mau"
              className="text-sm font-semibold text-[#586779] transition hover:text-[#183153]"
            >
              Phỏng vấn mẫu
            </a>
            <a
              href="#ngoai-le"
              className="text-sm font-semibold text-[#586779] transition hover:text-[#183153]"
            >
              Xử lý tình huống
            </a>

            <span className="h-4 w-[1px] bg-[#DEE5ED]" aria-hidden="true" />

            {/* Real Application Routes */}
            <Link
              href="/jobs/backend-developer"
              className="text-sm font-semibold text-[#586779] transition hover:text-[#087F78]"
            >
              Vị trí tuyển dụng
            </Link>

            {!isLoading && user ? (
              <>
                <Link
                  href="/applications"
                  className="text-sm font-semibold text-[#586779] transition hover:text-[#183153]"
                >
                  Đơn ứng tuyển
                </Link>
                <Link
                  href="/profile"
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#087F78] px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-[#066660]"
                >
                  <span>Vào hồ sơ ứng dụng</span>
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="text-sm font-bold text-[#183153] transition hover:text-[#087F78]"
                >
                  Đăng nhập
                </Link>
                <a
                  href="#phong-van-mau"
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#087F78] px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-[#066660] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183153]"
                >
                  <span>Xem phiên phỏng vấn mẫu</span>
                  <ArrowUpRight className="h-4 w-4" />
                </a>
              </>
            )}
          </nav>

          {/* Mobile Menu Toggle */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-nav-drawer"
            aria-label={
              mobileMenuOpen ? "Đóng menu điều hướng" : "Mở menu điều hướng"
            }
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#DEE5ED] bg-[#F7F8FA] text-[#183153] transition hover:border-[#087F78] md:hidden"
          >
            {mobileMenuOpen ? (
              <X className="h-5 w-5 text-[#087F78]" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
        </div>

        {/* Mobile Menu Drawer */}
        {mobileMenuOpen && (
          <nav
            id="mobile-nav-drawer"
            aria-label="Menu di động"
            className="border-t border-[#DEE5ED] bg-white px-4 py-5 shadow-lg md:hidden"
          >
            <div className="flex flex-col space-y-2.5">
              <a
                href="#giai-phap"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-xl px-3 py-2 text-base font-bold text-[#183153] hover:bg-[#F7F8FA]"
              >
                Giải pháp
              </a>
              <a
                href="#quy-trinh"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-xl px-3 py-2 text-base font-bold text-[#183153] hover:bg-[#F7F8FA]"
              >
                Quy trình (7 chặng)
              </a>
              <a
                href="#phong-van-mau"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-xl px-3 py-2 text-base font-bold text-[#183153] hover:bg-[#F7F8FA]"
              >
                Phỏng vấn mẫu
              </a>
              <a
                href="#ngoai-le"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-xl px-3 py-2 text-base font-bold text-[#183153] hover:bg-[#F7F8FA]"
              >
                Khi quy trình thay đổi
              </a>

              <div className="my-2 h-[1px] bg-[#DEE5ED]" />

              <Link
                href="/jobs/backend-developer"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-xl px-3 py-2 text-sm font-semibold text-[#586779] hover:bg-[#F7F8FA] hover:text-[#183153]"
              >
                Vị trí ứng tuyển thực tế (/jobs/backend-developer)
              </Link>

              {!isLoading && user ? (
                <div className="grid grid-cols-2 gap-2.5 pt-1">
                  <Link
                    href="/applications"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center justify-center rounded-xl border border-[#DEE5ED] bg-[#F7F8FA] px-4 py-2.5 text-sm font-bold text-[#183153]"
                  >
                    Đơn ứng tuyển
                  </Link>
                  <Link
                    href="/profile"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center justify-center rounded-xl bg-[#087F78] px-4 py-2.5 text-sm font-bold text-white"
                  >
                    Hồ sơ SpeakCV
                  </Link>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2.5 pt-1">
                  <Link
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center justify-center rounded-xl border border-[#DEE5ED] bg-[#F7F8FA] px-4 py-2.5 text-sm font-bold text-[#183153]"
                  >
                    Đăng nhập
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center justify-center rounded-xl border border-[#087F78]/30 bg-[#087F78]/10 px-4 py-2.5 text-sm font-bold text-[#087F78]"
                  >
                    Đăng ký
                  </Link>
                </div>
              )}

              <a
                href="#phong-van-mau"
                onClick={() => setMobileMenuOpen(false)}
                className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-[#087F78] px-4 py-3 text-sm font-bold text-white shadow-sm"
              >
                <span>Xem phiên phỏng vấn mẫu</span>
                <ArrowUpRight className="h-4 w-4" />
              </a>
            </div>
          </nav>
        )}
      </header>

      <main>
        {/* ============================================================
            B. HERO — TOÀN BỘ HÀNH TRÌNH
            Desktop: Chữ bên trái, cảnh bàn phỏng vấn 3D đặt trực tiếp trong không gian Hero bên phải
           ============================================================ */}
        <section className="relative overflow-hidden border-b border-[#DEE5ED] bg-[#F7F8FA] pt-8 pb-14 sm:pt-12 sm:pb-16 lg:pt-14 lg:pb-20">
          {/* Vùng nền xanh nhạt rất nhẹ phía sau cảnh 3D để làm nổi vật thể */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(circle at 70% 50%, #E0EFEF 0%, rgba(247,248,250,0) 58%)",
            }}
          />

          <div className="relative mx-auto max-w-[1280px] px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 items-center gap-8 lg:grid-cols-12 lg:gap-6">
              {/* Left Column: Clean Headline, Description & 2 CTAs */}
              <div className="lg:col-span-5">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#087F78]/25 bg-white px-3.5 py-1.5 shadow-sm">
                  <span className="h-2 w-2 rounded-full bg-[#087F78]" />
                  <span className="text-xs font-bold tracking-wide text-[#087F78]">
                    Cuộc phỏng vấn được chuẩn bị từ tri thức và hồ sơ
                  </span>
                </div>

                <h1 className="mt-6 text-[1.9rem] font-extrabold leading-[1.24] tracking-[-0.02em] text-[#183153] sm:text-[2.65rem] sm:leading-[1.2] lg:text-[2.6rem] xl:text-[2.95rem] lg:leading-[1.22]">
                  <span className="block whitespace-nowrap">
                    Từ nhu cầu tuyển dụng
                  </span>
                  <span className="mt-1 block whitespace-nowrap text-[#087F78]">
                    đến cuộc phỏng vấn
                  </span>
                  <span className="mt-1 block text-[#087F78]">có cơ sở.</span>
                </h1>

                <p className="mt-5 max-w-[46ch] text-base leading-[1.72] text-[#586779] sm:text-lg">
                  Kết nối tri thức doanh nghiệp, hồ sơ ứng viên và phỏng vấn AI trong một quy trình có người kiểm soát.
                </p>

                {/* Two Required Hero Buttons */}
                <div className="mt-8 flex flex-wrap items-center gap-3.5">
                  <a
                    href="#quy-trinh"
                    className="inline-flex items-center gap-2 rounded-2xl bg-[#087F78] px-6 py-3.5 text-sm font-bold text-white shadow-[0_10px_25px_rgba(8,127,120,0.22)] transition hover:-translate-y-0.5 hover:bg-[#066660] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183153] sm:text-base"
                  >
                    <span>Khám phá quy trình</span>
                    <ArrowRight className="h-4 w-4" />
                  </a>

                  <a
                    href="#phong-van-mau"
                    className="inline-flex items-center gap-2 rounded-2xl border border-[#DEE5ED] bg-white px-6 py-3.5 text-sm font-bold text-[#183153] shadow-sm transition hover:border-[#087F78] hover:text-[#087F78] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78] sm:text-base"
                  >
                    <span>Xem phiên phỏng vấn mẫu</span>
                    <ArrowUpRight className="h-4 w-4 text-[#087F78]" />
                  </a>
                </div>
              </div>

              {/* Right Column: Open 3D Interview Table Scene (No enclosing card/frame) */}
              <div className="lg:col-span-7">
                <PortalScene3D
                  stage={0}
                  showControls={false}
                  className="h-[420px] sm:h-[500px] lg:h-[560px]"
                />
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================
            SECTION PHÂN VAI — AI LÀM PHẦN NÀO TRONG QUY TRÌNH? (#giai-phap)
            (Tách riêng xuống dưới Hero để Hero thoáng và tập trung vào cảnh 3D)
           ============================================================ */}
        <section
          id="giai-phap"
          aria-labelledby="roles-heading"
          className="border-b border-[#DEE5ED] bg-white py-12 sm:py-16"
        >
          <div className="mx-auto max-w-[1280px] px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <span className="text-xs font-extrabold uppercase tracking-wider text-[#087F78]">
                  Phân định rõ trách nhiệm
                </span>
                <h2
                  id="roles-heading"
                  className="mt-1 text-2xl font-extrabold text-[#183153] sm:text-3xl"
                >
                  Ai làm phần nào trong quy trình tuyển dụng?
                </h2>
              </div>
              <p className="max-w-md text-sm text-[#586779]">
                Màu sắc nhận diện nhất quán xuyên suốt các chặng để phân biệt rõ phần việc của AI, người phụ trách và ứng viên.
              </p>
            </div>

            <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
              <div className="rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-6">
                <div className="inline-flex items-center gap-2 rounded-full bg-[#7963BE]/12 px-3 py-1 text-xs font-bold text-[#7963BE]">
                  <span className="h-2 w-2 rounded-full bg-[#7963BE]" />
                  AI chuẩn bị &amp; tổng hợp
                </div>
                <h3 className="mt-3.5 text-lg font-extrabold text-[#183153]">
                  Chuẩn hóa tri thức &amp; trích dẫn bằng chứng
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-[#586779]">
                  Hỗ trợ soạn JD, phân loại tài liệu, gợi ý câu hỏi có nguồn, tiến hành phỏng vấn theo bộ đề đã duyệt và trích dẫn bằng chứng trả lời.
                </p>
              </div>

              <div className="rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-6">
                <div className="inline-flex items-center gap-2 rounded-full bg-[#287A55]/12 px-3 py-1 text-xs font-bold text-[#287A55]">
                  <span className="h-2 w-2 rounded-full bg-[#287A55]" />
                  Quản lý &amp; HR kiểm soát
                </div>
                <h3 className="mt-3.5 text-lg font-extrabold text-[#183153]">
                  Phê duyệt đầu vào &amp; ra quyết định cuối cùng
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-[#586779]">
                  Xác nhận tiêu chí JD, kiểm duyệt bộ câu hỏi trước khi mở lịch, đối chiếu bằng chứng trả lời và trực tiếp quyết định tuyển dụng.
                </p>
              </div>

              <div className="rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-6">
                <div className="inline-flex items-center gap-2 rounded-full bg-[#387BC1]/12 px-3 py-1 text-xs font-bold text-[#387BC1]">
                  <span className="h-2 w-2 rounded-full bg-[#387BC1]" />
                  Ứng viên chủ động
                </div>
                <h3 className="mt-3.5 text-lg font-extrabold text-[#183153]">
                  Kiểm tra hồ sơ tự điền &amp; chọn lịch hẹn
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-[#586779]">
                  Nộp CV để hệ thống hỗ trợ tự điền hồ sơ SpeakCV, rà soát thông tin trước khi xác nhận, đặt lịch và tham gia phỏng vấn tuyển dụng thật.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================
            C. HÀNH TRÌNH CHÍNH — 7 CHẶNG (#quy-trinh)
            Desktop: Chữ bên trái, cảnh 3D dùng lại ghim bên phải + thanh 01–07
            Mobile: Từng chặng xếp dọc: Tiêu đề → Cảnh minh họa → Giải thích
           ============================================================ */}
        <section
          id="quy-trinh"
          aria-labelledby="journey-heading"
          className="relative border-b border-[#DEE5ED] bg-[#F7F8FA] py-16 sm:py-24"
        >
          <div className="mx-auto max-w-[1280px] px-4 sm:px-6 lg:px-8">
            {/* Section Header + Sticky 01–07 Step Progress Bar */}
            <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
              <div className="max-w-3xl">
                <span className="inline-flex items-center gap-2 rounded-full border border-[#7963BE]/30 bg-[#7963BE]/10 px-3.5 py-1 text-xs font-bold text-[#7963BE]">
                  <GitBranch className="h-3.5 w-3.5" />
                  Hành trình tuyển dụng hoàn chỉnh · 7 chặng liên thông
                </span>
                <h2
                  id="journey-heading"
                  className="mt-3.5 text-3xl font-extrabold leading-[1.22] tracking-[-0.02em] text-[#183153] sm:text-4xl"
                >
                  Từng bước từ chốt nhu cầu, chuẩn bị tri thức đến quyết định tuyển dụng.
                </h2>
                <p className="mt-3 text-base leading-[1.7] text-[#586779]">
                  Cuộn trang hoặc bấm trực tiếp vào các mốc <strong>01–07</strong> để di chuyển tới từng chặng. Ở mỗi chặng, bấm <strong>“Xem chi tiết bước này”</strong> để mở các bước con, vai trò phụ trách và điều kiện chuyển bước.
                </p>
              </div>

              {/* Step Marker Bar 01–07 */}
              <div
                role="navigation"
                aria-label="Chọn nhanh 7 chặng hành trình"
                className="flex flex-wrap items-center gap-1.5 rounded-2xl border border-[#DEE5ED] bg-white p-2 shadow-sm"
              >
                {JOURNEY_STAGES.map((s) => {
                  const isCurrent =
                    !inspectingExceptionIn3D && activeStage === s.stage;
                  return (
                    <button
                      key={s.stage}
                      type="button"
                      onClick={() => jumpToStage(s.stage)}
                      aria-label={`Đi tới Chặng ${s.num}: ${s.title}`}
                      aria-current={isCurrent ? "step" : undefined}
                      className={`inline-flex h-9 w-9 items-center justify-center rounded-xl font-mono text-xs font-extrabold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78] ${
                        isCurrent
                          ? "bg-[#087F78] text-white shadow-sm"
                          : "bg-[#F7F8FA] text-[#586779] hover:bg-[#EBF4F3] hover:text-[#183153]"
                      }`}
                    >
                      {s.num}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Main 2-Column Scrollytelling Grid */}
            <div className="mt-10 grid grid-cols-1 gap-8 lg:mt-12 lg:grid-cols-12 lg:items-start lg:gap-10">
              {/* Left Column: 7 Journey Stage Cards */}
              <div className="space-y-6 lg:col-span-6">
                {JOURNEY_STAGES.map((item, idx) => {
                  const isCurrent =
                    !inspectingExceptionIn3D && activeStage === item.stage;
                  const isExpanded = Boolean(expandedStages[item.stage]);

                  const badgeColors = {
                    approved:
                      "border-[#287A55]/30 bg-[#287A55]/10 text-[#287A55]",
                    knowledge:
                      "border-[#7963BE]/30 bg-[#7963BE]/10 text-[#7963BE]",
                    candidate:
                      "border-[#387BC1]/30 bg-[#387BC1]/10 text-[#387BC1]",
                    action:
                      "border-[#087F78]/30 bg-[#087F78]/10 text-[#087F78]",
                  }[item.statusType];

                  return (
                    <article
                      key={item.stage}
                      id={`chang-0${item.stage}`}
                      ref={(el) => {
                        stageCardRefs.current[idx] = el;
                      }}
                      data-stage={item.stage}
                      onClick={() => {
                        setInspectingExceptionIn3D(false);
                        setActiveStage(item.stage);
                      }}
                      className={`scroll-mt-24 rounded-3xl border bg-white p-6 transition-all sm:p-7 ${
                        isCurrent
                          ? "border-[#087F78] ring-2 ring-[#087F78]/15 shadow-[0_16px_40px_rgba(24,49,83,0.08)]"
                          : "border-[#DEE5ED] hover:border-[#183153]/30"
                      }`}
                    >
                      {/* Stage Header */}
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-3">
                          <span
                            className={`inline-flex h-9 w-9 items-center justify-center rounded-xl font-mono text-sm font-extrabold ${
                              isCurrent
                                ? "bg-[#087F78] text-white"
                                : "bg-[#F7F8FA] text-[#183153] border border-[#DEE5ED]"
                            }`}
                          >
                            {item.num}
                          </span>
                          <span className="text-xs font-bold uppercase tracking-wider text-[#586779]">
                            {item.laneTitle}
                          </span>
                        </div>

                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${badgeColors}`}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          <span>{item.statusTag}</span>
                        </span>
                      </div>

                      {/* 1. Title */}
                      <h3 className="mt-4 text-xl font-extrabold leading-[1.3] text-[#183153] sm:text-2xl">
                        {item.title}
                      </h3>

                      {/* 2. Mobile-Only Stacked Visual Illustration (Tiêu đề → Hình/cảnh → Giải thích) */}
                      <div className="mt-4 block lg:hidden">
                        <div className="h-[220px] w-full">
                          <StaticPortalFallback stage={item.stage} />
                        </div>
                      </div>

                      {/* 3. Short Explanation */}
                      <p className="mt-3 text-base font-medium leading-[1.68] text-[#183153]">
                        {item.summary}
                      </p>

                      {/* Scene Action Description Box */}
                      <div className="mt-3.5 rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-3.5">
                        <p className="text-xs font-bold uppercase tracking-wider text-[#087F78]">
                          Diễn biến trên bàn phỏng vấn:
                        </p>
                        <p className="mt-1 text-xs leading-relaxed text-[#586779]">
                          {item.sceneCaption}
                        </p>

                        {/* Stage-specific interactive motion triggers */}
                        {item.stage === 3 && (
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveStage(3);
                                setQuestionCardFlipped((prev) => !prev);
                              }}
                              aria-pressed={questionCardFlipped}
                              className="inline-flex items-center gap-1.5 rounded-xl bg-[#7963BE] px-3.5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#6650a8]"
                            >
                              <RotateCw className="h-3.5 w-3.5" />
                              <span>
                                {questionCardFlipped
                                  ? "Đang xem mặt sau thẻ (Kỹ năng · Nguồn · Độ khó · Tiêu chí)"
                                  : "Lật xem mặt sau: Điểm cần nghe & Bằng chứng"}
                              </span>
                            </button>
                          </div>
                        )}

                        {item.stage === 5 && (
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveStage(5);
                                setStage5Beat(1);
                              }}
                              className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${
                                stage5Beat === 1
                                  ? "bg-[#087F78] text-white"
                                  : "border border-[#DEE5ED] bg-white text-[#183153]"
                              }`}
                            >
                              Nhịp 1: Chọn ô giờ &amp; Xác nhận lịch
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveStage(5);
                                setStage5Beat(2);
                              }}
                              className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${
                                stage5Beat === 2
                                  ? "bg-[#087F78] text-white"
                                  : "border border-[#DEE5ED] bg-white text-[#183153]"
                              }`}
                            >
                              Nhịp 2: Ghép Hồ sơ + JD + Bộ đề tại bàn phỏng vấn
                            </button>
                          </div>
                        )}

                        {item.stage === 6 && (
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveStage(6);
                                setEvidenceHighlighted((prev) => !prev);
                              }}
                              aria-pressed={evidenceHighlighted}
                              className="inline-flex items-center gap-1.5 rounded-xl bg-[#087F78] px-3.5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#066660]"
                            >
                              <Sparkles className="h-3.5 w-3.5" />
                              <span>
                                {evidenceHighlighted
                                  ? "Đang làm nổi bật bằng chứng trả lời trên báo cáo"
                                  : "Bấm nhận xét để làm nổi bật bằng chứng"}
                              </span>
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Expandable Button: "Xem chi tiết bước này" */}
                      <div className="mt-4 flex items-center justify-between border-t border-[#DEE5ED] pt-4">
                        <span className="text-xs font-semibold text-[#586779]">
                          {item.subSteps.length} bước con · Vai trò &amp; điều kiện chuyển bước
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleStageDetail(item.stage);
                          }}
                          aria-expanded={isExpanded}
                          aria-controls={`stage-details-${item.stage}`}
                          className="inline-flex items-center gap-1.5 rounded-xl border border-[#DEE5ED] bg-[#F7F8FA] px-3.5 py-2 text-xs font-bold text-[#183153] transition hover:border-[#087F78] hover:text-[#087F78] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78]"
                        >
                          <span>Xem chi tiết bước này</span>
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </button>
                      </div>

                      {/* Expanded Sub-steps, Roles & Guardrails */}
                      {isExpanded && (
                        <div
                          id={`stage-details-${item.stage}`}
                          className="mt-4 space-y-4 border-t border-[#DEE5ED] pt-4"
                        >
                          {/* Sub-steps list */}
                          <div>
                            <p className="text-xs font-bold uppercase tracking-wider text-[#183153]">
                              Các bước con trong chặng {item.num}:
                            </p>
                            <div className="mt-2.5 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                              {item.subSteps.map((sub) => (
                                <div
                                  key={sub.name}
                                  className="rounded-xl border border-[#DEE5ED] bg-[#F7F8FA] p-3"
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-bold text-[#183153]">
                                      {sub.name}
                                    </span>
                                    <span className="rounded-md bg-white px-2 py-0.5 text-[10px] font-bold text-[#087F78] border border-[#DEE5ED]">
                                      {sub.actor}
                                    </span>
                                  </div>
                                  <p className="mt-1 text-xs leading-relaxed text-[#586779]">
                                    {sub.detail}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Roles Breakdown */}
                          <div className="grid grid-cols-1 gap-2.5 rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-3.5 sm:grid-cols-3">
                            <div>
                              <span className="text-[11px] font-bold text-[#7963BE]">
                                Vai trò của AI:
                              </span>
                              <p className="mt-0.5 text-xs leading-relaxed text-[#586779]">
                                {item.roles.ai}
                              </p>
                            </div>
                            <div>
                              <span className="text-[11px] font-bold text-[#287A55]">
                                Người phụ trách (HR / Quản lý):
                              </span>
                              <p className="mt-0.5 text-xs leading-relaxed text-[#586779]">
                                {item.roles.human}
                              </p>
                            </div>
                            <div>
                              <span className="text-[11px] font-bold text-[#387BC1]">
                                Phía ứng viên:
                              </span>
                              <p className="mt-0.5 text-xs leading-relaxed text-[#586779]">
                                {item.roles.candidate}
                              </p>
                            </div>
                          </div>

                          {/* Expanded Domain Notes & Transition Condition */}
                          <div className="rounded-2xl border border-[#287A55]/25 bg-[#287A55]/5 p-3.5">
                            <p className="text-xs font-bold text-[#287A55]">
                              Điều kiện chuyển bước &amp; lưu ý nghiệp vụ:
                            </p>
                            <p className="mt-1 text-xs font-semibold text-[#183153]">
                              {item.transitionCondition}
                            </p>
                            <ul className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                              {item.expandedNotes.map((note) => (
                                <li
                                  key={note}
                                  className="flex items-start gap-1.5 text-xs text-[#586779]"
                                >
                                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#087F78]" />
                                  <span>{note}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>

              {/* Right Column: Single Reusable Sticky 3D Viewport on Desktop */}
              <div className="hidden lg:col-span-6 lg:sticky lg:top-24 lg:block">
                <div
                  className="relative"
                  style={{
                    background:
                      "radial-gradient(circle at 50% 52%, #E2F0EF 0%, rgba(247,248,250,0) 68%)",
                  }}
                >
                  {/* Top Bar: Step 01-07 Quick Switcher */}
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-[#DEE5ED] bg-white/90 px-4 py-2.5 shadow-sm backdrop-blur-sm">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full bg-[#087F78]" />
                      <span className="text-xs font-bold text-[#183153]">
                        {inspectingExceptionIn3D
                          ? `Ngoại lệ: ${selectedExceptionObj.title}`
                          : `Chặng 0${activeStage} / 07 — ${
                              JOURNEY_STAGES.find((s) => s.stage === activeStage)
                                ?.title
                            }`}
                      </span>
                    </div>

                    <div className="flex items-center gap-1">
                      {JOURNEY_STAGES.map((s) => (
                        <button
                          key={s.stage}
                          type="button"
                          onClick={() => jumpToStage(s.stage)}
                          className={`h-7 w-7 rounded-lg font-mono text-xs font-extrabold transition ${
                            !inspectingExceptionIn3D && activeStage === s.stage
                              ? "bg-[#087F78] text-white"
                              : "bg-[#F7F8FA] text-[#586779] border border-[#DEE5ED] hover:text-[#183153]"
                          }`}
                        >
                          {s.num}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Single Shared Desktop 3D Scene (Open, unboxed) */}
                  <PortalScene3D
                    stage={
                      inspectingExceptionIn3D
                        ? selectedExceptionObj.relatedStage
                        : activeStage
                    }
                    exceptionBranch={
                      inspectingExceptionIn3D ? activeException : null
                    }
                    questionCardFlipped={questionCardFlipped}
                    onToggleQuestionFlip={() =>
                      setQuestionCardFlipped((prev) => !prev)
                    }
                    evidenceHighlighted={evidenceHighlighted}
                    onToggleEvidenceHighlight={() =>
                      setEvidenceHighlighted((prev) => !prev)
                    }
                    stage5Beat={stage5Beat}
                    onChangeStage5Beat={(b) => setStage5Beat(b)}
                    showControls={true}
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================
            D. DEMO XUYÊN SUỐT — FRONTEND DEVELOPER (#phong-van-mau)
           ============================================================ */}
        <section
          id="phong-van-mau"
          aria-labelledby="demo-section-heading"
          className="border-b border-[#DEE5ED] bg-white py-16 sm:py-24"
        >
          <div className="mx-auto max-w-[1280px] px-4 sm:px-6 lg:px-8">
            <div className="mb-10 flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
              <div className="max-w-2xl">
                <span className="inline-flex items-center gap-2 rounded-full border border-[#087F78]/30 bg-[#087F78]/10 px-3.5 py-1 text-xs font-bold text-[#087F78]">
                  <Sparkles className="h-3.5 w-3.5" />
                  Demo xuyên suốt · Vị trí Frontend Developer
                </span>
                <h2
                  id="demo-section-heading"
                  className="mt-3.5 text-3xl font-extrabold leading-[1.22] tracking-[-0.02em] text-[#183153] sm:text-4xl"
                >
                  Từ câu hỏi có nguồn đến câu trả lời và bằng chứng trích dẫn.
                </h2>
              </div>
              <p className="max-w-[48ch] text-sm leading-[1.7] text-[#586779] sm:text-base">
                Cùng một ví dụ xuyên suốt cho vị trí <strong>Frontend Developer</strong>: JD yêu cầu React và tối ưu hiệu năng, CV ứng viên có dự án React, bộ câu hỏi chuẩn bị từ tài liệu chuyên môn và báo cáo trích đúng đoạn trả lời liên quan.
              </p>
            </div>

            <ProductDemoSection />
          </div>
        </section>

        {/* ============================================================
            E. KHI QUY TRÌNH THAY ĐỔI — 5 NHÁNH NGOẠI LỆ (#ngoai-le)
            Hiển thị một nhánh được chọn tại một thời điểm + nút Quay về hành trình chính
           ============================================================ */}
        <section
          id="ngoai-le"
          aria-labelledby="exception-heading"
          className="border-b border-[#DEE5ED] bg-[#F7F8FA] py-16 sm:py-24"
        >
          <div className="mx-auto max-w-[1280px] px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
              <div className="max-w-3xl">
                <span className="inline-flex items-center gap-2 rounded-full border border-[#AD661B]/35 bg-[#AD661B]/10 px-3.5 py-1 text-xs font-bold text-[#AD661B]">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  Khi quy trình thay đổi · Xử lý ngoại lệ minh bạch
                </span>
                <h2
                  id="exception-heading"
                  className="mt-3.5 text-3xl font-extrabold leading-[1.22] tracking-[-0.02em] text-[#183153] sm:text-4xl"
                >
                  Mọi tình huống phát sinh đều có điểm kiểm soát và hướng xử lý riêng.
                </h2>
                <p className="mt-3 text-base leading-[1.7] text-[#586779]">
                  Bấm chọn một trong 5 tình huống bên dưới để xem cách hệ thống và HR xử lý mà không làm mất dữ liệu hay đánh đồng các trường hợp khác nhau.
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  setInspectingExceptionIn3D(false);
                  jumpToStage(selectedExceptionObj.relatedStage);
                }}
                className="inline-flex items-center gap-2 self-start rounded-2xl border border-[#DEE5ED] bg-white px-4 py-2.5 text-xs font-bold text-[#183153] shadow-sm transition hover:border-[#087F78] hover:text-[#087F78] lg:self-auto"
              >
                <RotateCcw className="h-4 w-4 text-[#087F78]" />
                <span>Quay về hành trình chính (Chặng 0{selectedExceptionObj.relatedStage})</span>
              </button>
            </div>

            {/* 5 Exception Selector Buttons */}
            <div
              role="tablist"
              aria-label="5 nhánh xử lý khi quy trình thay đổi"
              className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5"
            >
              {EXCEPTION_ITEMS.map((ex) => {
                const isSelected = ex.id === activeException;
                return (
                  <button
                    key={ex.id}
                    type="button"
                    role="tab"
                    id={`exception-tab-${ex.id}`}
                    aria-selected={isSelected}
                    aria-controls={`exception-panel-${ex.id}`}
                    onClick={() => {
                      setActiveException(ex.id);
                      setInspectingExceptionIn3D(true);
                    }}
                    className={`flex flex-col justify-between rounded-2xl border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F78] ${
                      isSelected
                        ? "border-[#183153] bg-white shadow-[0_12px_30px_rgba(24,49,83,0.08)]"
                        : "border-[#DEE5ED] bg-white/70 hover:border-[#183153]/30 hover:bg-white"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-extrabold text-[#586779]">
                        Tình huống {ex.num}
                      </span>
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: ex.badgeColor }}
                      />
                    </div>
                    <p className="mt-2.5 text-sm font-extrabold text-[#183153]">
                      {ex.title}
                    </p>
                    <span
                      className="mt-3 inline-block self-start rounded-full px-2.5 py-0.5 text-[11px] font-bold text-white"
                      style={{ backgroundColor: ex.badgeColor }}
                    >
                      {ex.badgeText}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Single Selected Exception Detail Panel (1 branch shown at a time for clarity) */}
            <div
              id={`exception-panel-${selectedExceptionObj.id}`}
              role="tabpanel"
              aria-labelledby={`exception-tab-${selectedExceptionObj.id}`}
              className="mt-6 rounded-3xl border border-[#DEE5ED] bg-white p-6 shadow-sm sm:p-8"
            >
              <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:items-center">
                <div className="lg:col-span-7">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span
                      className="rounded-full px-3 py-1 text-xs font-bold text-white"
                      style={{
                        backgroundColor: selectedExceptionObj.badgeColor,
                      }}
                    >
                      {selectedExceptionObj.badgeText}
                    </span>
                    <span className="text-xs font-semibold text-[#586779]">
                      {selectedExceptionObj.triggerStage}
                    </span>
                  </div>

                  <h3 className="mt-3.5 text-2xl font-extrabold text-[#183153]">
                    {selectedExceptionObj.num}. {selectedExceptionObj.title}
                  </h3>

                  <p className="mt-2.5 text-base font-medium leading-[1.68] text-[#183153]">
                    {selectedExceptionObj.summary}
                  </p>

                  <div className="mt-5 space-y-2.5">
                    {selectedExceptionObj.handlingSteps.map((step, i) => (
                      <div
                        key={step}
                        className="flex items-start gap-3 rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-3.5"
                      >
                        <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#183153] font-mono text-xs font-bold text-white">
                          {i + 1}
                        </span>
                        <p className="text-sm leading-relaxed text-[#183153]">
                          {step}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Right Guardrail Card & Return Button */}
                <div className="lg:col-span-5">
                  <div className="rounded-2xl border border-[#DEE5ED] bg-[#F7F8FA] p-6">
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#183153]">
                      <ShieldCheck className="h-4 w-4 text-[#087F78]" />
                      <span>Nguyên tắc bảo vệ quy trình &amp; ứng viên</span>
                    </div>

                    <p className="mt-3 text-sm font-semibold leading-relaxed text-[#183153]">
                      “{selectedExceptionObj.guardrailNote}”
                    </p>

                    <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-[#DEE5ED] pt-4">
                      <button
                        type="button"
                        onClick={() =>
                          jumpToStage(selectedExceptionObj.relatedStage)
                        }
                        className="inline-flex items-center gap-2 rounded-xl bg-[#087F78] px-4 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-[#066660]"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        <span>
                          Quay về Chặng 0{selectedExceptionObj.relatedStage} trong hành trình chính
                        </span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================
            F. CTA CUỐI TRANG
           ============================================================ */}
        <section
          aria-labelledby="final-cta-heading"
          className="bg-white py-16 sm:py-24"
        >
          <div className="mx-auto max-w-[1280px] px-4 sm:px-6 lg:px-8">
            <div className="rounded-3xl border border-[#DEE5ED] bg-gradient-to-b from-[#EBF4F3] to-[#F7F8FA] p-8 text-center shadow-[0_18px_50px_rgba(24,49,83,0.06)] sm:p-14">
              <span className="inline-flex items-center gap-2 rounded-full border border-[#087F78]/30 bg-white px-3.5 py-1 text-xs font-bold text-[#087F78]">
                INTERVIEWPATH × SPEAKCV
              </span>

              <h2
                id="final-cta-heading"
                className="mt-4 text-3xl font-extrabold leading-[1.2] tracking-[-0.02em] text-[#183153] sm:text-5xl"
              >
                Kết nối tri thức. Hiểu rõ ứng viên.
              </h2>

              <p className="mx-auto mt-4 max-w-2xl text-base leading-[1.7] text-[#586779] sm:text-lg">
                Chuẩn bị bộ phỏng vấn có nguồn, cá nhân hóa theo hồ sơ ứng viên và tổng hợp bằng chứng rõ ràng để người phụ trách đưa ra quyết định.
              </p>

              <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
                <a
                  href="#phong-van-mau"
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#087F78] px-7 py-4 text-base font-bold text-white shadow-[0_12px_28px_rgba(8,127,120,0.25)] transition hover:-translate-y-0.5 hover:bg-[#066660] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183153]"
                >
                  <span>Xem phiên phỏng vấn mẫu</span>
                  <ArrowRight className="h-5 w-5" />
                </a>

                <Link
                  href="/jobs/backend-developer"
                  className="inline-flex items-center gap-2 rounded-2xl border border-[#DEE5ED] bg-white px-6 py-4 text-sm font-bold text-[#183153] shadow-sm transition hover:border-[#087F78] hover:text-[#087F78] sm:text-base"
                >
                  <span>Vào trang vị trí tuyển dụng thật</span>
                  <ArrowUpRight className="h-4 w-4 text-[#087F78]" />
                </Link>
              </div>

              {/* Real Application Routes */}
              <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 border-t border-[#DEE5ED] pt-6 text-xs font-semibold text-[#586779] sm:text-sm">
                <span>Lối vào ứng dụng hiện có:</span>
                <Link
                  href="/login"
                  className="font-bold text-[#183153] hover:text-[#087F78]"
                >
                  Đăng nhập (/login)
                </Link>
                <span aria-hidden="true">·</span>
                <Link
                  href="/register"
                  className="font-bold text-[#183153] hover:text-[#087F78]"
                >
                  Đăng ký (/register)
                </Link>
                <span aria-hidden="true">·</span>
                <Link
                  href="/profile"
                  className="font-bold text-[#183153] hover:text-[#087F78]"
                >
                  Hồ sơ SpeakCV (/profile)
                </Link>
                <span aria-hidden="true">·</span>
                <Link
                  href="/applications"
                  className="font-bold text-[#183153] hover:text-[#087F78]"
                >
                  Đơn ứng tuyển (/applications)
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ============================================================
          FOOTER (Chỉ dùng thông tin và đường dẫn thật của dự án)
         ============================================================ */}
      <footer className="border-t border-[#DEE5ED] bg-[#F7F8FA] py-12 text-sm text-[#586779]">
        <div className="mx-auto max-w-[1280px] px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col justify-between gap-8 md:flex-row md:items-center">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[#183153] text-xs font-extrabold text-white">
                  IP
                </span>
                <span className="font-extrabold tracking-[0.1em] text-[#183153]">
                  INTERVIEWPATH × SPEAKCV
                </span>
              </div>
              <p className="mt-2 max-w-md text-xs leading-relaxed text-[#586779]">
                Hệ thống chuẩn bị tri thức tuyển dụng, tổ chức phỏng vấn tuyển dụng thật trên SpeakCV và tổng hợp bằng chứng trả lời cho đội ngũ tuyển dụng.
              </p>
            </div>

            <div className="flex flex-wrap gap-x-10 gap-y-4">
              <div className="flex flex-col space-y-2">
                <span className="text-xs font-extrabold uppercase tracking-wider text-[#183153]">
                  Mục trên trang
                </span>
                <a
                  href="#giai-phap"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Giải pháp
                </a>
                <a
                  href="#quy-trinh"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Hành trình 7 chặng
                </a>
                <a
                  href="#phong-van-mau"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Phỏng vấn mẫu Frontend Developer
                </a>
                <a
                  href="#ngoai-le"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Khi quy trình thay đổi
                </a>
              </div>

              <div className="flex flex-col space-y-2">
                <span className="text-xs font-extrabold uppercase tracking-wider text-[#183153]">
                  Route ứng dụng thật
                </span>
                <Link
                  href="/jobs/backend-developer"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Trang vị trí tuyển dụng (/jobs/backend-developer)
                </Link>
                <Link
                  href="/profile"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Hồ sơ ứng viên (/profile)
                </Link>
                <Link
                  href="/applications"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Đơn ứng tuyển (/applications)
                </Link>
                <Link
                  href="/login"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Đăng nhập (/login)
                </Link>
                <Link
                  href="/register"
                  className="text-xs font-medium text-[#586779] hover:text-[#087F78]"
                >
                  Đăng ký (/register)
                </Link>
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-[#DEE5ED] pt-6 text-xs text-[#586779]">
            <span>
              © {new Date().getFullYear()} INTERVIEWPATH × SPEAKCV. AI đề xuất đánh giá kèm bằng chứng; HR xem xét và Quản lý ra quyết định.
            </span>
            <span className="font-semibold text-[#183153]">
              Chính sách ràng buộc quy trình · Kiến thức chuyên môn làm căn cứ hỏi
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
