# 🏸 BadmintonPro - Hệ Sinh Thái Quản Lý Đặt Sân Cầu Lông

BadmintonPro là một nền tảng quản lý đặt sân cầu lông chuyên nghiệp, cung cấp hệ sinh thái từ Người Chơi đến Chủ Sân và Nhân Viên thu ngân. Dự án được tối ưu để hoạt động thời gian thực (real-time booking) và dễ dàng mở rộng.

## 🚀 Công Nghệ Sử Dụng (Tech Stack)

### Backend
- **Ngôn ngữ:** Python 3.x
- **Framework Chính:** Django (MVT architecture)
- **Microservice:** FastAPI (Xử lý các logic lock sân đồng thời, ngăn chặn việc 2 người đặt cùng lúc - Race Condition).
- **Asynchronous Tasks:** Celery (Hàng đợi tác vụ bất đồng bộ, xử lý kịch bản hủy sân tự động, gửi email...).
- **Cơ sở dữ liệu:** PostgreSQL (Lưu trữ dữ liệu quan hệ, transaction toàn vẹn).
- **Cache / Message Broker:** Redis (Sử dụng làm môi trường đệm lưu khóa lock sân và là Broker cho Celery).

### Frontend
- **Ngôn ngữ:** HTML5, CSS3, JavaScript (Vanilla JS).
- **Thư viện UI/UX:** Bootstrap 5 (Responsive UI), FontAwesome (Icons).
- **Biểu đồ Analytics:** Chart.js (Vẽ biểu đồ hình tròn, biểu đồ đường doanh thu).

### DevOps & Triển khai
- **Containerization:** Docker & Docker Compose (Quản lý các container đồng bộ: Web Django, FastAPI, Celery Worker, PostgreSQL, Redis).
- **Static / Media Serves:** WhiteNoise (Phục vụ static resources trong production).

---

## 🛠 Tính Năng Nổi Bật

**1. Dành cho Khách Hàng (Người chơi)**
- Đăng nhập/Đăng ký, bao gồm hỗ trợ Đăng nhập Mạng xã hội (Google, Github).
- Xem danh sách sân, tìm kiếm sân trống theo giờ/ngày thông minh.
- Giao diện "Booking Timeline" trực quan: Đặt sân giữ chỗ ngay lập tức qua API FastAPI.

**2. Dành cho Nhân viên (Staff)**
- Hệ thống POS bán hàng tại quầy (Nước, Cầu lông, Đồ ăn nhẹ).
- Chọn phương thức thanh toán **Tiền Mặt** hoặc **Chuyển Khoản** linh hoạt cho các biên lai.

**3. Dành cho Chủ Sân (Partner)**
- Bảng điều khiển (Dashboard): Thống kê doanh thu thời gian thực. Theo dõi tổng thu theo biểu đồ đường 7 ngày. Phễu tỷ trọng thanh toán Tiền mặt vs Chuyển khoản (Doughnut Chart).
- Quản lý CRM: Lưu trữ lịch sử đến sân, số tiền tổng chi tiêu của từng khách hàng.
- Phân quyền nội bộ: Tạo và gán quyền chi nhánh cho các tài khoản thu ngân/nhân viên.

---

## ⚙️ Hướng Dẫn Cài Đặt và Chạy (Local Development)

Dự án được cấu hình bằng Docker, bạn chỉ cần một vài lệnh để hệ thống tự động khởi chạy môi trường:

### Bước 1: Clone dự án và cấu hình biến môi trường
```bash
git clone https://github.com/your-username/badmintonpro.git
cd badmintonpro
```
Tạo file `.env` từ file `.env.example` và thiết lập các API key/password tương ứng:
```bash
cp .env.example .env
```

### Bước 2: Chạy Docker Compose
Khởi động cụm dịch vụ ẩn dưới background bằng Docker Compose:
```bash
docker compose up -d --build
```
Lệnh này sẽ tự động pull các image, cài đặt requirements, và khởi động: `db` (PostgreSQL), `redis`, `web` (Django), `fastapi`, và `celery`.

### Bước 3: Tạo Migrations (Nếu chạy lần đầu)
```bash
docker compose exec web python manage.py migrate
```

### Bước 4: Tạo tài khoản Admin (Superuser)
```bash
docker compose exec web python manage.py createsuperuser
```

### Bước 5: Truy cập 
- Giao diện chính (Khách hàng & Partner): [http://localhost:8000](http://localhost:8000)
- Trang admin quản trị Django: [http://localhost:8000/admin](http://localhost:8000/admin)
- Endpoint FastAPI đặt lịch: [http://localhost:8001](http://localhost:8001)

---

## 🛡 Bảo Mật (Security Note)
- File `.env` chứa các thông số quan trọng (Secret Key, DB credentials) đã được đưa vào `.gitignore`. Tuyệt đối không push file này lên repository public.
- Mọi mật khẩu và API key sẽ được lấy tuần tự từ biến môi trường.

---
_Sản phẩm được code với 💚 dành cho cộng đồng yêu Cầu Lông Việt Nam._
