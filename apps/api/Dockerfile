FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.11-slim

# Copy AWS Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set working directory
WORKDIR /app

# Install system dependencies if needed (e.g. for audio/video processing)
# ffmpeg might be needed for audio/video processing if done locally, strictly speaking we are moving to cloud gen
# but some libs might need it. kureita seems to rely on API generation now.
# But let's verify if we need `ffmpeg` for `pydub` or similar if used.
# The user dependencies list: "elevenlabs", "gtts", "boto3", "pillow", "aiofiles".
# "playwright" is there... Playwright in lambda is tricky.
# `requires-python = ">=3.11"`
# If playwright is a dependency, we might need a special base image or install browsers.
# Let's check if playwright is ACTUALLY used or just optional.
# It is in dependencies.
# If we need playwright, we should probably use a container that supports it or just install it and browsers.
# Installing browsers in lambda container makes it huge.
# Maybe we can skip playwright for now if it is only for scraping?
# The `WebScraper` service uses it.
# So we DO need it.
# Running playwright in Lambda usually requires a specific build.

# For now, let's stick to the plan but I might need to add playwright install steps.
# AWS Lambda Adapter works with any http app.
# Let's add playwright install.

RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*
    
# Download and install static ffmpeg for arm64 (aarch64) to avoid Lambda "exec format error"
RUN curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz > ffmpeg.tar.xz \
    && tar -xvf ffmpeg.tar.xz \
    && rm ffmpeg.tar.xz \
    && mv ffmpeg-*-static/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-*-static/ffprobe /usr/local/bin/ \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-*-static

# Copy project files
COPY pyproject.toml .
COPY main.py .
COPY app app
COPY static static

# Install python dependencies
RUN pip install --no-cache-dir .

# Install playwright browsers (chromium only to save space)
# RUN playwright install chromium --with-deps
# note: This might bloat the image. Lambda has 10GB limit now so maybe ok.
# But `playwright install --with-deps` installs system deps too.
# Let's try basic install first.

ENV PORT=8080
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
