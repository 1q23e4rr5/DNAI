# استفاده از Python 3.9 یا بالاتر
FROM python:3.9-slim

# تنظیم زمان تهران
ENV TZ=Asia/Tehran
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# تنظیم پورت (برای Render)
ENV PORT=10000

# کپی فایل‌های مورد نیاز
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل پروژه
COPY . .

# اجرای برنامه با run.py
CMD ["python", "run.py"]
