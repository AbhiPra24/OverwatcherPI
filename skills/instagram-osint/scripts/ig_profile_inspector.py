#!/usr/bin/env python3
"""
Zero-Login Instagram Profile Inspector & Mirror Linker
Generates direct unauthenticated mirror links and dorks for public Instagram accounts.
Part of PraLabs OSINT Skills collection.
"""

import sys
import re


def generate_zero_login_links(username: str) -> dict:
    cleaned = re.sub(r"[^A-Za-z0-9._]", "", username.lstrip("@"))

    return {
        "username": cleaned,
        "official_url": f"https://www.instagram.com/{cleaned}/",
        "zero_login_mirrors": {
            "picuki": f"https://www.picuki.com/profile/{cleaned}",
            "imginn": f"https://imginn.com/{cleaned}/",
            "dumpor": f"https://dumpoir.com/v/{cleaned}",
            "storiesig": f"https://storiesig.info/en/{cleaned}/",
        },
        "archive_url": f"https://web.archive.org/web/*/https://www.instagram.com/{cleaned}/",
        "search_dorks": [
            f'site:instagram.com inurl:{cleaned}',
            f'site:instagram.com "@{cleaned}"',
            f'site:instagram.com/p/ "@{cleaned}"',
            f'site:instagram.com/reel/ "@{cleaned}"',
            f'site:instagram.com "with @{cleaned}" OR "pc: @{cleaned}" OR "cr: @{cleaned}"',
            f'site:instagram.com/p/ "{cleaned}"',
            f'site:instagram.com/reel/ "{cleaned}"',
            f'"{cleaned}" (site:twitter.com OR site:linkedin.com OR site:github.com)',
        ],
        "instaloader_cmd": f"instaloader --no-login --no-posts {cleaned}",
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ig_profile_inspector.py <USERNAME>")
        sys.exit(1)

    res = generate_zero_login_links(sys.argv[1])
    print(f"Target: @{res['username']}")
    print(f"Instaloader Command: {res['instaloader_cmd']}")
    print("\nZero-Login Mirrors:")
    for name, url in res["zero_login_mirrors"].items():
        print(f"  [{name}]: {url}")
    print("\nHistoric Archive:")
    print(f"  {res['archive_url']}")
    print("\nSearch Dorks:")
    for d in res["search_dorks"]:
        print(f"  - {d}")
