import requests
from django.core.cache import cache


def get_bank():
    """
    Trả về danh sách Dictionary: 
    [{'id': 17, 'name': 'MB...', 'code': 'MB', 'bin': '970422', ...}, ...]
    """
    # Thử lấy từ cache
    data = cache.get('vietqr_banks_raw_data') 
    if data:
        return data

    #  Gọi API nếu chưa có cache 
    for attempt in range(2):
        try:
            response = requests.get(
                'https://api.vietqr.io/v2/banks',
                timeout=10,
                headers={'User-Agent': 'BadmintonPro/1.0'}
            )
            if response.status_code == 200:
                result = response.json()
                if result['code'] == '00':
                    raw_data = result['data']
                    # Lưu cache 24h
                    cache.set('vietqr_banks_raw_data', raw_data, 86400)
                    return raw_data
        except Exception as e:
            print(f"Error fetching banks (attempt {attempt + 1}): {e}")
    
    return []