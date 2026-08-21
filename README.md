# 🚀 Auto_post — Automated Social Media Content Pipeline

Hệ thống tự động hóa hoàn toàn quy trình tạo và đăng nội dung lên mạng xã hội, chạy miễn phí trên GitHub Actions.

## 📋 Tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTO_POST PIPELINE                           │
│                                                                 │
│  📥 SCRAPE  →  🤖 AI REWRITE  →  🎨 GEN IMAGE  →  📤 POST    │
│                                                                 │
│  Facebook ─┐    Gemini AI       Pollinations.ai    Facebook     │
│  TikTok  ──┤    (Free API)      (Free API)         TikTok      │
│  YouTube ──┘                                       YouTube      │
│                                                                 │
│  📝 Knowledge Base (Long-term Memory)                          │
│  ⏰ GitHub Actions (Auto-schedule every 4-6 hours)             │
└─────────────────────────────────────────────────────────────────┘
```

## ✨ Tính năng

| Tính năng | Mô tả |
|-----------|--------|
| 🕷️ **Multi-Platform Scraping** | Thu thập nội dung từ Facebook, TikTok, YouTube bằng Playwright |
| 🛡️ **Anti-Detection** | Proxy rotation, fake user-agent, human-like behavior |
| 🤖 **AI Content Rewriting** | Viết lại hoàn toàn bằng Gemini AI, giữ chủ đề, đổi góc nhìn |
| 🎨 **AI Image Generation** | Tạo ảnh minh họa bằng Pollinations.ai (miễn phí) |
| 🧠 **Long-term Memory** | Ghi nhớ lịch sử đăng bài, không lặp lại ý tưởng |
| 📤 **Auto-Posting** | Đăng tự động lên 3 nền tảng bằng Playwright |
| ⏰ **GitHub Actions** | Chạy tự động mỗi 4-6 tiếng, hoàn toàn miễn phí |
| 🔒 **Bảo mật** | Tất cả secrets lưu trong GitHub Secrets |

## 🏗️ Cấu trúc dự án

```
Auto_post/
├── .github/workflows/
│   └── auto_post.yml          # GitHub Actions cron workflow
├── config/
│   ├── sources.yaml           # Danh sách URL nguồn scrape
│   └── niches.yaml            # Cấu hình 3 niche nội dung
├── src/
│   ├── main.py                # CLI entry point
│   ├── scraper/               # Module thu thập dữ liệu
│   │   ├── base_scraper.py
│   │   ├── facebook_scraper.py
│   │   ├── tiktok_scraper.py
│   │   └── youtube_scraper.py
│   ├── ai_pipeline/           # Module AI sáng tạo nội dung
│   │   ├── content_rewriter.py
│   │   └── image_generator.py
│   ├── memory/                # Module lưu trữ ngữ cảnh
│   │   └── knowledge_base.py
│   ├── poster/                # Module đăng bài tự động
│   │   ├── base_poster.py
│   │   ├── facebook_poster.py
│   │   ├── tiktok_poster.py
│   │   └── youtube_poster.py
│   └── utils/                 # Tiện ích
│       ├── browser_manager.py
│       ├── human_simulator.py
│       ├── logger.py
│       └── proxy_manager.py
├── knowledge_base.md          # File nhớ dài hạn
├── output/                    # Ảnh AI tạm (gitignored)
├── requirements.txt
├── .env.example               # Hướng dẫn cấu hình secrets
└── .gitignore
```

## 🚀 Hướng dẫn cài đặt

### Bước 1: Clone repository

```bash
git clone https://github.com/YOUR_USERNAME/Auto_post.git
cd Auto_post
```

### Bước 2: Cài đặt dependencies

```bash
# Tạo virtual environment (khuyến nghị)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
.\venv\Scripts\activate  # Windows

# Cài đặt packages
pip install -r requirements.txt

# Cài đặt Playwright browsers
playwright install chromium
```

### Bước 3: Lấy API keys & Cookies

#### 🔑 Gemini API Key (miễn phí)
1. Truy cập [Google AI Studio](https://aistudio.google.com/)
2. Đăng nhập bằng tài khoản Google
3. Vào **Get API Key** → **Create API Key**
4. Copy API key

#### 🍪 Lấy Cookies từ trình duyệt

**Cách 1: Dùng extension (khuyến nghị)**
1. Cài extension [Cookie Editor](https://cookie-editor.com/) trên Chrome/Firefox
2. Đăng nhập vào Facebook/TikTok/YouTube
3. Mở Cookie Editor → **Export** → **JSON**
4. Copy toàn bộ JSON string

**Cách 2: Dùng DevTools**
1. Đăng nhập vào trang web
2. Mở DevTools (F12) → tab Application → Cookies
3. Copy tất cả cookies thành JSON format

### Bước 4: Cấu hình GitHub Secrets

Vào **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Giá trị | Bắt buộc |
|-------------|---------|----------|
| `GEMINI_API_KEY` | API key từ Google AI Studio | ✅ |
| `FB_COOKIES` | Facebook cookies (JSON string) | ✅ |
| `TIKTOK_COOKIES` | TikTok cookies (JSON string) | ✅ |
| `YT_COOKIES` | YouTube cookies (JSON string) | ✅ |
| `FB_PAGE_URL` | URL fanpage Facebook của bạn | ✅ |
| `TIKTOK_UPLOAD_URL` | URL trang upload TikTok | ⬜ |
| `YT_CHANNEL_URL` | URL kênh YouTube của bạn | ⬜ |
| `PROXY_LIST` | Danh sách proxy (comma-separated) | ⬜ |

### Bước 5: Cấu hình nguồn scrape

Chỉnh sửa `config/sources.yaml` để thêm các trang/kênh muốn scrape:

```yaml
facebook:
  sources:
    - url: "https://www.facebook.com/your.target.page"
      niche: "humor"    # humor, stories, hoặc health
    - url: "https://www.facebook.com/another.page"
      niche: "health"

tiktok:
  sources:
    - url: "https://www.tiktok.com/@target_account"
      niche: "stories"

youtube:
  sources:
    - url: "https://www.youtube.com/@target_channel"
      niche: "health"
```

### Bước 6: Test local

```bash
# Test scraping (không lưu kết quả)
python -m src.main scrape --platform facebook --dry-run

# Test tạo nội dung AI (không tạo ảnh)
python -m src.main generate --niche humor --dry-run

# Test toàn bộ pipeline (không đăng bài)
python -m src.main run --dry-run

# Chạy thật (sẽ đăng bài!)
python -m src.main run
```

### Bước 7: Kích hoạt GitHub Actions

1. Push code lên GitHub
2. Vào tab **Actions** → Enable workflows
3. Workflow sẽ tự chạy mỗi 4-6 tiếng
4. Hoặc bấm **Run workflow** để chạy thủ công

## 🎯 3 Niche nội dung

| Niche | Mô tả | Phong cách ảnh |
|-------|--------|----------------|
| 🏰 **stories** | Truyện dài tập có minh họa | Digital art, fantasy, cinematic |
| 😂 **humor** | Giải trí hài hước | Cartoon, vibrant colors, funny |
| 🥬 **health** | Sức khỏe rau củ | Photorealistic, fresh vegetables |

## 📝 CLI Commands

```bash
# Scrape nội dung
python -m src.main scrape --platform facebook --max-posts 10

# Tạo nội dung AI
python -m src.main generate --niche stories --platform tiktok

# Đăng bài
python -m src.main post --platform facebook --content "Nội dung..." --image output/image.png

# Pipeline đầy đủ
python -m src.main run                          # Tất cả platform
python -m src.main run --platforms facebook      # Chỉ Facebook
python -m src.main run --dry-run                 # Test không đăng
```

## 🧠 Hệ thống nhớ (Knowledge Base)

File `knowledge_base.md` tự động ghi lại:
- 📅 Ngày đăng
- 📱 Platform
- 🏷️ Niche/chủ đề
- 📝 Tóm tắt nội dung
- 🔑 Các theme đã dùng

AI sẽ đọc toàn bộ lịch sử này trước khi tạo nội dung mới, đảm bảo:
- ✅ Không lặp lại ý tưởng cũ
- ✅ Duy trì văn phong nhất quán
- ✅ Phát triển nội dung theo chiến lược

## ⚠️ Lưu ý quan trọng

> **🔒 Bảo mật**: TUYỆT ĐỐI KHÔNG commit cookies, API keys, hoặc bất kỳ dữ liệu nhạy cảm nào vào code. Luôn dùng GitHub Secrets.

> **🍪 Cookie hết hạn**: Cookies mạng xã hội có thời hạn (thường 30-90 ngày). Cần cập nhật lại cookies trong GitHub Secrets khi hết hạn.

> **⚖️ Pháp lý**: Tool này tạo nội dung GỐC được viết lại bằng AI, không sao chép. Tuy nhiên, hãy đảm bảo nội dung tuân thủ tiêu chuẩn cộng đồng của từng nền tảng.

> **💰 Chi phí**: Hoàn toàn MIỄN PHÍ — sử dụng Gemini Free API, Pollinations.ai free, và GitHub Actions free tier.

## 📊 Giám sát

- **GitHub Actions logs**: Tab Actions → chọn run → xem logs chi tiết
- **Pipeline logs**: Tải artifact `pipeline-logs` từ mỗi run
- **Knowledge base**: Kiểm tra `knowledge_base.md` để xem lịch sử đăng bài

## 🔧 Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| Cookie hết hạn | Lấy cookies mới và cập nhật GitHub Secrets |
| Scraping bị block | Thêm proxy vào `PROXY_LIST` secret |
| AI không tạo nội dung | Kiểm tra `GEMINI_API_KEY` còn hạn dùng |
| Ảnh không tạo được | Pollinations.ai có thể chậm, retry tự động |
| Đăng bài thất bại | Kiểm tra cookies và selectors (DOM có thể thay đổi) |

## 📄 License

GNU General Public License v3.0 — xem file [LICENSE](LICENSE) để biết thêm chi tiết.