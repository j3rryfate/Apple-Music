# =================================================================
# Stage 1: Builder
# This stage compiles both Bento4 and GPAC from their source code.
# This makes the build independent of unreliable external binaries and PPAs.
# =================================================================
FROM ubuntu:22.04 as builder

WORKDIR /build

# Install all build dependencies needed for both projects
# This includes g++, cmake, python, git, and specific libraries for GPAC
RUN apt-get update && apt-get install -y \
    g++ \
    cmake \
    python3-dev \
    curl \
    unzip \
    tar \
    git \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# === Compile Bento4 from Source ===
ENV BENTO4_SOURCE_URL https://github.com/axiomatic-systems/Bento4/archive/refs/tags/v1.6.0-641.zip
RUN curl -sSL ${BENTO4_SOURCE_URL} -o bento4_source.zip \
    && unzip bento4_source.zip \
    && cd Bento4-1.6.0-641 \
    && cmake -B build -S . \
    && cmake --build build --target mp4decrypt --config Release \
    && mv build/mp4decrypt /build/mp4decrypt

# === Compile GPAC from Source ===
# We clone the git repo to get a specific stable version
RUN git clone --branch v2.2.1 --depth 1 https://github.com/gpac/gpac.git \
    && cd gpac \
    && ./configure --static-mp4box \
    && make \
    && mv bin/gcc/MP4Box /build/MP4Box


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

# Copy the compiled binaries from the builder stage
COPY --from=builder /build/mp4decrypt /usr/local/bin/
COPY --from=builder /build/MP4Box /usr/local/bin/

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Run the bot
CMD ["python3", "bot.py"]
