#!/usr/bin/env python3
"""
RTO Plate Normalizer & District Identifier (India)
Part of PraLabs OSINT Skills collection.
"""

import re
import sys

STATE_CODES = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chhattisgarh",
    "DN": "Dadra and Nagar Haveli",
    "DD": "Daman and Diu",
    "DL": "Delhi",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JK": "Jammu and Kashmir",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PY": "Puducherry",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "WB": "West Bengal",
}

PLATE_REGEX = re.compile(r"^([A-Z]{2})([0-9]{1,2})([A-Z]{0,3})([0-9]{4})$")


def parse_plate(raw_plate: str) -> dict:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_plate.upper())
    match = PLATE_REGEX.match(cleaned)
    if not match:
        return {"valid": False, "raw": raw_plate, "error": "Invalid Indian plate format"}

    state_code, rto_code, series, number = match.groups()
    state_name = STATE_CODES.get(state_code, "Unknown / Central Government")

    return {
        "valid": True,
        "normalized": f"{state_code}{rto_code.zfill(2)}{series}{number}",
        "state_code": state_code,
        "state_name": state_name,
        "rto_code": rto_code.zfill(2),
        "series": series,
        "number": number,
        "parivahan_url": "https://parivahan.gov.in/rcdlstatus/",
        "echallan_url": "https://echallan.parivahan.gov.in/index/accused-challan",
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 rto_lookup.py <VEHICLE_NUMBER>")
        sys.exit(1)

    plate = sys.argv[1]
    res = parse_plate(plate)
    for k, v in res.items():
        print(f"{k}: {v}")
