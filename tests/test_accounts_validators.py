import pytest
from django.core.exceptions import ValidationError
from domains.accounts.validators import PasswordComplexityValidator


def test_password_complexity_validator_valid_passwords():
    """유효한 비밀번호들 테스트"""
    validator = PasswordComplexityValidator()
    
    valid_passwords = [
        "Password123!",
        "MyPass123@",
        "Test123#",
        "Valid123$",
        "Good123%",
        "Nice123^",
        "Cool123&",
        "Best123*",
        "Top123+=",
        "Win123==",
    ]
    
    for password in valid_passwords:
        # ValidationError가 발생하지 않아야 함
        try:
            validator.validate(password)
        except ValidationError:
            pytest.fail(f"Valid password '{password}' should not raise ValidationError")


def test_password_complexity_validator_invalid_length():
    """비밀번호 길이 검증 테스트"""
    validator = PasswordComplexityValidator()
    
    # 너무 짧은 비밀번호
    short_passwords = ["Pass1!", "Test2@", "Abc3#"]
    for password in short_passwords:
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(password)
        assert exc_info.value.code == "password_length"
    
    # 너무 긴 비밀번호
    long_passwords = ["VeryLongPassword123!", "ThisIsTooLongPassword123@", "SuperLongPassword123#"]
    for password in long_passwords:
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(password)
        assert exc_info.value.code == "password_length"


def test_password_complexity_validator_missing_components():
    """비밀번호 구성 요소 누락 테스트"""
    validator = PasswordComplexityValidator()
    
    # 대문자 누락
    with pytest.raises(ValidationError) as exc_info:
        validator.validate("password123!")
    assert exc_info.value.code == "password_no_upper"
    
    # 소문자 누락
    with pytest.raises(ValidationError) as exc_info:
        validator.validate("PASSWORD123!")
    assert exc_info.value.code == "password_no_lower"
    
    # 숫자 누락
    with pytest.raises(ValidationError) as exc_info:
        validator.validate("Password!")
    assert exc_info.value.code == "password_no_digit"
    
    # 특수문자 누락
    with pytest.raises(ValidationError) as exc_info:
        validator.validate("Password123")
    assert exc_info.value.code == "password_no_special"


def test_password_complexity_validator_whitespace():
    """비밀번호 공백 포함 테스트"""
    validator = PasswordComplexityValidator()
    
    passwords_with_spaces = [
        "Password 123!",
        "Pass word123!",
        "Password123 !",
        " Password123!",
        "Password123! ",
    ]
    
    for password in passwords_with_spaces:
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(password)
        assert exc_info.value.code == "password_has_spaces"


def test_password_complexity_validator_help_text():
    """도움말 텍스트 테스트"""
    validator = PasswordComplexityValidator()
    help_text = validator.get_help_text()
    
    assert isinstance(help_text, str)
    assert len(help_text) > 0
    assert "8~16자" in help_text
    assert "대/소문자" in help_text
    assert "숫자" in help_text
    assert "특수문자" in help_text
    assert "공백" in help_text
