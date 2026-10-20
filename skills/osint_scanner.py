#!/usr/bin/env python3
"""
PraLabs Unified OSINT Scanner & Public Indexing Orchestrator
Zero-Login, Multi-Vector Intelligence Engine for India & Global Platforms.
Accepts: Phone Number, Email Address, Username / Handle, Real Name, or Vehicle Plate.
"""

import argparse
import json
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

# --- 1. TELECOM & PHONE MODULE (+91) ---
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

    # Determine series allocation
    prefix_2 = digits[:2]
    carrier = "Unknown / Private Telco"
    if prefix_2 in ("94", "93"):
        carrier = "BSNL / MTNL"
    elif prefix_2 in ("98", "99", "97", "96", "70", "80"):
        carrier = "Airtel / Vodafone-Idea (Vi)"
    elif prefix_2 in ("62", "63", "79", "89", "78"):
        carrier = "Reliance Jio / Private"

    # Common deterministic UPI VPA handles (PhonePe, Google Pay, Paytm, BHIM, Amazon Pay)
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

    # WhatsApp unauthenticated metadata check
    wa_data = inspect_whatsapp(digits)

    dorks = [
        f'"{formatted_e164}" OR "{digits}" OR "{formatted_national}"',
        f'"{digits}" filetype:pdf OR filetype:xlsx OR filetype:docx',
        f'site:justdial.com "{digits}"',
        f'site:indiamart.com "{digits}"',
        f'site:facebook.com "{digits}" OR "{formatted_e164}"',
        f'site:linkedin.com "{digits}"',
        f'site:instagram.com "{digits}"',
        f'site:twitter.com "{digits}" OR site:x.com "{digits}"',
    ]

    return {
        "type": "phone",
        "valid": True,
        "national_number": digits,
        "e164": formatted_e164,
        "carrier_estimation": carrier,
        "whatsapp": wa_data,
        "upi_vpas": upi_handles,
        "search_dorks": dorks,
    }


def inspect_whatsapp(digits: str) -> dict:
    url = f"https://api.whatsapp.com/send/?phone=91{digits}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    result = {
        "registered": False,
        "account_type": "None",
        "public_name": None,
        "wa_link": f"https://wa.me/91{digits}",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            if "Phone number shared via url is invalid" in html:
                result["registered"] = False
                return result

            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if title_match:
                title = title_match.group(1).strip()
                if title and title != "Share on WhatsApp":
                    result["registered"] = True
                    result["public_name"] = title

            desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
            if desc_match:
                desc = desc_match.group(1).strip()
                result["account_type"] = desc
                if not result["registered"] and desc:
                    result["registered"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


# --- 2. EMAIL OSINT MODULE ---
def analyze_email(email: str) -> dict:
    cleaned = email.strip().lower()
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", cleaned):
        return {"valid": False, "raw": email, "error": "Invalid email address format"}

    username, domain = cleaned.split("@", 1)

    # Check MX records for domain
    mx_records = []
    try:
        import subprocess
        res = subprocess.run(["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=5)
        mx_records = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
    except Exception:
        pass

    dorks = [
        f'"{cleaned}"',
        f'"{cleaned}" filetype:pdf OR filetype:xlsx OR filetype:txt',
        f'site:github.com "{cleaned}"',
        f'site:pastebin.com "{cleaned}"',
        f'site:linkedin.com "{cleaned}"',
        f'site:twitter.com "{cleaned}" OR site:x.com "{cleaned}"',
        f'"{username}" site:{domain}',
    ]

    return {
        "type": "email",
        "valid": True,
        "email": cleaned,
        "username": username,
        "domain": domain,
        "mx_records": mx_records,
        "search_dorks": dorks,
        "disposable_hint": domain in ("tempmail.com", "mailinator.com", "guerrillamail.com", "10minutemail.com"),
    }


# --- 3. USERNAME & HANDLE OSINT MODULE ---
def analyze_username(username: str) -> dict:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", username.lstrip("@"))

    # Direct profile URLs on key networks
    direct_profiles = {
        "GitHub": f"https://github.com/{cleaned}",
        "Twitter_X": f"https://x.com/{cleaned}",
        "Instagram": f"https://www.instagram.com/{cleaned}/",
        "Reddit": f"https://www.reddit.com/user/{cleaned}",
        "Telegram": f"https://t.me/{cleaned}",
        "Pinterest": f"https://www.pinterest.com/{cleaned}/",
        "Medium": f"https://medium.com/@{cleaned}",
        "YouTube": f"https://www.youtube.com/@{cleaned}",
    }

    # Zero-login Instagram web mirrors
    ig_mirrors = {
        "picuki": f"https://www.picuki.com/profile/{cleaned}",
        "imginn": f"https://imginn.com/{cleaned}/",
        "dumpor": f"https://dumpoir.com/v/{cleaned}",
        "storiesig": f"https://storiesig.info/en/{cleaned}/",
    }

    # Deep interaction and public indexing dorks (Comments, Tagged posts, Collaborators)
    interaction_dorks = [
        f'site:instagram.com/p/ "@{cleaned}"',
        f'site:instagram.com/reel/ "@{cleaned}"',
        f'site:instagram.com "with @{cleaned}" OR "pc: @{cleaned}" OR "cr: @{cleaned}"',
        f'site:instagram.com/p/ "{cleaned}"',
        f'site:instagram.com/reel/ "{cleaned}"',
        f'site:reddit.com/user "{cleaned}" OR site:reddit.com "{cleaned}"',
    ]

    dorks = [
        f'"{cleaned}" (site:github.com OR site:twitter.com OR site:x.com OR site:linkedin.com)',
        f'site:instagram.com inurl:{cleaned}',
        f'site:t.me "{cleaned}"',
        f'"{cleaned}" filetype:pdf OR filetype:txt',
    ] + interaction_dorks

    return {
        "type": "username",
        "valid": True,
        "username": cleaned,
        "direct_profiles": direct_profiles,
        "instagram_mirrors": ig_mirrors,
        "sherlock_command": f"sherlock {cleaned} --print-found --timeout 10",
        "whatsmyname_url": f"https://whatsmyname.app/?q={cleaned}",
        "search_dorks": dorks,
        "interaction_dorks": interaction_dorks,
    }


# --- 4. REAL NAME OSINT MODULE ---
def analyze_name(name: str, location_hint: str = "India") -> dict:
    cleaned = " ".join(name.strip().split())
    tokens = cleaned.split()

    dorks = [
        f'"{cleaned}" "{location_hint}"',
        f'"{cleaned}" site:linkedin.com/in/',
        f'"{cleaned}" site:facebook.com',
        f'"{cleaned}" site:instagram.com',
        f'"{cleaned}" site:twitter.com OR site:x.com',
        f'"{cleaned}" site:github.com',
        f'"{cleaned}" (filetype:pdf OR filetype:xlsx) "{location_hint}"',
        f'site:zaubacorp.com/company/ "{cleaned}" OR site:tofler.in "{cleaned}"',
        f'site:ecourts.gov.in "{cleaned}"',
    ]

    return {
        "type": "name",
        "valid": True,
        "target_name": cleaned,
        "location_context": location_hint,
        "search_dorks": dorks,
    }


# --- 5. VEHICLE REGISTRATION (INDIA RTO) MODULE ---
STATE_CODES = {
    "AN": "Andaman and Nicobar Islands", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh",
    "AS": "Assam", "BR": "Bihar", "CH": "Chandigarh", "CG": "Chhattisgarh",
    "DN": "Dadra and Nagar Haveli", "DD": "Daman and Diu", "DL": "Delhi", "GA": "Goa",
    "GJ": "Gujarat", "HR": "Haryana", "HP": "Himachal Pradesh", "JK": "Jammu and Kashmir",
    "JH": "Jharkhand", "KA": "Karnataka", "KL": "Kerala", "LA": "Ladakh",
    "LD": "Lakshadweep", "MP": "Madhya Pradesh", "MH": "Maharashtra", "MN": "Manipur",
    "ML": "Meghalaya", "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha",
    "PY": "Puducherry", "PB": "Punjab", "RJ": "Rajasthan", "SK": "Sikkim",
    "TN": "Tamil Nadu", "TS": "Telangana", "TR": "Tripura", "UP": "Uttar Pradesh",
    "UK": "Uttarakhand", "WB": "West Bengal"
}
PLATE_REGEX = re.compile(r"^([A-Z]{2})([0-9]{1,2})([A-Z]{0,3})([0-9]{4})$")


def analyze_plate(raw_plate: str) -> dict:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_plate.upper())
    match = PLATE_REGEX.match(cleaned)
    if not match:
        return {"valid": False, "raw": raw_plate, "error": "Invalid Indian plate format"}

    state_code, rto_code, series, number = match.groups()
    state_name = STATE_CODES.get(state_code, "Unknown / Central Government")

    return {
        "type": "vehicle_plate",
        "valid": True,
        "normalized": f"{state_code}{rto_code.zfill(2)}{series}{number}",
        "state_code": state_code,
        "state_name": state_name,
        "rto_code": rto_code.zfill(2),
        "series": series,
        "number": number,
        "parivahan_url": "https://parivahan.gov.in/rcdlstatus/",
        "echallan_url": "https://echallan.parivahan.gov.in/index/accused-challan",
        "search_dorks": [
            f'"{cleaned}" echallan OR parivahan',
            f'"{state_code}{rto_code.zfill(2)} {series} {number}"',
        ],
    }


# --- AUTO-DISPATCHER ---
def auto_detect_and_scan(target: str, location_hint: str = "India") -> dict:
    target = target.strip()
    digits = re.sub(r"[^0-9]", "", target)

    # Check if Email
    if "@" in target and "." in target:
        return analyze_email(target)

    # Check if Phone (10 digits starting with 6-9, or +91 format)
    if (len(digits) == 10 and digits[0] in VALID_PREFIXES) or (len(digits) == 12 and digits.startswith("91")):
        return analyze_phone(target)

    # Check if Indian License Plate
    cleaned_alphanum = re.sub(r"[^A-Za-z0-9]", "", target.upper())
    if PLATE_REGEX.match(cleaned_alphanum):
        return analyze_plate(cleaned_alphanum)

    # Check if Multi-word (Name)
    if " " in target:
        return analyze_name(target, location_hint)

    # Default to Username
    return analyze_username(target)


def main():
    parser = argparse.ArgumentParser(description="PraLabs Unified OSINT Scanner & Public Indexing Orchestrator")
    parser.add_argument("target", help="Target indicator: Phone, Email, Username, Real Name, or Vehicle Plate")
    parser.add_argument("--type", choices=["phone", "email", "username", "name", "plate", "auto"], default="auto",
                        help="Explicit target type (default: auto-detect)")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--location", default="India", help="Location context for real names (default: India)")

    args = parser.parse_args()

    if args.type == "phone":
        res = analyze_phone(args.target)
    elif args.type == "email":
        res = analyze_email(args.target)
    elif args.type == "username":
        res = analyze_username(args.target)
    elif args.type == "name":
        res = analyze_name(args.target, args.location)
    elif args.type == "plate":
        res = analyze_plate(args.target)
    else:
        res = auto_detect_and_scan(args.target, args.location)

    if args.json:
        print(json.dumps(res, indent=2))
        return

    # Print Clean Text / Markdown Output
    print("=" * 60)
    print(f"PraLabs OSINT Triage Report: {args.target}")
    print(f"Detected Target Type: {res.get('type', 'Unknown').upper()}")
    print("=" * 60)

    for k, v in res.items():
        if k in ("search_dorks", "direct_profiles", "instagram_mirrors"):
            print(f"\n[{k.replace('_', ' ').title()}]:")
            if isinstance(v, list):
                for item in v:
                    print(f"  • {item}")
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    print(f"  • {sub_k}: {sub_v}")
        elif isinstance(v, dict):
            print(f"\n[{k.replace('_', ' ').title()}]:")
            for sub_k, sub_v in v.items():
                print(f"  - {sub_k}: {sub_v}")
        else:
            print(f"{k.replace('_', ' ').title()}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
