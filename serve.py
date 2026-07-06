import os
import subprocess
import sys

try:
    port = int(os.environ.get("PORT", "8000"))
except (ValueError, TypeError):
    port = 8000

sys.exit(subprocess.call([
    "gunicorn", "config.wsgi:application",
    f"--bind=0.0.0.0:{port}",
    "--workers=2",
    "--timeout=120",
    "--access-logfile=-",
    "--error-logfile=-",
]))
