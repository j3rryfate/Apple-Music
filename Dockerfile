# =================================================================
# Stage 1: Builder for downloading and extracting external binaries
# =================================================================
FROM debian:bookworm-slim as builder

WORKDIR /build

# Environment variables for tool URLs
ENV BENTO4_VERSION 1.6.0-641
ENV BENTO4_URL https://www.bento4.com/downloads/Bento4-SDK-${BENTO4_VERSION}-x86_64-linux.zip
ENV GPAC_URL https://download.gpac.io/latest/linux64/gpac.tar.gz

# Install only the necessary tools for downloading and extracting
RUN apt-get update && apt-get install -y curl unzip tar && rm -rf /var/lib/apt/lists/*

# Download and extract Bento4, placing the required binaries in the workdir
RUN curl -sSL ${BENTO4_URL} -o bento4.zip \
    && (unzip bento4.zip || { echo "Failed to unzip bento4.zip"; exit 1; }) \
    && mv Bento4-SDK-${BENTO4_VERSION}-x86_64-linux/bin/mp4decrypt . \
    && mv Bento4-SDK-${BENTO4_VERSION}-x86_64-linux/bin/mp4info .

# Download and extract GPAC, placing the required binary in the workdir
RUN curl -sSL ${GPAC_URL} -o gpac.tar.gz \
    && tar -xzf gpac.tar.gz \
    && mv ./bin/gcc/MP4Box .

# =================================================================
# Stage 2: Final application image
# =================================================================
FROM python:3.11-bookworm

WORKDIR /app

# Install main application system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    rclone \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built binaries from the builder stage into the final image's PATH
COPY --from=builder /build/mp4decrypt /usr/local/bin/
COPY --from=builder /build/mp4info /usr/local/bin/
COPY --from=builder /build/MP4Box /usr/local/bin/

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Command to run the bot
CMD ["python", "bot.py"]
