 document.addEventListener("DOMContentLoaded", function() {
        const ctx = document.getElementById('revenueChart').getContext('2d');
        new Chart(ctx, {
            type: 'line', 
            data: {
                labels: ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'], // Trục hoành
                datasets: [{
                    label: 'Doanh thu (VNĐ)',
                    data: [1500000, 2100000, 1800000, 2400000, 3000000, 4500000, 5200000], // Dữ liệu giả lập
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4 
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false } 
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    });