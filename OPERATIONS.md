# OPERATIONS

Everything that runs, how it fails safely, what to watch, and the keys a human can turn later.

## Automated jobs

### `deploy.yml`: daily scoreboard (09:23 UTC; also on code pushes and by hand)
1. **Tests** (synthetic fixtures, no network).
2. **Fetch:** `python -m scoreboard.sources work`.
   - Downloads weio-ops `offerings.csv.gz` and verifies its SHA-256 against the dataset's `manifest.json`.
   - Downloads the XOOMAR CSV and verifies it against the Hugging Face LFS SHA-256.
   - Normalises both, cross-checks every overlapping filing since 2025 (amount sold, offering amount, state, industry, CIK) and merges them.
   - If `EDGAR_CONTACT_EMAIL` is set, also reads EDGAR's daily form index and each new filing's `primary_doc.xml` for days after the mirrors' last day, at 5 requests per second or fewer, with that email in the User-Agent.
3. **Guard:** `scripts/guard_data.py` against the live `/data/source.json`. It refuses if:
   - the rows fall by more than 2%;
   - the complete-through date goes backwards;
   - the mirrors overlap on fewer than 1,000 filings;
   - the mirrors agree on less than 99.5%.

   On scheduled runs it skips the build when the data checksums, the complete-through date and the code commit all match the live build.
4. **Build** (`scoreboard/site.py`, about 20,000 pages), share images (`scripts/og.py`, default card on failure), Pages deploy.
5. **IndexNow** (`scripts/indexnow.py`): priority URLs plus a daily rotating slice, up to 10,000. Never fails the run.
6. **Keep-alive** (scheduled runs): see `keepalive.yml`.

**Fails safe:**
- A download, checksum, guard, test or build failure stops the job before deploying, and Pages keeps the last good build.
- GitHub emails the repository owner on failure.

### `selftest.yml`: weekly (Wednesdays 05:47 UTC, or by hand)
- Tests on `main`.
- `scripts/health.py`:
  - 13 key URLs answer;
  - data is complete through no more than 6 days ago;
  - the mirrors agree at 99.5% or more;
  - the box score of this week's top raise resolves.
- Then keep-alive.

### `keepalive.yml`: called by every scheduled workflow
- Re-enables every workflow through the API.
- Pushes a `.github/heartbeat` commit if the repository has been quiet for 40+ days. GitHub disables schedules after 60 days without activity, and this repo commits no data, so the heartbeat is what keeps it active.

### `ci.yml`: tests on every push and pull request (Python 3.9 and 3.12).

## What to watch

| Signal | Where | Healthy |
|---|---|---|
| Daily runs | Actions tab; failure emails | Green; most days deploy |
| Freshness | `/data/source.json` (`complete_through`, `fetched`) and the site footer | Within one business day of today |
| Mirror agreement | `/data/source.json` (`cross_check.agreement`, `examples`) | 100% (the guard trips below 99.5%) |
| Source health | `weio.as_of` advancing weekly; `xoomar.latest_filing` advancing daily | If a mirror stops updating, see the playbook below |
| Reach | Bing indexing; GoatCounter once the key is set (`boxscore_open`, `share`, `embed_copy`, `game_over`) | Growing |

## Keys Jack can turn later

| Key | Why | Exact steps |
|---|---|---|
| **EDGAR contact email** | Same-day data straight from the SEC, and no dependence on third-party mirrors. EDGAR refuses automated clients without an email in the User-Agent (verified 2026-10-25) | Choose a real, monitored mailbox (not a personal address). Set the repository variable `EDGAR_CONTACT_EMAIL` to it (Settings, then Secrets and variables, then Actions, then Variables), then run `gh workflow run deploy.yml`. `/data/source.json` → `edgar` then reads "on: N filings after <date>". The client stays at 5 requests per second or fewer |
| **Custom domain** | Brand, a root robots.txt, trust | LAUNCH.md §5 (silicontank.com is owned) |
| **Money: sponsor slot** | First revenue | GitHub Pages is non-commercial, so host the paid placement off Pages (for example Cloudflare Pages on the custom domain). Then set `SB_SPONSOR_URL` to the sponsor's page and redeploy: a "Sponsored" box appears in the footer, marked as such. Optional display ads need an ad-network account and the same off-Pages hosting |
| **Analytics** | Measure `boxscore_open` and shares | Create a GoatCounter site, set `SB_GOATCOUNTER=https://<code>.goatcounter.com/count` and redeploy. It is cookieless and honours DNT and GPC |
| **Google Search Console** | Google does not use IndexNow | Verify the custom domain (DNS TXT record), then submit `/sitemap.xml` |
| **Alerts product** | "Raises in my league and state, daily" by email | Needs a mail provider account and a privacy policy; not built |

## Scheduled Claude routine (optional)

No AI-written content is required: every recap sentence is computed from the data. If someone wants a monthly review, schedule a Claude Code routine in this repo with this prompt:

> In ~/code/espn-of-venture (git pull):
> 1. Check `/data/source.json` on the live site for freshness and agreement, and the last 4 runs of `deploy.yml`.
> 2. Review open issues labelled `correction`. Fix code-level problems (for example a name-casing rule in `scoreboard/model.py`), never edit SEC figures, and close each issue with the filing link.
> 3. Spot-check the week's top 5 raises against their sec.gov filings in a browser.
> 4. Run the tests, commit and push. Do not post anywhere.

## Failure playbook

- **Checksum mismatch or download failure:** usually a mirror mid-publish. The next daily run retries automatically.
- **Guard refused (agreement fell):** look at `cross_check.examples` in the failed run's `work/source.json` log output. If one mirror is wrong, remove it from `fetch()` (the other still works alone, with filings marked provisional), or set `EDGAR_CONTACT_EMAIL`.
- **A mirror stops updating:**
  - If weio-ops stalls, XOOMAR still fills the recent days (fewer fields). If XOOMAR stalls, data lags by up to a week.
  - Either way, `EDGAR_CONTACT_EMAIL` restores same-day data.
- **Pages size:** the build is about 250 MB of the 1 GB limit. If it grows, raise the company-page thresholds in `model.Board._companies`.
