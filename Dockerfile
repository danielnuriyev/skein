FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y curl bash git bzip2 libgomp1 && rm -rf /var/lib/apt/lists/*

# Install goose-cli
RUN curl -fsSL "https://github.com/block/goose/releases/download/stable/download_cli.sh" | CONFIGURE=false bash
# The download script usually puts goose in /usr/local/bin or similar, let's make sure it's in PATH
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Install python dependencies
# Reading from pyproject.toml / setup.sh equivalent
RUN pip install --no-cache-dir bottle requests boto3

# Copy source code and config
COPY src/ /app/src/
COPY config/ /app/config/
COPY prompts/ /app/prompts/

ENV PYTHONPATH=/app

# Create logs directory
RUN mkdir -p /app/.logs && chmod 777 /app/.logs
