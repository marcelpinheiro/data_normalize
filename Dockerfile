FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    automake \
    libtool \
    pkg-config \
    ca-certificates \
    python3-dev \
    libffi-dev \
    libssl-dev \
    wget \
    unzip \
    && apt-get clean

# Build libpostal without SSE2 (fix for M1 building for amd64)
RUN git clone https://github.com/openvenues/libpostal /opt/libpostal && \
    cd /opt/libpostal && \
    ./bootstrap.sh && \
    ./configure --disable-sse2 && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

CMD ["python", "main.py"]
