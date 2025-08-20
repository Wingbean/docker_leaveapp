FROM python:3.10-slim

# System deps สำหรับ build mysqlclient ให้เสถียรบน arm64/Raspberry Pi
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libmariadb-dev \
    libmariadb-dev-compat curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# อัปเกรด pip/setuptools/wheel เพื่อลดปัญหา build จากซอร์ส
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# คัดลอกซอร์สโค้ด
COPY . .

EXPOSE 5001
CMD ["gunicorn", "--timeout", "180", "--graceful-timeout", "30","--access-logfile", "-", "--error-logfile", "-","-w", "2", "-b", "0.0.0.0:5001", "app:app"]