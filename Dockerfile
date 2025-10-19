# --- Oubon MailBot container (Python 3.12) ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (build-essential needed for some libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# If present, install deps from requirements/poetry first to leverage Docker layer cache
COPY requirements.txt* pyproject.toml* poetry.lock* /tmp/dep/
RUN python -m pip install --upgrade pip \
    && if [ -f /tmp/dep/requirements.txt ]; then pip install -r /tmp/dep/requirements.txt; fi

# Copy app code
COPY . /app

EXPOSE 8011

# Uvicorn entrypoint
CMD ["uvicorn", "ospra_os.main:app", "--host", "0.0.0.0", "--port", "8011"]
