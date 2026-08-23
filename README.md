# 🎬 Auto_post — Tự động sản xuất & đăng Video Truyện Tranh lên YouTube

Hệ thống AI tự động hóa hoàn toàn quy trình: **Cào dữ liệu → Viết kịch bản mới → Vẽ ảnh → Lồng tiếng → Ghép video → Upload YouTube**. Chạy miễn phí 100% trên GitHub Actions, đăng video mỗi 3-6 tiếng.

## 📋 Tổng quan

```
┌────────────────────────────────────────────────────────────────────┐
│                   AUTO VIDEO PIPELINE                              │
│                                                                    │
│  🕷️ SCRAPE → 🤖 AI SCRIPT → 🎨 IMAGES → 🔊 TTS → 🎬 VIDEO → 📤 │
│                                                                    │
│  YouTube ──→  Gemini 2.0    Pollinations  edge-tts  moviepy  YouTube│
│  (nguồn)     (kịch bản)    (vẽ ảnh)     (giọng đọc) (ghép)  Studio│
│                                                                    │
│  📝 Knowledge Base (nhớ dài hạn, tránh lặp nội dung)             │
│  ⏰ GitHub Actions (tự động mỗi 3-6 tiếng, random delay)          │
│  💰 100% MIỄN PHÍ                                                 │
└────────────────────────────────────────────────────────────────────┘
```

## ✨ Tính năng

| Tính năng | Mô tả |
|-----------|--------|
| 🕷️ **YouTube Scraping** | Cào nội dung video từ kênh YouTube bằng Playwright stealth |
| 🛡️ **Anti-Detection** | Proxy rotation, fake user-agent, giả lập hành vi người thật |
| 🤖 **AI Kịch bản đa cảnh** | Gemini 2.0 Flash viết lại thành kịch bản nhiều phân cảnh (Scene) |
| 🎨 **AI Vẽ ảnh hàng loạt** | Pollinations.ai tạo ảnh cho từng cảnh, giữ phong cách nhất quán |
| 🔊 **Lồng tiếng AI** | edge-tts giọng nam miền Nam tự nhiên (`vi-VN-NamMinhNeural`) |
| 🎬 **Ghép video tự động** | moviepy + ffmpeg: Ken Burns effect + phụ đề tiếng Việt |
| 📐 **Tự chọn định dạng** | Dưới 60s → YouTube Shorts (9:16) · Trên 60s → Video thường (16:9) |
| 📤 **Upload YouTube** | Playwright tự động mở YouTube Studio, tải video, điền thông tin, đăng |
| 🧠 **Nhớ dài hạn** | Ghi lịch sử đăng bài, AI không lặp lại chủ đề cũ |
| ⏰ **Lịch 3-6 tiếng** | GitHub Actions cron + random delay, không cần bật máy |
| 🔒 **Bảo mật** | API key & cookies lưu trong GitHub Secrets |

## 🏗️ Cấu trúc dự án

```
Auto_post/
├── .github/workflows/
│   └── auto_post.yml              # GitHub Actions: cron + ffmpeg + random delay
├── config/
│   ├── sources.yaml               # Kênh YouTube nguồn cần cào
│   └── niches.yaml                # Cấu hình 3 niche: stories, humor, health
├── src/
│   ├── main.py                    # CLI entry point (scrape/generate/post/run)
│   ├── models/
│   │   └── pipeline_models.py     # Data models: Scene, StoryScript, VideoOutput
│   ├── scraper/
│   │   ├── base_scraper.py
│   │   └── youtube_scraper.py     # Cào video titles & descriptions
│   ├── ai_pipeline/
│   │   ├── content_rewriter.py    # Gemini → kịch bản đa cảnh (StoryScript)
│   │   ├── image_generator.py     # Pollinations.ai → ảnh từng cảnh
│   │   ├── audio_generator.py     # edge-tts → giọng đọc AI
│   │   └── video_maker.py         # moviepy → ghép video + phụ đề
│   ├── memory/
│   │   └── knowledge_base.py      # Đọc/ghi lịch sử nội dung
│   ├── poster/
│   │   └── youtube_poster.py      # Upload video lên YouTube Studio
│   └── utils/
│       ├── browser_manager.py     # Playwright stealth setup
│       ├── human_simulator.py     # Giả lập chuột/bàn phím như người thật
│       ├── logger.py              # Structured logging
│       └── proxy_manager.py       # Xoay vòng proxy
├── tests/                         # 117+ test cases (unit/integration/e2e)
├── knowledge_base.md              # File nhớ dài hạn
├── requirements.txt
├── .env.example
└── .gitignore
```

## 🚀 Hướng dẫn cài đặt

### Bước 1: Clone repository

```bash
git clone https://github.com/HungThichCodee/Auto_post.git
cd Auto_post
```

### Bước 2: Cài đặt dependencies

```bash
# Tạo virtual environment (khuyến nghị)
python -m venv venv
source venv/bin/activate    # Linux/Mac
# hoặc
.\venv\Scripts\activate     # Windows

# Cài đặt packages
pip install -r requirements.txt

# Cài đặt Playwright browsers
playwright install chromium

# Cài ffmpeg (bắt buộc cho video)
# Ubuntu/Debian:
sudo apt-get install -y ffmpeg fonts-noto-cjk
# Windows: tải từ https://ffmpeg.org/download.html
# Mac:
brew install ffmpeg
```

### Bước 3: Lấy API keys & Cookies

#### 🔑 Gemini API Key (miễn phí)
1. Truy cập [Google AI Studio](https://aistudio.google.com/)
2. Đăng nhập → **Get API Key** → **Create API Key**
3. Copy API key

#### 🍪 Lấy YouTube Cookies
1. Cài extension [Cookie Editor](https://cookie-editor.com/) trên Chrome/Firefox
2. Đăng nhập YouTube bằng tài khoản có kênh muốn đăng video
3. Mở Cookie Editor → **Export** → Copy toàn bộ JSON

### Bước 4: Cấu hình GitHub Secrets

Vào **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Giá trị | Bắt buộc |
|-------------|---------|----------|
| `GEMINI_API_KEY` | API key từ Google AI Studio | ✅ |
| `YT_COOKIES` | YouTube cookies (JSON string) | ✅ |
| `PROXY_LIST` | Danh sách proxy (comma-separated) | ⬜ Tùy chọn |

### Bước 5: Cấu hình kênh nguồn

Chỉnh sửa `config/sources.yaml`:

```yaml
youtube:
  sources:
    # Kênh YouTube muốn cào nội dung làm nguồn cảm hứng
    - url: "https://www.youtube.com/@AI-thegioitihon"
      niche: "stories"    # stories, humor, hoặc health
```

### Bước 6: Test local

```bash
# Test cào dữ liệu
python -m src.main scrape --platform youtube

# Test tạo kịch bản + ảnh + audio (không upload)
python -m src.main generate --niche stories

# Test toàn bộ pipeline (không đăng video thật)
python -m src.main run --dry-run

# Chạy thật (sẽ tạo video và đăng lên YouTube!)
python -m src.main run
```

### Bước 7: Kích hoạt GitHub Actions

1. Push code lên GitHub
2. Vào tab **Actions** → Enable workflows
3. Bấm **Run workflow** để test thủ công
4. Sau đó workflow sẽ tự chạy mỗi 3-6 tiếng

## 🎯 3 Niche nội dung

| Niche | Mô tả | Phong cách AI |
|-------|--------|---------------|
| 🏰 **stories** | Truyện dài tập, phiêu lưu kỳ thú | Kịch tính, hấp dẫn, có twist |
| 😂 **humor** | Giải trí hài hước, video vui | Dí dỏm, gần gũi, trendy |
| 🥬 **health** | Sức khỏe, rau củ, đời sống | Chuyên nghiệp, dễ hiểu |

## 📝 CLI Commands

```bash
# Cào nội dung từ YouTube
python -m src.main scrape --platform youtube

# Tạo kịch bản + ảnh + audio
python -m src.main generate --niche stories

# Upload video có sẵn
python -m src.main post --video output/video.mp4 --title "Tiêu đề" --description "Mô tả"

# Pipeline đầy đủ
python -m src.main run                # Scrape → AI → Video → Upload
python -m src.main run --dry-run      # Test không upload thật
```

## 🔄 Quy trình tự động (Pipeline)

```
1. ⏰ GitHub Actions kích hoạt (cron mỗi 3h + random delay 0-180 phút)
2. 🕷️ Playwright stealth cào nội dung từ kênh YouTube nguồn
3. 🤖 Gemini AI viết kịch bản mới (khác nội dung gốc) → chia thành nhiều Scene
4. 🎨 Pollinations.ai vẽ ảnh minh họa cho từng Scene
5. 🔊 edge-tts đọc lời thuyết minh bằng giọng nam miền Nam
6. 🎬 moviepy ghép ảnh + audio + phụ đề → xuất file .mp4
7. 📐 Tự chọn format: < 60s → Shorts (9:16) | ≥ 60s → Video (16:9)
8. 📤 Playwright mở YouTube Studio → upload video → đặt Public → Đăng
9. 📝 Ghi lại nội dung vào knowledge_base.md → commit lên GitHub
10. 🔁 Lặp lại sau 3-6 tiếng
```

## 🧠 Hệ thống nhớ (Knowledge Base)

File `knowledge_base.md` tự động ghi lại:
- 📅 Ngày đăng
- 🎬 Tiêu đề video
- 🏷️ Chủ đề & themes
- 📊 Số cảnh & thời lượng

AI đọc toàn bộ lịch sử trước khi tạo nội dung mới → đảm bảo:
- ✅ Không lặp lại chủ đề/ý tưởng cũ
- ✅ Mỗi video là một câu chuyện hoàn toàn mới
- ✅ Phong cách nhất quán theo niche đã chọn

## 🛠️ Công nghệ sử dụng (100% miễn phí)

| Công nghệ | Mục đích | Chi phí |
|------------|----------|---------|
| [Playwright](https://playwright.dev/) | Browser automation (scrape + upload) | Miễn phí |
| [Gemini 2.0 Flash](https://aistudio.google.com/) | Viết kịch bản AI | Miễn phí (free tier) |
| [Pollinations.ai](https://pollinations.ai/) | Tạo ảnh AI | Miễn phí |
| [edge-tts](https://github.com/rany2/edge-tts) | Giọng đọc AI tiếng Việt | Miễn phí |
| [moviepy](https://zulko.github.io/moviepy/) | Ghép video | Miễn phí |
| [GitHub Actions](https://github.com/features/actions) | Lịch chạy tự động | Miễn phí (public repo) |

## ⚠️ Lưu ý quan trọng

> **🔒 Bảo mật**: TUYỆT ĐỐI KHÔNG commit cookies, API keys vào code. Luôn dùng GitHub Secrets.

> **🍪 Cookie hết hạn**: Cookies YouTube có thời hạn (~30-90 ngày). Cần cập nhật lại khi hết hạn.

> **⚖️ Nội dung gốc**: Tool tạo nội dung MỚI được viết lại hoàn toàn bằng AI, không sao chép.

> **💰 Chi phí**: Hoàn toàn MIỄN PHÍ — tất cả API và dịch vụ đều dùng free tier.

## 🔧 Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| Cookie hết hạn | Lấy cookies mới, cập nhật GitHub Secrets |
| Scraping bị chặn | Thêm proxy vào `PROXY_LIST` secret |
| Gemini không phản hồi | Kiểm tra `GEMINI_API_KEY` còn hạn |
| Ảnh không tạo được | Pollinations.ai đôi khi chậm, có retry tự động |
| Video không render được | Kiểm tra ffmpeg đã cài chưa |
| Upload YouTube thất bại | Kiểm tra cookies và giao diện YouTube Studio (DOM hay đổi) |
| Subtitle không hiện | Cần cài ImageMagick (hoặc video sẽ không có phụ đề) |

## 📄 License

GNU General Public License v3.0 — xem file [LICENSE](LICENSE) để biết thêm chi tiết.