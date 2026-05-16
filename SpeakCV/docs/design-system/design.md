# SpeakCV Design System (Minimalist & Professional)

## 1) Design Direction
- **Style**: Minimal, clean, professional (Korean - Vietnamese fusion).
- **Theme**: White background with a strong, trustworthy accent color.
- **Tone**: Calm, clear, interview-focused, low visual noise.
- **Keywords**: whitespace, clarity, trust, readability.

## 2) Color Tokens

### Core & Brand
- `--color-primary: #2563EB` (Blue 600 - Màu nhấn chính/Nút bấm)
- `--color-primary-hover: #1D4ED8` (Blue 700)
- `--color-background: #F8FAFC` (Slate 50 - Nền ngoài)
- `--color-surface: #FFFFFF` (Nền thẻ/Card, nền chính)
- `--color-border: #E2E8F0` (Slate 200)

### Text
- `--color-text-primary: #0F172A` (Slate 900)
- `--color-text-secondary: #475569` (Slate 600)
- `--color-text-muted: #94A3B8` (Slate 400)

### Semantic
- `--color-success: #16A34A`
- `--color-warning: #D97706`
- `--color-danger: #DC2626`
- `--color-info: #3B82F6`

### Interactive
- `--color-focus-ring: rgba(37, 99, 235, 0.5)`
- `--color-overlay: rgba(15, 23, 42, 0.45)`

### Disabled
- `--color-surface-disabled: #E2E8F0` (Slate 200)
- `--color-text-disabled: #94A3B8` (Slate 400)

## 3) Accessibility Rules
- Body text contrast >= 4.5:1 on white surfaces.
- Touch target min 44x44px.
- Focus ring visible on all keyboard-focusable elements.

## 4) Typography (Tối ưu Đa ngôn ngữ Hàn - Việt)
- **Primary Font**: `Pretendard`, `Noto Sans KR`, `Inter`, `sans-serif` (Pretendard hiển thị tiếng Hàn và Việt rất thanh lịch).
- **CSS Font Declaration**: `font-family: 'Pretendard', 'Noto Sans KR', 'Inter', sans-serif;`
- Base size: `16px`
- Body line-height: `1.6` (Tiếng Hàn cần line-height lớn hơn tiếng Anh một chút).
- Scale: `12 / 14 / 16 / 18 / 24 / 32`
- Weights: `400 (Regular) / 500 (Medium) / 600 (Semi-bold)`

## 5) Spacing & Radius
- Spacing scale: `4, 8, 12, 16, 24, 32, 40, 48, 64`
- Component radius:
  - Inputs/Buttons: `8px` hoặc `12px` (Hàn Quốc chuộng bo tròn nhẹ).
  - Cards: `16px`
  - Modals: `20px`

## 6) Elevation & Shadow
- `--shadow-sm: 0 1px 2px rgba(15,23,42,0.05)`
- `--shadow-md: 0 4px 12px rgba(15,23,42,0.08)`
- `--shadow-lg: 0 12px 32px rgba(15,23,42,0.10)`

## 7) Component Guidance

### Buttons
- **Primary**: Nền `--color-primary`, chữ Trắng. Chuyên dùng cho "Tạo CV", "Bắt đầu phỏng vấn".
- **Secondary**: Nền trắng, viền `--color-border`, chữ `--color-text-primary`.
- **Ghost/Tertiary**: Không nền, chữ xám, hover lên nền xám nhạt (`Slate 100`).

### Inputs
- Nền trắng + viền Slate 200. Focus: Viền xanh Primary + Blue Focus Ring.

### Cards & Modals
- Nền trắng tuyệt đối (`#FFFFFF`), shadow rất nhẹ để tạo cảm giác "nổi" tinh tế (Airy design).

## 8) Interview Screen Specific Notes
- Vùng câu hỏi/trả lời: Max contrast, không dùng màu gây xao nhãng.
- Thanh đếm giờ (Timer): Dùng Neutral color, chỉ chuyển cam/đỏ (Warning/Danger) khi còn dưới 20%.
