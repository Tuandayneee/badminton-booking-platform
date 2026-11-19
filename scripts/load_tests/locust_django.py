"""
LOCUST LOAD TESTING CHO DJANGO END-TO-END FLOW (PORT 8000)
Chạy với host: http://localhost:8000
"""

import os
import random
from locust import task, between
from locust.contrib.fasthttp import FastHttpUser

TARGET_COURT_ID = int(os.getenv("TARGET_COURT_ID", "1"))
TARGET_DATE = os.getenv("TARGET_DATE", "2026-11-20")


class DjangoBookingE2EUser(FastHttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.username = f"test_user_{random.randint(1, 500)}"
        self.password = "123456"
        self.csrf_token = ""
        self._login_and_get_csrf()

    def _login_and_get_csrf(self):
        resp = self.client.get("/users/login/", name="[Django] 1. Get Login Page")
        self.csrf_token = resp.cookies.get("csrftoken", "")

        login_data = {
            "username": self.username,
            "password": self.password,
            "csrfmiddlewaretoken": self.csrf_token
        }
        headers = {
            "Referer": f"{self.host}/users/login/",
            "X-CSRFToken": self.csrf_token
        }
        self.client.post(
            "/users/login/",
            data=login_data,
            headers=headers,
            name="[Django] 2. Submit Login"
        )
        self.csrf_token = self.client.cookies.get("csrftoken", self.csrf_token)

    @task(3)
    def view_booking_timeline(self):
        center_id = "00000000-0000-0000-0000-000000000001"
        self.client.get(
            f"/booking/booking_timeline/{center_id}?date={TARGET_DATE}",
            name="[Django] 3. View Timeline"
        )
