"""Phone number normalization for Meta WhatsApp Cloud API payloads."""

from __future__ import annotations

import re


def format_phone_number_for_meta(phone_number: str) -> str:
    """Return a phone number in the digit-only format accepted by Meta.

    Meta's Cloud API expects the country code and subscriber number without
    punctuation. Brazilian numbers occasionally arrive with an additional
    leading ``9`` after the area code. The known Meta normalization case is a
    13-digit Brazilian number whose local part starts with ``99``; remove only
    that duplicated leading digit and leave every other country untouched.
    """

    digits = re.sub(r"[^0-9]", "", phone_number)
    if not digits:
        raise ValueError("Phone number must contain at least one digit")

    digits = digits.removeprefix("00")
    if not digits:
        raise ValueError("Phone number must contain an international number")

    # Brazil: +55, two-digit area code, and a nine-digit local number that
    # starts with 99. In this case the first 9 is the extra digit described by
    # Meta's accepted-and-corrected behavior.
    if digits.startswith("55") and len(digits) == 13:
        local_number = digits[4:]
        if local_number.startswith("99"):
            digits = digits[:4] + local_number[1:]

    return digits
