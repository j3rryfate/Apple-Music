# ============================================
# FILE: setup.sh
# ============================================
#!/bin/bash

echo "🚀 Setting up Apple Music Telegram Bot..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg not found. Please install FFmpeg first."
    exit 1
fi
echo "✓ FFmpeg installed"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p downloads temp

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration"
else
    echo "✓ .env file already exists"
fi

# Check for cookies file
if [ ! -f cookies.txt ]; then
    echo "⚠️  cookies.txt not found. Please add your Apple Music cookies."
else
    echo "✓ cookies.txt found"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your bot token and admin IDs"
echo "2. Add cookies.txt file with Apple Music cookies"
echo "3. Run: ./run.sh"


# ============================================
# FILE: run.sh
# ============================================
#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Run ./setup.sh first."
    exit 1
fi

# Check if cookies.txt exists
if [ ! -f cookies.txt ]; then
    echo "❌ cookies.txt not found. Please add your Apple Music cookies."
    exit 1
fi

echo "🤖 Starting Apple Music Telegram Bot..."
python -m bot.main


# ============================================
# FILE: run_docker.sh
# ============================================
#!/bin/bash

echo "🐳 Starting bot with Docker..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found."
    exit 1
fi

# Check if cookies.txt exists
if [ ! -f cookies.txt ]; then
    echo "❌ cookies.txt not found."
    exit 1
fi

# Build and start
docker-compose up --build -d

echo "✅ Bot started in background"
echo "View logs: docker-compose logs -f"
echo "Stop bot: docker-compose down"


# ============================================
# FILE: SETUP_GUIDE.md
# ============================================
# Complete Setup Guide

## Prerequisites

1. **Python 3.8+**
   ```bash
   python3 --version
