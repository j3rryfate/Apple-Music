# Use an Ubuntu-based Python image for better package availability
FROM python:3.11-jammy

# Set the working directory
WORKDIR /app

# Set non-interactive frontend for apt-get to avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install prerequisites for adding PPAs, then add the PPA for bento4,
# and finally install all required tools from apt.
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:unifreq/ppa && \
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
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Command to run the bot
CMD ["python", "bot.py"]
