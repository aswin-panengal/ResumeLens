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

# gunicorn.conf.py reads PORT from os.environ — no shell expansion needed
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
