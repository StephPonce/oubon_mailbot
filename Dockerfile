# --- Oubon MailBot container (Python 3.12) ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*
RUN update-ca-certificates

WORKDIR /app

# Leverage cache when requirements/poetry files don't change
COPY requirements.txt* pyproject.toml* poetry.lock* /tmp/dep/
RUN python -m pip install --upgrade pip \
 && if [ -f /tmp/dep/requirements.txt ]; then pip install -r /tmp/dep/requirements.txt; fi

# App
COPY . /app

# The app listens on 8011 inside the container
EXPOSE 8011
CMD ["uvicorn", "ospra_os.main:app", "--host", "0.0.0.0", "--port", "8011"]
