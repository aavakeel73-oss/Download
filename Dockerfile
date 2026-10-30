FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DENO_INSTALL=/opt/deno PATH="/opt/deno/bin:${PATH}" PORT=10000
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deno.land/install.sh | sh
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
COPY templates ./templates
EXPOSE 10000
CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 900 app:app"]
