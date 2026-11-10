"""
Rule-based Chatbot Engine cho Badminton Pro
Sử dụng keyword matching - không cần API bên ngoài
"""
import re
import random

# ============================================
# CHATBOT RESPONSES (Knowledge Base)
# ============================================

RESPONSES = {
    'greeting': {
        'keywords': ['xin chào', 'hello', 'hi', 'chào', 'hey', 'alo', 'chào bạn', 'bắt đầu'],
        'replies': [
            'Xin chào! 👋 Tôi là trợ lý của <strong>Badminton Pro</strong>.<br>Tôi có thể giúp bạn về đặt sân, thanh toán, chính sách hủy sân và nhiều hơn nữa. Hãy hỏi tôi nhé! 😊',
            'Chào bạn! 🏸 Rất vui được hỗ trợ bạn. Bạn cần giúp gì hôm nay?',
        ]
    },
    'booking_guide': {
        'keywords': ['hướng dẫn đặt sân', 'đặt sân', 'cách đặt', 'book sân', 'đặt chỗ', 'làm sao đặt', 'muốn đặt', 'đặt lịch'],
        'replies': [
            '🏸 <strong>Hướng dẫn đặt sân (4 bước):</strong><br><br>'
            '<strong>Bước 1: Tìm kiếm sân</strong><br>'
            'Tại trang chủ, nhập khu vực, ngày chơi và giờ bắt đầu vào thanh tìm kiếm nhanh.<br><br>'
            '<strong>Bước 2: Chọn sân & khung giờ</strong><br>'
            'Click vào sân muốn đặt, xem thông tin chi tiết. Chọn ngày và tích các khung giờ trống (màu xanh).<br><br>'
            '<strong>Bước 3: Thanh toán</strong><br>'
            'Kiểm tra đơn hàng, thanh toán qua VNPAY, Momo hoặc chuyển khoản. Bạn có <strong>10 phút</strong> để hoàn tất.<br><br>'
            '<strong>Bước 4: Xác nhận & đến sân</strong><br>'
            'Nhận mã đơn hàng, đưa mã cho nhân viên khi đến sân. ✅'
        ]
    },
    'payment': {
        'keywords': ['thanh toán', 'trả tiền', 'payment', 'chuyển khoản', 'vnpay', 'momo', 'qr', 'giá', 'phí', 'tiền'],
        'replies': [
            '💰 <strong>Thông tin thanh toán:</strong><br><br>'
            '<ul>'
            '<li>Chuyển khoản ngân hàng (quét mã QR)</li>'
            '<li>VNPAY</li>'
            '<li>Momo</li>'
            '<li>Ví điện tử</li>'
            '</ul>'
            '⏰ Thời gian chờ thanh toán: <strong>10 phút</strong>. Nếu không thanh toán kịp, slot sẽ bị hủy tự động.<br><br>'
            'Hệ thống tự động xác nhận sau khi nhận được thanh toán. ✅<br>'
            'Giá sân do chủ sân đối tác niêm yết.'
        ]
    },
    'cancel_policy': {
        'keywords': ['hủy', 'hủy sân', 'cancel', 'hoàn tiền', 'đổi lịch', 'chính sách hủy', 'refund'],
        'replies': [
            '❌ <strong>Chính sách hủy sân:</strong><br><br>'
            '<ul>'
            '<li>Đơn đặt sân thành công <strong>KHÔNG THỂ HỦY</strong> tự động trên hệ thống.</li>'
            '<li>Nếu cần hủy hoặc đổi lịch → liên hệ trực tiếp <strong>chủ sân</strong> (SĐT có trong chi tiết đơn hàng).</li>'
            '<li>Việc hoàn tiền (nếu có) do chủ sân quyết định.</li>'
            '</ul>'
            '📞 Cần hỗ trợ thêm? Gọi hotline <strong>0912.345.678</strong>'
        ]
    },
    'faq': {
        'keywords': ['câu hỏi', 'faq', 'thường gặp', 'thắc mắc', 'hỏi đáp'],
        'replies': [
            '❓ <strong>Câu hỏi thường gặp:</strong><br><br>'
            '<strong>Q: Làm sao biết sân trống?</strong><br>'
            'A: Hệ thống đồng bộ Real-time. Khung giờ <span style="color:#22c55e">xanh</span> = còn trống, <span style="color:#9ca3af">xám</span> = đã đặt.<br><br>'
            '<strong>Q: Đăng ký làm đối tác chủ sân?</strong><br>'
            'A: Vào trang "Dành cho Chủ sân", điền thông tin. Đội ngũ liên hệ trong 24h.<br><br>'
            '<strong>Q: Thanh toán lỗi, trừ tiền nhưng chưa xác nhận?</strong><br>'
            'A: Hệ thống tự đối soát, hoàn tiền trong 1-3 ngày. Gọi Hotline <strong>0912.345.678</strong> để xử lý ngay.'
        ]
    },
    'membership': {
        'keywords': ['hạng', 'thành viên', 'vip', 'điểm', 'tích điểm', 'bronze', 'silver', 'gold', 'diamond', 'đồng', 'bạc', 'vàng', 'kim cương', 'ưu đãi'],
        'replies': [
            '🏅 <strong>Hạng thành viên & Tích điểm:</strong><br><br>'
            '<ul>'
            '<li>🥉 <strong>Đồng (Bronze)</strong>: Mặc định khi đăng ký</li>'
            '<li>🥈 <strong>Bạc (Silver)</strong>: Từ 120 điểm</li>'
            '<li>🥇 <strong>Vàng (Gold)</strong>: Từ 250 điểm</li>'
            '<li>💎 <strong>Kim Cương (Diamond)</strong>: Từ 500 điểm</li>'
            '</ul>'
            'Tích lũy điểm sau mỗi lần đặt sân để nâng hạng VIP và nhận ưu đãi độc quyền! 🎉'
        ]
    },
    'court_type': {
        'keywords': ['loại sân', 'sàn gỗ', 'sàn thảm', 'wooden', 'carpet', 'giờ vàng', 'cao điểm'],
        'replies': [
            '🏸 <strong>Loại sân cầu lông:</strong><br><br>'
            '<ul>'
            '<li>🪵 <strong>Sàn gỗ (Wooden)</strong>: Bề mặt chất lượng cao</li>'
            '<li>🟩 <strong>Sàn thảm (Carpet)</strong>: Êm chân, phổ biến</li>'
            '</ul>'
            'Mỗi sân có giá cơ bản/giờ và có thể có <strong>giá giờ vàng</strong> (cao hơn vào khung giờ cao điểm). ⏰'
        ]
    },
    'order_status': {
        'keywords': ['trạng thái', 'đơn hàng', 'order', 'pending', 'confirmed', 'completed', 'xác nhận'],
        'replies': [
            '📋 <strong>Trạng thái đơn hàng:</strong><br><br>'
            '<strong>Chờ xác nhận</strong> (Pending)<br>→ <strong>Chờ xác nhận thanh toán</strong> (Waiting Verify)<br>→ <strong>Đã thanh toán</strong> (Confirmed)<br>→ <strong>Hoàn thành</strong> (Completed)<br><br>'
            'Admin có thể hủy đơn nếu cần (Admin Cancelled).'
        ]
    },
    'account': {
        'keywords': ['tài khoản', 'đăng nhập', 'đăng ký', 'login', 'register', 'mật khẩu', 'password', 'google', 'github', 'hồ sơ'],
        'replies': [
            '👤 <strong>Tài khoản người dùng:</strong><br><br>'
            '<ul>'
            '<li>Vai trò: Khách hàng, Đối tác, Nhân viên, Quản trị viên</li>'
            '<li>Đăng nhập bằng <strong>Email/Password</strong> hoặc <strong>Google, GitHub</strong></li>'
            '<li>Có thể thay đổi mật khẩu, cập nhật hồ sơ cá nhân</li>'
            '</ul>'
            'Mỗi cá nhân chỉ được sở hữu <strong>1 tài khoản</strong>.'
        ]
    },
    'contact': {
        'keywords': ['liên hệ', 'hotline', 'email', 'hỗ trợ', 'support', 'số điện thoại', 'địa chỉ', 'facebook', 'gọi'],
        'replies': [
            '📞 <strong>Thông tin liên hệ:</strong><br><br>'
            '<ul>'
            '<li>📱 Hotline: <strong>0912.345.678</strong></li>'
            '<li>📧 Email: <strong>support@badmintonpro.vn</strong></li>'
            '<li>📍 Địa chỉ: Hà Nội, Việt Nam</li>'
            '<li>🌐 Facebook, TikTok, YouTube: <strong>Badminton Pro</strong></li>'
            '</ul>'
            'Đội ngũ luôn sẵn sàng hỗ trợ bạn! 💪'
        ]
    },
    'about': {
        'keywords': ['giới thiệu', 'về chúng tôi', 'badminton pro là gì', 'nền tảng', 'about'],
        'replies': [
            '🏸 <strong>Về Badminton Pro:</strong><br><br>'
            'Badminton Pro là nền tảng đặt sân cầu lông trực tuyến <strong>hàng đầu Việt Nam</strong>.<br><br>'
            '<ul>'
            '<li>Kết nối người chơi với 50+ sân đối tác toàn quốc</li>'
            '<li>Đặt sân thông minh, thanh toán chỉ trong 30 giây</li>'
            '<li>10,000+ người chơi hàng tháng</li>'
            '<li>Uptime 99.9%</li>'
            '</ul>'
        ]
    },
    'security': {
        'keywords': ['bảo mật', 'an toàn', 'security', 'thông tin cá nhân', 'riêng tư', 'privacy'],
        'replies': [
            '🔒 <strong>Bảo mật & An toàn:</strong><br><br>'
            '<ul>'
            '<li>Mã hóa mật khẩu bằng PBKDF2 + SHA256</li>'
            '<li>Bảo vệ form bằng CSRF token</li>'
            '<li>Triển khai Docker với phân quyền nghiêm ngặt</li>'
            '<li><strong>Không bán, cho thuê hoặc trao đổi</strong> thông tin cá nhân cho bên thứ ba</li>'
            '</ul>'
            'Thông tin của bạn luôn được bảo vệ an toàn! 🛡️'
        ]
    },
    'partner': {
        'keywords': ['đối tác', 'chủ sân', 'partner', 'đăng ký sân', 'hợp tác'],
        'replies': [
            '🤝 <strong>Đăng ký đối tác chủ sân:</strong><br><br>'
            '<ul>'
            '<li>Vào trang <strong>"Dành cho Chủ sân"</strong> hoặc <strong>"Liên hệ đối tác"</strong></li>'
            '<li>Điền thông tin đăng ký</li>'
            '<li>Đội ngũ Badminton Pro sẽ liên hệ trong <strong>24h</strong></li>'
            '<li>Hướng dẫn thiết lập sân <strong>miễn phí</strong>!</li>'
            '</ul>'
        ]
    },
    'thanks': {
        'keywords': ['cảm ơn', 'thank', 'thanks', 'tks', 'ok', 'được rồi', 'hiểu rồi'],
        'replies': [
            'Không có gì! 😊 Nếu cần hỗ trợ thêm, đừng ngại hỏi tôi nhé! 🏸',
            'Rất vui được giúp bạn! Chúc bạn có trải nghiệm tuyệt vời với Badminton Pro! 🎉',
        ]
    },
    'slot_check': {
        'keywords': ['sân trống', 'còn trống', 'khung giờ', 'slot', 'lịch trống', 'check sân'],
        'replies': [
            '📅 <strong>Kiểm tra sân trống:</strong><br><br>'
            'Hệ thống đồng bộ <strong>Real-time</strong> với phần mềm quản lý của chủ sân:<br>'
            '<ul>'
            '<li>🟢 Khung giờ <strong>xanh</strong> = Còn trống</li>'
            '<li>⚪ Khung giờ <strong>xám</strong> = Đã đặt hoặc sân nghỉ</li>'
            '</ul>'
            'Bạn có thể chọn nhiều khung giờ liên tiếp hoặc nhiều sân cùng lúc! 🏸'
        ]
    },
    'payment_error': {
        'keywords': ['lỗi thanh toán', 'trừ tiền', 'chưa xác nhận', 'mất tiền', 'không thành công'],
        'replies': [
            '⚠️ <strong>Thanh toán lỗi - Đã trừ tiền nhưng chưa xác nhận?</strong><br><br>'
            'Đừng lo lắng! Hệ thống sẽ tự động đối soát và <strong>hoàn tiền trong 1-3 ngày làm việc</strong>.<br><br>'
            'Để xử lý ngay, hãy:<br>'
            '<ul>'
            '<li>📞 Gọi Hotline: <strong>0912.345.678</strong></li>'
            '<li>Cung cấp <strong>mã giao dịch</strong> để đội ngũ xử lý nhanh nhất</li>'
            '</ul>'
        ]
    },
}

# Default response khi không khớp keyword nào
DEFAULT_RESPONSES = [
    'Xin lỗi, tôi chưa hiểu rõ câu hỏi của bạn 😅<br><br>'
    'Bạn có thể thử hỏi về:<br>'
    '<ul>'
    '<li>📋 Hướng dẫn đặt sân</li>'
    '<li>💰 Thanh toán</li>'
    '<li>❌ Chính sách hủy sân</li>'
    '<li>❓ Câu hỏi thường gặp</li>'
    '<li>📞 Liên hệ hỗ trợ</li>'
    '</ul>'
    'Hoặc liên hệ hotline <strong>0912.345.678</strong> để được hỗ trợ trực tiếp! 🙏',
]


def normalize_text(text):
    """Chuẩn hóa text tiếng Việt để matching tốt hơn"""
    text = text.lower().strip()
    # Loại bỏ dấu câu
    text = re.sub(r'[?.!,;:()"\']', ' ', text)
    # Loại bỏ khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_chatbot_response(user_message):
    """Trả về response dựa trên keyword matching"""
    normalized = normalize_text(user_message)

    best_match = None
    best_score = 0

    for intent, data in RESPONSES.items():
        score = 0
        for keyword in data['keywords']:
            if keyword in normalized:
                # Ưu tiên keyword dài hơn (chính xác hơn)
                score += len(keyword)

        if score > best_score:
            best_score = score
            best_match = intent

    if best_match and best_score > 0:
        replies = RESPONSES[best_match]['replies']
        return random.choice(replies)

    return random.choice(DEFAULT_RESPONSES)
