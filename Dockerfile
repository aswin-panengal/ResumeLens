FROM python:3.12-slim

WORKDIR /app

# System deps: gcc for psycopg2-binary build, libpq5 for PostgreSQL runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect WhiteNoise-compressed static files at build time
ARG DJANGO_SECRET_KEY=collectstatic-build-placeholder
ENV DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
RUN python manage.py collectstatic --no-input

EXPOSE 8000

# 2 workers fits within 512MB RAM (Railway/Render free tier)
# 120s timeout covers Gemini + Groq API round-trip latency
CMD gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
