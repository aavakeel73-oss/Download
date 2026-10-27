FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/opt/deno sh
ENV PATH="/opt/deno/bin:${PATH}"
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates ./templates
ENV PORT=10000
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 240 app:app"]
