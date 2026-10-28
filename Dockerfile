
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg curl unzip ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV DENO_INSTALL=/opt/deno

RUN curl -fsSL https://deno.land/install.sh | sh

ENV PATH="/opt/deno/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY video_processor.py .
COPY templates ./templates
COPY static ./static

EXPOSE 8080

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 240 app:app"]
