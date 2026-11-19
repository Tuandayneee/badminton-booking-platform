import http from 'k6/http';
import { check, sleep } from 'k6';
import crypto from 'k6/crypto';
import { Trend, Rate, Counter } from 'k6/metrics';

// ==========================================
// CUSTOM METRICS CHO BÁO CÁO SENIOR CV
// ==========================================
export const lockSlotDuration = new Trend('lock_slot_duration', true);
export const successLocks = new Counter('success_locks_total');
export const conflictLocks = new Counter('conflict_locks_total');
export const errorLocks = new Counter('error_locks_total');
export const successfulLockRate = new Rate('successful_lock_rate');

// ==========================================
// CẤU HÌNH THỜI GIAN & KỊCH BẢN TẢI (STAGES)
// ==========================================
export const options = {
  // Thử thách tải đa tầng (Multi-stage load profile)
  stages: [
    { duration: '30s', target: 50 },    // Warm-up: 0 -> 50 users trong 30s
    { duration: '1m',  target: 200 },   // Ramp-up: 50 -> 200 users trong 1m
    { duration: '2m',  target: 500 },   // Peak traffic / Stress: Duy trì 500 VUs trong 2m
    { duration: '30s', target: 1000 },  // Spike test: Đột biến lên 1,000 VUs trong 30s (Flash-sale mô phỏng)
    { duration: '1m',  target: 0 },     // Cool-down: Hạ tải về 0
  ],
  thresholds: {
    // Tiêu chí chấp nhận dịch vụ (SLA / SLO)
    'http_req_duration': ['p(95)<150', 'p(99)<300'], // 95% request phải xong dưới 150ms
    'lock_slot_duration': ['p(95)<80'],              // Với endpoint lock Redis, 95% dưới 80ms
    'http_req_failed': ['rate<0.01'],                // Tỷ lệ lỗi hệ thống (5xx, timeout) dưới 1%
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:8001';
const SECRET_KEY = __ENV.INTERNAL_LOCK_SECRET || 'dev-internal-lock-secret';
const TARGET_DATE = __ENV.TARGET_DATE || '2026-11-20';

/**
 * Hàm sinh chữ ký HMAC-SHA256 theo chuẩn bảo mật của hệ thống
 */
function generateHMAC(userId) {
  const ts = Math.floor(Date.now() / 1000).toString();
  const payload = `${ts}:${userId}`;
  const hasher = crypto.createHMAC('sha256', SECRET_KEY);
  hasher.update(payload);
  const signature = hasher.digest('hex');
  return `${ts}:${userId}:${signature}`;
}

export default function () {
  // Mỗi Virtual User tương ứng với 1 user_id duy nhất
  const userId = __VU * 10000 + __ITER;

  // Mô phỏng 2 kịch bản:
  // 80% truy cập các khung giờ thông thường (High RPS Distributed)
  // 20% truy cập tranh chấp khung giờ hot 18:00 (Concurrency Collision / Race Condition Test)
  const isHotSpot = Math.random() < 0.20;

  let courtId = 1;
  let startTime = '18:00';

  if (!isHotSpot) {
    courtId = Math.floor(Math.random() * 10) + 1; // Sân 1 -> 10
    const hour = Math.floor(Math.random() * 14) + 7; // Giờ từ 07:00 đến 21:00
    const minute = Math.random() < 0.5 ? '00' : '30';
    startTime = `${hour.toString().padStart(2, '0')}:${minute}`;
  }

  const payload = JSON.stringify({
    court_id: courtId,
    date: TARGET_DATE,
    start_time: startTime,
    end_time: '23:59',
  });

  const token = generateHMAC(userId);
  const headers = {
    'Content-Type': 'application/json',
    'X-Internal-Token': token,
  };

  const startTimeReq = Date.now();
  const res = http.post(`${BASE_URL}/api/v1/lock-slot/`, payload, {
    headers: headers,
    tags: { name: isHotSpot ? 'Lock_Hotspot_Slot' : 'Lock_Normal_Slot' },
  });
  const latency = Date.now() - startTimeReq;
  lockSlotDuration.add(latency);

  // Phân tích kết quả:
  // 200 OK: Lock thành công (Ghi nhận vào Redis SETNX)
  // 409 Conflict: Slot đã bị user khác chiếm (Đúng thiết kế kiến trúc chống race condition)
  // >= 500: Lỗi backend / Redis sập
  const isSuccess = res.status === 200;
  const isConflict = res.status === 409;
  const isError = res.status >= 500 || res.status === 0;

  if (isSuccess) {
    successLocks.add(1);
    successfulLockRate.add(true);
  } else if (isConflict) {
    conflictLocks.add(1);
    successfulLockRate.add(false);
  } else {
    errorLocks.add(1);
  }

  check(res, {
    'Status là 200 hoặc 409 (Đúng business logic)': (r) => r.status === 200 || r.status === 409,
    'Phản hồi không bị lỗi 5xx': (r) => r.status < 500,
    'Thời gian phản hồi < 200ms': (r) => r.timings.duration < 200,
  });

  // Nghỉ giữa các lượt click (Pacing)
  sleep(Math.random() * 0.2 + 0.1);
}
