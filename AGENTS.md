# Workspace Guidelines & Autonomous Multi-Agent OSINT Protocol

## Automatic Fan-Out OSINT Execution Protocol

Whenever the user provides any target indicator (a phone number, email address, username/handle, real name, or Indian vehicle registration plate):

**DO NOT ask for confirmation, clarification, or permission to proceed. Immediately and autonomously fan out tasks to gather all intelligence in parallel:**

### 1. Autonomous Execution & Subagent Fan-Out
- **Script & Technical Resolution**:
  - Immediately run the unified scanner:
    ```bash
    python3 skills/osint_scanner.py "<TARGET>"
    ```
- **Parallel Deep Research & Public Indexing**:
  - Fan out research tasks (via `invoke_subagent` or direct search tools) across public search indexes to probe the auto-generated dorks:
    - Public pastebins, documents (PDF/XLSX), commercial directories (IndiaMART, Justdial).
    - Social media platforms (Instagram, LinkedIn, X/Twitter, GitHub).
    - Indian official registries (Parivahan, eChallan, MCA/ZaubaCorp, eCourts).
- **Unauthenticated Metadata Verification**:
  - For phone numbers: Run live WhatsApp zero-login OpenGraph probe and derive deterministic UPI VPAs (PhonePe, Google Pay, Paytm, BHIM, Amazon Pay) for KYC beneficiary name validation.
  - For vehicle plates: Parse RTO district and state jurisdiction.
  - For emails: Validate DNS MX records and query for public exposures.
  - For usernames: Construct zero-login Instagram mirrors (Picuki, Imginn) and Sherlock commands.

### 2. Output Standard: Consolidated Intelligence Dossier
Present the complete, comprehensive intelligence report in a single response, structured as:
1. **Target Identification & Technical Resolution** (Normalized format, carrier/domain/RTO jurisdiction).
2. **Platform & Financial/Identity Presence** (WhatsApp registration status, deterministic UPI VPAs, active social accounts, web mirrors).
3. **Deep Public Search Indexing Findings**:
   - **Professional & Academic Records** (Employment trajectory, university degrees, research projects, committee roles).
   - **Indexed Comments & Discussion Snippets** (Extracted quotes, community discussions, forum participation).
   - **Tagged Posts & Reels** (Posts/reels where the target was tagged, co-authored, or credited with `pc: @...`).
   - **Tagged Accounts & Collaborators** (Co-tagged creators, brands, venues, and clustered sub-accounts).
   - **Public Documents, Leaks & Directories** (Findings across commercial directories, MCA/ZaubaCorp, or public lists).
4. **Direct Verification Links & Action Items** (UPI payment verification, eChallan, Parivahan, archive snapshots, or direct links).
