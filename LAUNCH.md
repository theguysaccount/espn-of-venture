# LAUNCH: machine-driven

The scoreboard launches and grows without anyone posting, emailing or hosting anything.

## 1. What's live

- **Site:** https://theguysaccount.github.io/espn-of-venture/ (GitHub Pages, deployed by `deploy.yml`)
- **Data:** `/data/latest-week.json`, `/data/season-<year>.csv`, `/data/game.json`, `/data/source.json` (provenance and cross-check)
- **Widgets:** `/embed/week/` and `/embed/league/<league>/` (the embed code sits at the bottom of the home and league pages)

## 2. How a deploy happens

1. `deploy.yml` runs daily at 09:23 UTC, after the daily mirror updates; on pushes that change code; or with `gh workflow run deploy.yml`.
2. It downloads the mirrors, verifies the checksums and cross-checks them (`scoreboard/sources.py`).
3. `scripts/guard_data.py` compares the result with the live `/data/source.json` and refuses on fewer rows, a backwards date or disagreeing mirrors. On scheduled runs it skips when the data and code are unchanged.
4. Tests run, then the build (`scoreboard/site.py`), share images (`scripts/og.py`), the Pages deploy and the IndexNow submission.

## 3. How people find it (machine channels only)

| Channel | What is in place |
|---|---|
| Search | About 20,000 box scores titled "<Company>: $X raised (Form D, <Month Year>)". There are also weekly recaps ("Biggest startup raises, Week N"), league pages ("Biggest tech startup funding rounds of 2026") and state pages ("Biggest startup raises in Texas, 2026") |
| Structured data | `WebSite` and `Dataset` on the scoreboard, `Article` on recaps, `Organization` on box scores |
| Sitemaps | A sitemap index with a pages sitemap and company sitemaps (40,000 URLs per file), plus `robots.txt` |
| IndexNow | Every deploy submits all priority URLs (scoreboard, weeks, leagues, states, companies with filings in the last 14 days), then a slice of the rest that rotates daily, up to 10,000 per day |
| Share loop | 1200×630 scoreboard cards for the home page, every week, league and state; share buttons; the game's "share your streak" |
| Embeds | Copy-paste widgets for the weekly top 10 and each league's leaders, updated daily, each linking back |
| GitHub | Public repo with a description and topics; open data under CC BY 4.0 |

Search terms each page is built to answer:
- `<company> funding`, `<company> raised`, `<company> form d`
- `biggest startup funding rounds this week`, `startup funding this week`
- `biggest funding rounds 2026`
- `<state> startup funding 2026`
- `biotech funding this week`
- `venture capital fund raises 2026`
- `form d filings`

## 4. The first 14 days (automatic)

| Day | Automation | What to look at (optional) |
|---|---|---|
| 0 | First deploy; IndexNow gets the priority URLs and the first rotation slice | Actions green; `/data/source.json` |
| 1-14 | Daily rebuilds as the mirrors update; new weekly recaps every Monday | New `week/` pages; the home page scoreboard |
| Wednesdays | `selftest.yml`: health, freshness, mirror agreement, keep-alive | Run summary |

Signals of use without an analytics account:
- correction issues;
- GitHub stars;
- Bing indexing (`site:theguysaccount.github.io/espn-of-venture`);
- referrers, once `SB_GOATCOUNTER` is set.

## 5. Production domain (needs Jack; nothing is blocked)

1. **silicontank.com.** Owned (Namecheap, since 2024-02-13). It matches the note's "silicon tank vibes".
2. **raisescoreboard.com.** Unregistered per WHOIS on 2026-10-25. Needs Jack's OK to spend about $10/yr.
3. **formdscoreboard.com.** Unregistered per WHOIS on 2026-10-25. Backup.

Steps for an apex domain (option 1):
1. At Namecheap, set `A @` to `185.199.108.153`, `185.199.109.153`, `185.199.110.153` and `185.199.111.153`.
2. Set `AAAA @` to `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153` and `2606:50c0:8003::153`.
3. Add `CNAME www theguysaccount.github.io.`
4. Set the repository variables `SB_CUSTOM_DOMAIN=silicontank.com` and `SB_BASE_URL=https://silicontank.com`.
5. Run `gh workflow run deploy.yml`. The build writes `dist/CNAME` and switches canonical URLs, sitemaps and share cards to the domain.
6. In Settings, then Pages, confirm the domain and tick "Enforce HTTPS" once the certificate is issued.

For a subdomain instead (e.g. `scores.silicontank.com`), use one record, `CNAME scores theguysaccount.github.io.`, then do steps 4-6.
