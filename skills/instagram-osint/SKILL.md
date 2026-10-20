---
name: instagram-osint
description: Primary goal is to execute unauthenticated Instagram profile inspection, construct zero-login mirror links (Picuki, Imginn, Dumpor), generate search index dorks, and prepare Instaloader commands for any provided handle.
---

# Zero-Login Instagram OSINT

Automated execution skill to inspect public Instagram profiles and run public search indexing without hitting login walls or maintaining an Instagram account.

## Execution Goal

Whenever an Instagram handle or username is provided:
1. **Execute Profile Inspector Script**:
   ```bash
   python3 skills/instagram-osint/scripts/ig_profile_inspector.py <USERNAME>
   ```
2. **Execute Public Search Index Checks**:
   - Query search engines:
     - `site:instagram.com inurl:<USERNAME>`
     - `site:instagram.com "@<USERNAME>"`
     - `"<USERNAME>" (site:twitter.com OR site:linkedin.com)`
3. **Dispatch Zero-Login Web Mirrors**:
   - Provide direct links to Picuki, Imginn, Dumpor, and StoriesIG for immediate anonymous browsing.
4. **Instaloader Command**:
   - Provide `instaloader --no-login --no-posts <USERNAME>` for CLI post/avatar extraction.
