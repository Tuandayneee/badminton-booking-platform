import requests
from django.core.cache import cache


def get_bank():
    """
    Trả về danh sách Dictionary đầy đủ: 
    [{'id': 17, 'name': 'MB...', 'code': 'MB', 'bin': '970422', ...}, ...]
    """
    # 1. Thử lấy từ cache
    data = cache.get('vietqr_banks_raw_data') 
    if data:
        return data

    # 2. Gọi API nếu chưa có cache
    try:
        response = requests.get('https://api.vietqr.io/v2/banks')
        if response.status_code == 200:
            result = response.json()
            if result['code'] == '00':
                raw_data = result['data']
                # Lưu cache 24h
                cache.set('vietqr_banks_raw_data', raw_data, 86400)
                return raw_data
    except Exception as e:
        print(f"Error fetching banks: {e}")
        pass
    
    return []