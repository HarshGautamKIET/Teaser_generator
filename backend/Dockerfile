# FFmpeg and FFprobe are hard runtime dependencies, not optional extras -- the
# media pipeline shells out to both -- so they are baked in rather than left to
# the host. This is the main reason the backend is containerised at all: it
# removes "install ffmpeg and put it on PATH" from every setup.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copied first so the dependency layer is cached independently of source edits.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app

# Storage roots are bind-mounted in compose; create them so an unmounted run
# still starts instead of failing on a missing directory.
RUN mkdir -p /data/uploads /data/generated

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
