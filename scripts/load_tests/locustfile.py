"""
LOCUST LOAD TESTING - FASTAPI LOCK-SLOT ENGINE (PORT 8001)
Phiên bản đã tối ưu: Dùng HttpUser chuẩn thay vì FastHttpUser
để tránh lỗi "status 0: None" do gevent C-binding bị connection reset.
"""

import hashlib
import hmac
import os
import random
import time
from locust import HttpUser, task, between

INTERNAL_SECRET = os.getenv("INTERNAL_LOCK_SECRET", "dev-internal-lock-secret")
TARGET_COURT_ID = int(os.getenv("TARGET_COURT_ID", "1"))
TARGET_DATE = os.getenv("TARGET_DATE", "2026-11-20")


def generate_hmac_token(user_id: int, secret: str = INTERNAL_SECRET) -> str:
    timestamp = str(int(time.time()))
    payload = f"{timestamp}:{user_id}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{timestamp}:{user_id}:{signature}"


class FastAPILockSlotUser(HttpUser):
    """
    Test trực tiếp FastAPI Microservice (Port 8001)
    Dùng HttpUser (requests + urllib3 connection pooling) thay vì FastHttpUser
    để xử lý tốt hơn khi số lượng VU lớn trên máy cá nhân.
    """
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.user_id = random.randint(1, 100000)
        # Cấu hình connection pooling phía client
        adapter = self.client.adapters.get("http://")
        if adapter:
            adapter._pool_connections = 50
            adapter._pool_maxsize = 200

    @task(8)
    def test_random_slot_locking(self):
        """80% traffic: Đặt các khung giờ khác nhau trên các sân khác nhau (Normal Traffic)"""
        random_court_id = random.randint(1, 10)
        random_hour = random.randint(6, 21)
        random_minute = random.choice(["00", "30"])
        start_time_str = f"{random_hour:02d}:{random_minute}"

        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": generate_hmac_token(self.user_id),
        }
        payload = {
            "court_id": random_court_id,
            "date": TARGET_DATE,
            "start_time": start_time_str,
            "end_time": f"{random_hour:02d}:59"
        }

        with self.client.post(
            "/api/v1/lock-slot/",
            json=payload,
            headers=headers,
            catch_response=True,
            name="[FastAPI] Lock Random Slot",
            timeout=10,
        ) as response:
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Lỗi {response.status_code}: {response.text}")

    @task(2)
    def test_hotspot_collision(self):
        """20% traffic: Nhiều người cùng tranh 1 slot hot 18:00 Court 1 (Race Condition Test)"""
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": generate_hmac_token(self.user_id),
        }
        payload = {
            "court_id": TARGET_COURT_ID,
            "date": TARGET_DATE,
            "start_time": "18:00",
            "end_time": "18:30"
        }

        with self.client.post(
            "/api/v1/lock-slot/",
            json=payload,
            headers=headers,
            catch_response=True,
            name="[FastAPI] Lock Hotspot Slot (18:00)",
            timeout=10,
        ) as response:
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Lỗi {response.status_code}: {response.text}")
