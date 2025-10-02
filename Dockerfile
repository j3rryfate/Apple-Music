# Use the official Ubuntu 22.04 (Jammy) LTS as the base image
FROM ubuntu:22.04

# Set the working directory
WORKDIR /app

# Set non-interactive frontend for apt-get to avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

# === Step 1: Install ALL system-level dependencies FIRST ===
# This uses the system's default Python (3.10) and its libraries, preventing any conflicts.
RUN apt-get update && \
    apt-get install -y \
    software-properties-common \
    python3-apt \
    && \
    add-apt-repository -y ppa:unifreq/ppa && \
    apt-get update && \
    apt-get install -y \
    ffmpeg \
    gpac \
    bento4 \
    rclone \
    zip

# === Step 2: Now, install Python 3.11 specifically for our application ===
RUN apt-get install -y \
    python3.11 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# === Step 3: Install Python packages using the specific pip for Python 3.11 ===
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

# === Step 4: Copy application code and set the final command ===
COPY . .

# Explicitly use python3.11 to run the bot, leaving the system's python3 untouched.
CMD ["python3.11", "bot.py"]
