# Use a small official Python runtime as the base image.
FROM python:3.10-slim

# Keep Python output unbuffered so progress logs are visible in Docker.
ENV PYTHONUNBUFFERED=1 \
    SUBSYNC_TEMP_DIR=/tmp/subsync_temp \
    FFSUBSYNC_BINARY=ffs

# Install ffmpeg, which subtitle synchronization tools use to read audio streams.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Run the app from a dedicated working directory.
WORKDIR /app

# Install Python dependencies separately for better Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the synchronization scripts into the container.
COPY sub.py sub_sync_recursive.py download_jellyfin_subtitles.py auto_subs.sh ./

# Store user media outside the image; docker-compose mounts ./media here.
WORKDIR /media

# Default to recursive batch synchronization. Override the command for one-off syncs.
ENTRYPOINT ["python", "/app/sub_sync_recursive.py"]
