# domains/accounts/utils.py
def refresh_cookie_kwargs(debug: bool = False) -> dict:
    return dict(
        httponly=True,
        secure=not debug,
        samesite="Lax",
        path="/api/v1/auth/",
        max_age=14 * 24 * 3600,
    )
