
document.addEventListener('DOMContentLoaded', function () {

    // --- DOM Elements ---
    const toggle = document.getElementById('chatbot-toggle');
    const chatWindow = document.getElementById('chatbot-window');
    const closeBtn = document.getElementById('chatbot-close');
    const messagesContainer = document.getElementById('chatbot-messages');
    const inputField = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send');
    const quickRepliesContainer = document.getElementById('chatbot-quick-replies');

    // --- State ---
    let conversationHistory = [];
    let isWaiting = false;

    // --- Quick Reply Options ---
    const quickReplies = [
        { icon: '📋', text: 'Hướng dẫn đặt sân' },
        { icon: '💰', text: 'Thanh toán' },
        { icon: '❌', text: 'Chính sách hủy sân' },
        { icon: '❓', text: 'Câu hỏi thường gặp' },
        { icon: '📞', text: 'Liên hệ hỗ trợ' },
    ];

    // --- Init ---
    function init() {
        renderQuickReplies();
        addBotMessage(
            `Xin chào! 👋 Tôi là trợ lý AI của <strong>Badminton Pro</strong>.<br>` +
            `Tôi có thể giúp bạn về:<br>` +
            `<ul class="welcome-list">` +
            `<li>🏸 Đặt sân cầu lông</li>` +
            `<li>💳 Thanh toán & Chính sách</li>` +
            `<li>📖 Hướng dẫn sử dụng</li>` +
            `<li>📞 Liên hệ & Hỗ trợ</li>` +
            `</ul>` +
            `Hãy hỏi tôi bất cứ điều gì! 😊`
        );
    }

    // --- Toggle Chat Window ---
    toggle.addEventListener('click', function () {
        chatWindow.classList.add('open');
        toggle.classList.add('active');
        inputField.focus();
    });

    closeBtn.addEventListener('click', function () {
        chatWindow.classList.remove('open');
        toggle.classList.remove('active');
    });

    // --- Send Message ---
    sendBtn.addEventListener('click', sendMessage);
    inputField.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    function sendMessage() {
        const text = inputField.value.trim();
        if (!text || isWaiting) return;

        addUserMessage(text);
        inputField.value = '';
        hideQuickReplies();
        showTyping();
        setWaiting(true);

        // Send to backend
        fetch('/api/chatbot/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({
                message: text,
                history: conversationHistory.slice(-10) // Send last 10 messages for context
            }),
        })
            .then(response => {
                if (!response.ok) throw new Error('Server error');
                return response.json();
            })
            .then(data => {
                hideTyping();
                if (data.reply) {
                    addBotMessage(data.reply);
                    // Update history
                    conversationHistory.push({ role: 'user', text: text });
                    conversationHistory.push({ role: 'bot', text: data.reply });
                } else if (data.error) {
                    addBotMessage('Xin lỗi, tôi đang gặp sự cố kỹ thuật. Vui lòng thử lại sau hoặc liên hệ hotline <strong>0912.345.678</strong> 🙏');
                }
            })
            .catch(error => {
                console.error('Chatbot error:', error);
                hideTyping();
                addBotMessage('Xin lỗi, không thể kết nối đến server. Vui lòng thử lại sau hoặc liên hệ <strong>support@badmintonpro.vn</strong> 🙏');
            })
            .finally(() => {
                setWaiting(false);
                showQuickReplies();
            });
    }

    // --- Render Messages ---
    function addBotMessage(html) {
        const div = document.createElement('div');
        div.className = 'chat-message bot';
        div.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="msg-bubble">${html}</div>
        `;
        messagesContainer.appendChild(div);
        scrollToBottom();
    }

    function addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'chat-message user';
        div.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-user"></i></div>
            <div class="msg-bubble">${escapeHtml(text)}</div>
        `;
        messagesContainer.appendChild(div);
        scrollToBottom();
    }

    // --- Typing Indicator ---
    function showTyping() {
        const div = document.createElement('div');
        div.className = 'typing-indicator';
        div.id = 'typing-indicator';
        div.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        messagesContainer.appendChild(div);
        scrollToBottom();
    }

    function hideTyping() {
        const typing = document.getElementById('typing-indicator');
        if (typing) typing.remove();
    }

    // --- Quick Replies ---
    function renderQuickReplies() {
        quickRepliesContainer.innerHTML = '';
        quickReplies.forEach(qr => {
            const btn = document.createElement('button');
            btn.className = 'quick-reply-btn';
            btn.textContent = `${qr.icon} ${qr.text}`;
            btn.addEventListener('click', function () {
                inputField.value = qr.text;
                sendMessage();
            });
            quickRepliesContainer.appendChild(btn);
        });
    }

    function hideQuickReplies() {
        quickRepliesContainer.style.display = 'none';
    }

    function showQuickReplies() {
        quickRepliesContainer.style.display = 'flex';
    }

    // --- Utilities ---
    function scrollToBottom() {
        requestAnimationFrame(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        });
    }

    function setWaiting(val) {
        isWaiting = val;
        sendBtn.disabled = val;
        inputField.disabled = val;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        // Fallback: get from meta tag or hidden input
        if (!cookieValue) {
            const meta = document.querySelector('meta[name="csrf-token"]');
            if (meta) cookieValue = meta.getAttribute('content');
        }
        if (!cookieValue) {
            const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
            if (input) cookieValue = input.value;
        }
        return cookieValue;
    }

    // --- Start ---
    init();
});
