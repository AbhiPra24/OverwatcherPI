#!/usr/bin/env python3
"""
Indian Phone Number Analyzer & Dork Generator
Part of PraLabs OSINT Skills collection.
"""

import re
import sys

# Common initial digit allocations in India (6, 7, 8, 9 are valid GSM/VoLTE prefixes)
VALID_PREFIXES = ("6", "7", "8", "9")


def analyze_phone(raw: str) -> dict:
    digits = re.sub(r"[^0-9]", "", raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) != 10 or not digits.startswith(VALID_PREFIXES):
        return {
            "valid": False,
            "raw": raw,
            "error": "Not a valid 10-digit Indian mobile number",
        }

    formatted_e164 = f"+91{digits}"
    formatted_national = f"0{digits}"

    # Standard search dorks
    dorks = [
        f'"{formatted_e164}" OR "{digits}" OR "{formatted_national}"',
        f'"{digits}" filetype:pdf OR filetype:xlsx OR filetype:docx',
        f'site:justdial.com "{digits}"',
        f'site:indiamart.com "{digits}"',
        f'site:facebook.com "{digits}" OR "{formatted_e164}"',
        f'site:linkedin.com "{digits}"',
    ]

    # Common deterministic UPI VPA handles
    upi_handles = [
        f"{digits}@paytm",
        f"{digits}@ybl",
        f"{digits}@ibl",
        f"{digits}@axl",
        f"{digits}@okhdfcbank",
        f"{digits}@okaxis",
        f"{digits}@oksbi",
        f"{digits}@okicici",
        f"{digits}@apl",
        f"{digits}@upi",
    ]

    return {
        "valid": True,
        "national_number": digits,
        "e164": formatted_e164,
        "lead_digit": digits[0],
        "whatsapp_url": f"https://wa.me/91{digits}",
        "upi_vpas": upi_handles,
        "search_dorks": dorks,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 phone_analyzer.py <PHONE_NUMBER>")
        sys.exit(1)

    res = analyze_phone(sys.argv[1])
    for k, v in res.items():
        if isinstance(v, list):
            print(f"{k}:")
            for item in v:
                print(f"  - {item}")
        else:
            print(f"{k}: {v}")
