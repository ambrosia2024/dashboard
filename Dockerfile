# Base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    binutils \
    gdal-bin \
    libgdal-dev \
    python3-dev \
    libpq-dev \
    postgresql-client \
    gcc \
    g++ \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Then pip install GDAL
RUN pip install --no-cache-dir GDAL==3.6.2

# Copy only requirements first for better caching
COPY requirements.txt /app/requirements.txt

# Install Python dependencies before copying entire project (Docker caching)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

# Copy rest of the project files
COPY . /app/

# Copy entrypoint script and give execute permissions
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose the application port
EXPOSE 8000

# Default command (overridden in docker-compose)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
