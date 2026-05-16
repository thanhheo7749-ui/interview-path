## Context

SpeakCV là nền tảng luyện phỏng vấn AI với flow hiện tại: User nói (mic) → Groq Whisper transcribe → Gemini/OpenAI chat → Edge TTS audio response. Giao diện hiện tại chỉ có MicroButton + ChatBox text-based. User muốn thêm chế độ "video call" mô phỏng phỏng vấn face-to-face, hiển thị webcam user + avatar AI HR.

Frontend sử dụng Next.js + TailwindCSS. Backend sử dụng FastAPI. Tất cả interview logic nằm trong `src/backend/app/routers/interview.py` và frontend interview components tại `src/frontend/components/Interview/`.

## Goals / Non-Goals

**Goals:**
- Thêm giao diện "Phỏng vấn Camera" dạng full-screen overlay có webcam user + AI avatar
- AI avatar là SVG illustration phong cách HR chuyên nghiệp với lip-sync animation
- Layout responsive: desktop side-by-side, mobile kiểu Zalo video call (AI full + user PiP)
- Reuse 100% backend APIs hiện có, không cần endpoint mới
- MVP approach: animation đơn giản bằng CSS + Web Audio API

**Non-Goals:**
- Không ghi hình/lưu video (chỉ real-time preview)
- Không dùng 3D engine (Three.js, Ready Player Me) ở giai đoạn MVP
- Không thay đổi flow phỏng vấn backend
- Không thêm tính năng face detection/emotion recognition
- Không hỗ trợ virtual background

## Decisions

### 1. Full-screen Modal Overlay vs. Separate Page

**Chọn: Full-screen Modal Overlay**

- **Lý do**: Giữ được context của Sidebar (lịch sử, công cụ). User có thể đóng modal quay lại chế độ phỏng vấn text bất kỳ lúc nào. Không cần tạo page/route mới.
- **Thay vì**: Tạo `/interview/camera` page riêng — phức tạp hơn, mất context sidebar, cần duplicate state management.

### 2. SVG Animation vs. Canvas vs. Lottie cho Avatar

**Chọn: SVG + CSS Animation**

- **Lý do**: Nhẹ nhất, không cần thêm dependency. SVG dễ style theo theme. CSS animation cho lip-sync (transform scaleY trên mouth element), blink (opacity), breathing (subtle scale). Performance tốt trên mobile.
- **Thay vì Canvas**: Overkill cho animation đơn giản, cần manual render loop.
- **Thay vì Lottie**: Cần thêm lottie-react dependency + tạo After Effects animation file.

### 3. Lip-sync approach: Audio Amplitude Analysis

**Chọn: Web Audio API AnalyserNode**

- Kết nối TTS audio output → AudioContext → AnalyserNode → getByteFrequencyData()
- Map average amplitude (0-255) → mouth openness (scaleY 0.1 to 1.0)
- requestAnimationFrame loop cập nhật ~60fps
- **Lý do**: Đơn giản, chính xác đủ cho MVP, zero dependency.

### 4. Webcam Integration

- Sử dụng `navigator.mediaDevices.getUserMedia({ video: true, audio: true })`
- Hiện tại app đã xin quyền mic. Sẽ thêm video constraint.
- Video stream render trực tiếp lên `<video>` element với `transform: scaleX(-1)` để mirror.
- Cần xử lý graceful fallback khi user từ chối quyền camera → hiển thị placeholder avatar thay vì webcam.

### 5. State Management

- Camera interview modal sẽ sử dụng state từ interview page hiện tại (chat history, config, TTS audio).
- Thêm state mới: `isCameraMode: boolean`, `webcamStream: MediaStream | null`, `audioAnalyser: AnalyserNode | null`.
- Khi đóng modal → cleanup: stop webcam stream, disconnect audio analyser.

## Risks / Trade-offs

- **[Browser Compatibility]** getUserMedia không support trên một số browser cũ → Mitigation: Check `navigator.mediaDevices` existence, hiển thị thông báo yêu cầu browser hiện đại.
- **[Camera Permission Denied]** User có thể từ chối quyền camera → Mitigation: Cho phép phỏng vấn camera với placeholder avatar (không bật cam), vẫn hoạt động bình thường.
- **[Mobile Performance]** Webcam + SVG animation + Audio analysis cùng lúc → Mitigation: Giảm animation frequency trên mobile (30fps thay vì 60fps), SVG đơn giản.
- **[Audio Routing]** Trên một số device mobile, TTS audio có thể bị capture lại bởi mic → Mitigation: Đây là vấn đề hiện tại đã có, không phải do camera mode gây ra.
