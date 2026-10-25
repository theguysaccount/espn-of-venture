# Raise Scoreboard (repo: espn-of-venture)

**Live:** https://theguysaccount.github.io/espn-of-venture/ · **This week (JSON):** [latest-week.json](https://theguysaccount.github.io/espn-of-venture/data/latest-week.json) · **Screens:** [docs/screens](docs/screens/)

Every company and fund that files a new SEC Form D, turned into a sports-style scoreboard:
- **Weekly scoreboard and recap:** the top raises, plus "rookies" (first Form D ever).
- **League tables:** Tech, Bio & Health, Energy, Real Estate, Finance, Main Street, Open and Fund leagues.
- **State standings** with power-ranking movement.
- **Season leaders**, and a **box score** page for every company that raised at least $1M (funds: $50M) since 2024.
- **Higher or Lower:** a guessing game built on real raises.
- **Embeddable leaderboard widgets.**

No personal data is published: Form D's list of executives and directors is never read.

## How it runs (no human in the loop)

| Job | Workflow | When | Fails safe because |
|---|---|---|---|
| Fetch Form D data, verify checksums, cross-check two independent mirrors, guard, build about 20,000 pages and share images, deploy to Pages, ping IndexNow | `deploy.yml` | daily 09:23 UTC; on code pushes; by hand | any failed step stops before deploying, and the last good deploy stays live; scheduled runs skip when neither data nor code changed |
| Live health: pages answer, data fresh, mirrors agree, tests pass | `selftest.yml` | Wednesdays 05:47 UTC | read-only |
| Keep schedules alive: re-enable workflows, heartbeat commit after 40 quiet days | `keepalive.yml` | called by every scheduled workflow | runs even when the caller fails |
| Tests (Python 3.9 and 3.12) | `ci.yml` | every push | n/a |

## Data

Form D is filed with the SEC within 15 days of the first sale in a private (exempt) offering. EDGAR's fair-access policy refuses automated clients without a contact email in the User-Agent, so the default path reads two public, independent mirrors of the SEC data on Hugging Face:

- [weio-ops/sec-form-d](https://huggingface.co/datasets/weio-ops/sec-form-d) (CC BY 4.0): every Form D since 2009, rebuilt weekly from the SEC's quarterly data sets and filing XML. Its SHA-256 manifest is verified on download.
- [XOOMAR/sec-form-d-offerings](https://huggingface.co/datasets/XOOMAR/sec-form-d-offerings) (public domain), updated daily. It is compared filing by filing with the first mirror and fills the days after the first mirror's last complete day. On 2026-10-25 the two agreed on 100% of 107,118 overlapping filings since 2025.

Setting the repository variable `EDGAR_CONTACT_EMAIL` switches on direct pulls from EDGAR's daily index at 5 requests per second or fewer. See [OPERATIONS.md](OPERATIONS.md).

## Layout

```
scoreboard/
  sources.py   fetch, verify, normalise, cross-check, merge, guard (mirrors and optional EDGAR direct)
  model.py     leagues, ISO weeks, seasons, eligibility rules, standings, power rankings, box scores
  site.py      static site generator (pages, embeds, share-card HTML, sitemaps, data exports)
  charts.py    SVG bar charts
site/          CSS, browser scripts (share, game), about page, IndexNow key, default share image
scripts/       data guard, share images (og.py), IndexNow (priority plus daily rotation), live health, screenshots
tests/         unittest suites on synthetic fixtures (no network)
```

## Run, test, deploy

```bash
python3 -m scoreboard.sources work    # downloads ~170 MB of mirror data into work/ (git-ignored)
python3 -m scoreboard.site work       # builds dist/ (~20,000 pages, ~10 s)
python3 scripts/og.py dist            # optional: share images with local Chrome
python3 -m http.server 4741 --directory dist
python3 -m unittest discover -s tests -t .
```

Deploys run from `deploy.yml` (push to `main`, daily, or `gh workflow run deploy.yml`).

## What counts as a new raise

All four must hold:
- a new Form D, not an amendment;
- not an acquisition exchange;
- money already sold;
- first sale within 400 days of filing.

Amendments and stale offerings still appear on box scores, marked "not ranked". Weeks run Monday to Sunday by filing date and are final after Friday's filings; seasons are calendar years.

## Licence

Code MIT. Data: SEC public records via weio-ops/sec-form-d (CC BY 4.0); site data CC BY 4.0. See [LICENSE](LICENSE). Not investment advice; Form D is not an offer to sell securities.
