## Why

SpeakCV hiện chỉ hỗ trợ phỏng vấn dạng text/audio — người dùng nói qua mic, AI trả lời qua TTS, tương tác qua chatbox. Trải nghiệm này thiếu yếu tố "face-to-face" — một phần quan trọng của phỏng vấn thực tế. Tính năng "Phỏng vấn Camera" sẽ mô phỏng cuộc phỏng vấn video call, giúp người dùng luyện tập với cảm giác chân thực hơn: thấy mình trên camera, đối diện với avatar AI HR biết nhép miệng theo audio.

## What Changes

- **Thêm chế độ "Phỏng vấn Camera"** vào menu Công cụ trên Sidebar — mở ra giao diện video call full-screen overlay
- **Webcam integration**: Hiển thị camera người dùng real-time (không ghi hình)
- **AI HR Avatar**: Nhân vật hoạt hình HR phong thái chuyên nghiệp, lip-sync theo TTS audio bằng Web Audio API AnalyserNode
- **Responsive layout**: Desktop hiển thị side-by-side (user | AI), Mobile hiển thị kiểu Zalo video call (AI full + user PiP góc)
- **Reuse toàn bộ backend**: Flow phỏng vấn (transcribe → chat → TTS) giữ nguyên, chỉ thêm lớp UI mới phía frontend
- **MVP approach**: Avatar dạng SVG illustration với CSS animation (lip-sync, blink, breathing), không dùng 3D engine

## Capabilities

### New Capabilities
- `camera-interview-ui`: Giao diện phỏng vấn camera full-screen overlay với webcam user + AI avatar, layout responsive desktop/mobile
- `ai-hr-avatar`: SVG avatar HR hoạt hình với lip-sync animation dựa trên audio amplitude, idle animations (blink, breathing)

### Modified Capabilities
_(Không có capability hiện tại nào bị thay đổi requirements. Backend APIs giữ nguyên.)_

## Impact

- **Frontend**: Thêm 3 component mới (`CameraInterviewModal`, `AvatarHR`, `WebcamView`), thêm 1 nút vào Sidebar tools menu
- **Backend**: Không thay đổi — reuse `/api/transcribe`, `/api/chat`, `/api/end-interview`
- **Dependencies**: Không cần thêm package mới (dùng native Web APIs: getUserMedia, AudioContext, AnalyserNode)
- **Browser permissions**: Cần xin thêm quyền camera (hiện chỉ xin mic)
- **Performance**: SVG + CSS animation nhẹ, không ảnh hưởng hiệu năng
