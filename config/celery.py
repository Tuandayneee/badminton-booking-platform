import os
from celery import Celery

# Thiết lập biến môi trường mặc định cho Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Load cấu hình từ settings.py, bắt đầu bằng 'CELERY_'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tự động tìm task trong các app (booking, partner, users...)
app.autodiscover_tasks()