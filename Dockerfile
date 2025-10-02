# =================================================================
# Stage 1: Builder
# This stage compiles Bento4 from source and downloads GPAC
# =================================================================
FROM debian:bookworm as builder

WORKDIR /build

# Install build dependencies for Bento4, plus download tools
RUN apt-get update && apt-get install -y \
    g++ \
    cmake \
    python3-dev \
    curl \
    unzip \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Stable URLs for source code and binaries
ENV GPAC_URL https://download.gpac.io/latest/linux64/gpac.tar.gz
ENV BENTO4_SOURCE_URL https://github.com/axiomatic-systems/Bento4/archive/refs/tags/v1.6.0-641.zip

# Download, unzip, and COMPILE Bento4 from source
RUN curl -sSL ${BENTO4_SOURCE_URL} -o bento4_source.zip \
    && unzip bento4_source.zip \
    && cd Bento4-1.6.0-641 \
    && cmake -B build -S . \
    && cmake --build build --target mp4decrypt --config Release \
    && mv build/mp4decrypt /build/mp4decrypt

# Download and extract GPAC binary
RUN curl -sSL ${GPAC_URL} -o gpac.tar.gz \
    && tar -xzf gpac.tar.gz \
    && mv ./bin/gcc/MP4Box /build/MP4Box


# =================================================================
# Stage 2: Final application image
# =================================================================
FROM python:3.11-bookworm

WORKDIR /app

# Install only the necessary RUNTIME system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    rclone \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled/downloaded binaries from the builder stage
COPY --from=builder /build/mp4decrypt /usr/local/bin/
COPY --from=builder /build/MP4Box /usr/local/bin/

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Run the bot
CMD ["python", "bot.py"]
