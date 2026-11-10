import concurrent.futures
import hashlib
import hmac
import os
import time

import requests

URL = os.getenv("FASTAPI_LOCK_URL", "http://fastapi:8001/api/v1/lock-slot/")
SECRET = os.getenv("INTERNAL_LOCK_SECRET", "dev-internal-lock-secret")

PAYLOAD_TEMPLATE = {
    "court_id": 999,
    "date": "2026-05-21",
    "start_time": "18:00",
    "end_time": "19:00",
}


def make_internal_token(user_id):
    ts = str(int(time.time()))
    sig = hmac.new(SECRET.encode("utf-8"), f"{ts}:{user_id}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{ts}:{user_id}:{sig}"


def make_request(user_id):
    headers = {"X-Internal-Token": make_internal_token(user_id)}
    try:
        response = requests.post(URL, json=PAYLOAD_TEMPLATE, headers=headers, timeout=5)
        return user_id, response.status_code, response.json()
    except Exception as exc:
        return user_id, 500, str(exc)


if __name__ == "__main__":
    print("Bắt đầu bài kiểm tra đồng thời (Concurrency Test) - 50 User truy cập cùng lúc...")
    start_time = time.time()
    success_count = 0
    fail_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(make_request, i) for i in range(1, 51)]
        for future in concurrent.futures.as_completed(futures):
            _, status, _ = future.result()
            if status == 200:
                success_count += 1
            else:
                fail_count += 1

    elapsed = time.time() - start_time
    print(f"Tổng: 50 | Thành công: {success_count} | Thất bại: {fail_count} | Thời gian: {elapsed:.2f}s")
