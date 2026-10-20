#!/usr/bin/env python3
"""
Zero-Login WhatsApp Profile & Metadata Inspector
Extracts public OpenGraph metadata (Name, Account Type, Status) with NO authentication.
Part of PraLabs OSINT Skills collection.
"""

import re
import sys
import urllib.request
import urllib.error


def inspect_whatsapp(raw_number: str) -> dict:
    digits = re.sub(r"[^0-9]", "", raw_number)
    # Default to India (+91) if 10 digits provided
    if len(digits) == 10:
        digits = f"91{digits}"
    elif digits.startswith("0") and len(digits) == 11:
        digits = f"91{digits[1:]}"

    url = f"https://api.whatsapp.com/send/?phone={digits}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    result = {
        "phone_number": digits,
        "direct_url": url,
        "wa_me_link": f"https://wa.me/{digits}",
        "registered": False,
        "public_name": None,
        "account_type": None,
        "error": None,
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

            # Check if number is flagged as invalid/not on whatsapp
            if "Phone number shared via url is invalid" in html:
                result["registered"] = False
                result["error"] = "Number not registered on WhatsApp or invalid"
                return result

            # Extract og:title (Usually public profile name or business name)
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if title_match:
                title = title_match.group(1).strip()
                if title and title != "Share on WhatsApp":
                    result["registered"] = True
                    result["public_name"] = title

            # Extract og:description (e.g. "Business Account", or custom status)
            desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
            if desc_match:
                desc = desc_match.group(1).strip()
                result["account_type"] = desc
                if not result["registered"] and desc:
                    result["registered"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 wa_link_generator.py <PHONE_NUMBER>")
        print("Example: python3 wa_link_generator.py 9876543210")
        sys.exit(1)

    target_num = sys.argv[1]
    res = inspect_whatsapp(target_num)
    for k, v in res.items():
        print(f"{k}: {v}")
