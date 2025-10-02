# domains/accounts/validators.py
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordComplexityValidator:
    """
    8~16자이며, 대문자/소문자/숫자/특수문자(공백 제외) 각각 1개 이상 포함
    특수문자: 영숫자/언더스코어를 제외한 모든 문장부호를 허용 (공백은 허용하지 않음)
    """

    UPPER = re.compile(r"[A-Z]")
    LOWER = re.compile(r"[a-z]")
    DIGIT = re.compile(r"[0-9]")
    SPECIAL = re.compile(
        r"[^\w\s]"
    )  # \w = [A-Za-z0-9_], \s = 공백류 → 공백 제외한 특수문자만 매칭

    def validate(self, password: str, user=None):
        if not 8 <= len(password) <= 16:
            raise ValidationError(
                _("비밀번호는 8~16자여야 합니다."), code="password_length"
            )
        if not self.UPPER.search(password):
            raise ValidationError(
                _("비밀번호에 대문자가 최소 1개 포함되어야 합니다."),
                code="password_no_upper",
            )
        if not self.LOWER.search(password):
            raise ValidationError(
                _("비밀번호에 소문자가 최소 1개 포함되어야 합니다."),
                code="password_no_lower",
            )
        if not self.DIGIT.search(password):
            raise ValidationError(
                _("비밀번호에 숫자가 최소 1개 포함되어야 합니다."),
                code="password_no_digit",
            )
        if not self.SPECIAL.search(password):
            raise ValidationError(
                _("비밀번호에 특수문자가 최소 1개 포함되어야 합니다."),
                code="password_no_special",
            )
        if re.search(r"\s", password):
            raise ValidationError(
                _("비밀번호에 공백을 포함할 수 없습니다."), code="password_has_spaces"
            )

    def get_help_text(self):
        return _(
            "비밀번호는 8~16자이며 대/소문자, 숫자, 특수문자를 각각 최소 1자 이상 포함해야 하며 공백은 허용되지 않습니다."
        )
