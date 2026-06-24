# استفاده از Python 3.9
FROM python:3.9-slim

# تنظیم زمان تهران
ENV TZ=Asia/Tehran
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# نصب وابستگی‌های سیستمی مورد نیاز OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# تنظیم متغیرهای محیطی
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# ایجاد دایرکتوری کاری
WORKDIR /app

# کپی و نصب وابستگی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل پروژه
COPY . .

# ایجاد دایرکتوری برای دیتابیس (اگر از SQLite استفاده می‌کنید)
RUN mkdir -p /app/instance

# اجرای برنامه
CMD ["python", "run.py"]
