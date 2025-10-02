# Use a stable Python image
FROM python:3.11-bookworm

# Set the working directory
WORKDIR /app

# Environment variables for tool versions and URLs
ENV BENTO4_VERSION 1.6.0-642
ENV BENTO4_URL https://github.com/axiomatic-systems/Bento4/releases/download/v${BENTO4_VERSION}/Bento4-SDK-${BENTO4_VERSION}-x86_64-unknown-linux.zip
ENV GPAC_URL https://download.gpac.io/latest/linux64/gpac.tar.gz

# Install base dependencies (Replaced wget with curl)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    rclone \
    zip \
    curl \
    unzip \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Download, extract, and install Bento4 (using curl)
RUN curl -sSL ${BENTO4_URL} -o bento4.zip \
    && unzip bento4.zip \
    && cp Bento4-SDK-${BENTO4_VERSION}-x86_64-unknown-linux/bin/mp4decrypt /usr/local/bin/ \
    && cp Bento4-SDK-${BENTO4_VERSION}-x86_64-unknown-linux/bin/mp4info /usr/local/bin/ \
    && rm -rf bento4.zip Bento4-SDK-*

# Download, extract, and install GPAC (using curl)
RUN curl -sSL ${GPAC_URL} -o gpac.tar.gz \
    && tar -xzf gpac.tar.gz \
    && cp ./bin/gcc/MP4Box /usr/local/bin/ \
    && rm -rf gpac.tar.gz ./bin ./include ./lib ./share

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Command to run the bot
CMD ["python", "bot.py"]
