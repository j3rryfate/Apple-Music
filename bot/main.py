# ============================================
# FILE: bot/main.py
# ============================================
import logging
import re
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.config import BOT_TOKEN
from bot.database.models import init_db
from bot.handlers.start import start_command, help_command, stats_command
from bot.handlers.admin import (
    approve_command, reject_command, ban_command, unban_command,
    users_command, systemstats_command
)
from bot.handlers.download import handle_url, button_callback

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Apple Music URL pattern
APPLE_MUSIC_URL_PATTERN = re.compile(
    r'https?://music\.apple\.com/[a-z]{2}/(album|playlist|song|music-video|artist|post)/'
)

def main():
    """Start the bot"""
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Admin commands
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("reject", reject_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("systemstats", systemstats_command))
    
    # URL handler
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(APPLE_MUSIC_URL_PATTERN) & ~filters.COMMAND,
        handle_url
    ))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    logger.info("Bot started")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()


# ============================================
# FILE: requirements.txt
# ============================================
python-telegram-bot==20.7
sqlalchemy==2.0.23
click
inquirerpy
m3u8
pillow
pywidevine
pyyaml
yt-dlp
requests


# ============================================
# FILE: .env.example
# ============================================
# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321
DUMP_CHANNEL_ID=-1001234567890

# Apple Music Configuration
COOKIES_PATH=./cookies.txt

# Paths
OUTPUT_PATH=./downloads
TEMP_PATH=./temp

# Database
DATABASE_URL=sqlite:///bot.db

# Download Settings
MAX_FILE_SIZE_MB=2000
CONCURRENT_DOWNLOADS=3


# ============================================
# FILE: .gitignore
# ============================================
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Bot specific
.env
cookies.txt
*.db
downloads/
temp/
Apple Music/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db


# ============================================
# FILE: Dockerfile
# ============================================
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p downloads temp

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run bot
CMD ["python", "-m", "bot.main"]


# ============================================
# FILE: docker-compose.yml
# ============================================
version: '3.8'

services:
  bot:
    build: .
    container_name: gamdl-telegram-bot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./cookies.txt:/app/cookies.txt:ro
      - ./downloads:/app/downloads
      - ./temp:/app/temp
      - ./bot.db:/app/bot.db
    environment:
      - DATABASE_URL=sqlite:///bot.db
      - OUTPUT_PATH=/app/downloads
      - TEMP_PATH=/app/temp
      - COOKIES_PATH=/app/cookies.txt


# ============================================
# FILE: README.md
# ============================================
# Apple Music Downloader Telegram Bot

Telegram bot for downloading Apple Music songs, albums, and playlists with membership system.

## Features

✅ **Download Options:**
- Track by track download
- ZIP archive download
- Support for songs, albums, playlists, and music videos

✅ **Membership System:**
- Admin approval required
- User management (approve/reject/ban)
- Download history tracking

✅ **Dump Channel:**
- Automatic backup to channel
- Forward to users

✅ **Admin Commands:**
- `/approve <user_id>` - Approve user
- `/reject <user_id>` - Reject user
- `/ban <user_id>` - Ban user
- `/unban <user_id>` - Unban user
- `/users` - List all users
- `/systemstats` - System statistics

## Setup

### 1. Prerequisites

- Python 3.8+
- FFmpeg
- Apple Music cookies (Netscape format)
- Telegram Bot Token
- Dump Channel ID

### 2. Installation

```bash
# Clone repository
git clone <your-repo>
cd gamdl-telegram-bot

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

### 3. Configuration

Edit `.env` file:

```env
BOT_TOKEN=your_bot_token_from_@BotFather
ADMIN_IDS=your_telegram_id,another_admin_id
DUMP_CHANNEL_ID=-1001234567890
COOKIES_PATH=./cookies.txt
```

### 4. Get Apple Music Cookies

1. Login to music.apple.com
2. Use browser extension to export cookies:
   - Firefox: [Export Cookies](https://addons.mozilla.org/addon/export-cookies-txt)
   - Chrome: [Get cookies.txt](https://chrome.google.com/webstore/detail/gdocmgbfkjnnpapoeobnolbbkoibbcif)
3. Save as `cookies.txt`

### 5. Create Dump Channel

1. Create a private channel
2. Add bot as admin
3. Get channel ID (use @username_to_id_bot)
4. Add ID to `.env` (with `-100` prefix)

### 6. Run Bot

```bash
python -m bot.main
```

## Docker Deployment

### Build and Run

```bash
# Build image
docker-compose build

# Start bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop bot
docker-compose down
```

### Deploy to Railway/Zeabur

1. **Railway:**
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Deploy
railway up
```

2. **Zeabur:**
```bash
# Connect GitHub repo
# Add environment variables in dashboard
# Deploy automatically
```

## Usage

### For Users:

1. Start bot: `/start`
2. Wait for admin approval
3. Send Apple Music URL
4. Choose download format
5. Wait for upload

### For Admins:

```
/users - View pending users
/approve 123456789 - Approve user
/reject 123456789 - Reject user
/ban 123456789 - Ban user
/systemstats - View statistics
```

## Project Structure

```
gamdl-telegram-bot/
├── bot/
│   ├── __init__.py
│   ├── config.py              # Configuration
│   ├── main.py                # Main bot file
│   ├── database/
│   │   ├── models.py          # Database models
│   │   └── db.py              # Database operations
│   ├── handlers/
│   │   ├── start.py           # Start/help commands
│   │   ├── admin.py           # Admin commands
│   │   └── download.py        # Download handler
│   └── utils/
│       ├── downloader.py      # GAMDL wrapper
│       ├── zip_helper.py      # ZIP creation
│       └── uploader.py        # Telegram upload
├── gamdl/                     # Original GAMDL code
├── .env                       # Environment variables
├── cookies.txt                # Apple Music cookies
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram bot token | `123456:ABC-DEF...` |
| `ADMIN_IDS` | Comma-separated admin IDs | `123456789,987654321` |
| `DUMP_CHANNEL_ID` | Backup channel ID | `-1001234567890` |
| `COOKIES_PATH` | Apple Music cookies path | `./cookies.txt` |
| `DATABASE_URL` | Database connection | `sqlite:///bot.db` |
| `MAX_FILE_SIZE_MB` | Max upload size | `2000` |

## Troubleshooting

**Bot not responding:**
- Check bot token
- Verify bot is running
- Check logs

**Download fails:**
- Verify cookies are valid
- Check Apple Music subscription
- Ensure FFmpeg is installed

**Upload fails:**
- Check file size limits
- Verify dump channel permissions
- Check bot is admin in channel

## License

MIT License

## Credits

- Based on [GAMDL](https://github.com/glomatico/gamdl)
- Python Telegram Bot library
