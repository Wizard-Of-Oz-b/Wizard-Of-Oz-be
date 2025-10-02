"""
domains/accounts/utils.py 테스트
"""

import pytest

from domains.accounts.utils import refresh_cookie_kwargs


def test_refresh_cookie_kwargs_debug_false():
    """debug=False일 때 쿠키 설정 테스트"""
    kwargs = refresh_cookie_kwargs(debug=False)

    assert kwargs["httponly"] == True
    assert kwargs["secure"] == True  # debug=False이므로 secure=True
    assert kwargs["samesite"] == "Lax"
    assert kwargs["path"] == "/api/v1/auth/"
    assert kwargs["max_age"] == 14 * 24 * 3600  # 14일


def test_refresh_cookie_kwargs_debug_true():
    """debug=True일 때 쿠키 설정 테스트"""
    kwargs = refresh_cookie_kwargs(debug=True)

    assert kwargs["httponly"] == True
    assert kwargs["secure"] == False  # debug=True이므로 secure=False
    assert kwargs["samesite"] == "Lax"
    assert kwargs["path"] == "/api/v1/auth/"
    assert kwargs["max_age"] == 14 * 24 * 3600  # 14일


def test_refresh_cookie_kwargs_default():
    """기본값(debug=False)으로 호출할 때 테스트"""
    kwargs = refresh_cookie_kwargs()

    assert kwargs["httponly"] == True
    assert kwargs["secure"] == True  # 기본값은 debug=False
    assert kwargs["samesite"] == "Lax"
    assert kwargs["path"] == "/api/v1/auth/"
    assert kwargs["max_age"] == 14 * 24 * 3600
