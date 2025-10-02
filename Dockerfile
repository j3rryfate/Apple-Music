# Use a more stable and complete Python image for better package availability
FROM python:3.11-bookworm

# Set the working directory in the container
WORKDIR /app

# Define Bento4 version for easy updates
ENV BENTO4_VERSION 1.6.0-640
ENV BENTO4_URL https://www.bento4.com/downloads/Bento4-SDK-${BENTO4_VERSION}.x86_64-unknown-linux.zip

# Install system dependencies, including tools to download and extract Bento4
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gpac \
    rclone \
    zip \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Download, extract, and install Bento4 binaries (for mp4decrypt)
RUN wget -q ${BENTO4_URL} -O bento4.zip \
    && unzip bento4.zip \
    && cp Bento4-SDK-${BENTO4_VERSION}.x86_64-unknown-linux/bin/mp4decrypt /usr/local/bin/ \
    && cp Bento4-SDK-${BENTO4_VERSION}.x86_64-unknown-linux/bin/mp4info /usr/local/bin/ \
    && rm -rf bento4.zip Bento4-SDK-*

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Command to run the bot
CMD ["python", "bot.py"]
