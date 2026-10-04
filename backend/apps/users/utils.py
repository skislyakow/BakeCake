import re

_DIGITS_RE = re.compile(r"\D")


def normalize_phone(value):
    if not value:
        return ""
    raw = str(value).strip()
    digits = _DIGITS_RE.sub("", raw)
    if len(digits) == 10 and digits[:1] == "9":
        digits = "7" + digits
    if len(digits) == 11 and digits[:1] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[:1] == "7":
        return "+" + digits
    return raw