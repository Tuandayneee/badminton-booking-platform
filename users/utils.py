import logging

from django.core.cache import cache
import requests

logger = logging.getLogger(__name__)


def get_bank():
    """
    Trả về danh sách ngân hàng từ VietQR API (cache 24h).
    """
    try:
        data = cache.get('vietqr_banks_raw_data')
        if data:
            return data
    except Exception as exc:
        logger.warning("Cache read error in get_bank: %s", exc)

    for attempt in range(2):
        try:
            response = requests.get(
                'https://api.vietqr.io/v2/banks',
                timeout=10,
                headers={'User-Agent': 'BadmintonPro/1.0'},
            )
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == '00':
                    raw_data = result.get('data', [])
                    try:
                        cache.set('vietqr_banks_raw_data', raw_data, 86400)
                    except Exception as exc:
                        logger.warning("Cache write error in get_bank: %s", exc)
                    return raw_data
        except requests.RequestException as exc:
            logger.warning("Error fetching VietQR banks (attempt %d): %s", attempt + 1, exc)

    return []
