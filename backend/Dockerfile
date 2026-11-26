# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copied first so the dependency layer is cached independently of app source.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user; /app stays read-only to it, which is all the app needs.
RUN useradd --create-home --uid 1000 appuser
# Product photos are written at runtime and served from this directory. Create
# it before dropping privileges so the app user can write uploads safely.
RUN mkdir -p /app/uploads/products && chown -R appuser:appuser /app/uploads
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
