FROM python:3.10-slim

# prevent pyc files, force stdout logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# copy requirements first
COPY backend/requirements.txt ./backend/requirements.txt

# install system libs (needed for reportlab, motor, SSL, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# upgrade pip
RUN pip install --upgrade pip setuptools wheel

# install backend requirements
RUN pip install -r backend/requirements.txt

# copy backend code
COPY backend ./backend

# expose the port
EXPOSE 8000

# run uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
