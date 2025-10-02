# Use the official Ubuntu 22.04 (Jammy) LTS as the base image
FROM ubuntu:22.04

# Set the working directory
WORKDIR /app

# Set non-interactive frontend for apt-get to avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.11, pip, and prerequisites for adding PPAs
RUN apt-get update && \
    apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-dev \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default python3 and pip3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    pip3 install --no-cache-dir --upgrade pip

# Add the PPA for bento4 and install all required application tools
RUN add-apt-repository ppa:unifreq/ppa && \
    apt-get update && \
    apt-get install -y \
    ffmpeg \
    gpac \
    bento4 \
    rclone \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Command to run the bot using the installed python3
CMD ["python3", "bot.py"]
