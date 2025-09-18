# domains/orders/utils.py
from urllib.parse import parse_qsl

def parse_option_key_safe(option_key: str) -> dict[str, str]:
    """
    'size=L&color=red' -> {'size': 'L', 'color': 'red'}
    - 빈 값 허용
    - 잘못된 토큰은 무시
    """
    if not option_key:
        return {}
    try:
        # 예외 던지지 않도록 완화
        return dict(parse_qsl(option_key, keep_blank_values=True, strict_parsing=False))
    except Exception:
        # 최후 보루: '=' 없는 조각은 버리고 '=' 있는 것만 받기
        pairs = [p.split('=', 1) for p in str(option_key).split('&') if '=' in p]
        return {k: v for k, v in pairs}
