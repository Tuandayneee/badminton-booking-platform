
FROM python:3.12-slim

# 2. Không tạo file .pyc (file rác của python) và in log ngay lập tức
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Tạo thư mục làm việc trong container
WORKDIR /app

# 4. Cài đặt các thư viện cần thiết cho hệ điều hành (để cài được PostgreSQL driver)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy file requirements.txt từ máy thật vào container
COPY requirements.txt /app/

# 6. Cài đặt các thư viện Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 7. Copy toàn bộ code dự án vào container
COPY . /app/

# 8. Mở cổng 8000 (Cổng mặc định của Django)
EXPOSE 8000

# 9. Lệnh chạy server khi container khởi động
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]