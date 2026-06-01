FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN groupadd --gid 1001 svc && useradd --uid 1001 --gid svc --no-create-home --shell /bin/false svc
COPY --from=builder /install /usr/local
COPY . .
RUN mkdir -p /certs/service-c && chown -R svc:svc /certs
USER svc
EXPOSE 8003
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--log-level", "warning"]
