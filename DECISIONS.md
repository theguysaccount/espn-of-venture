# DECISIONS

**D1: data product, not a video show.**
- The evaluator's fastest path, a weekly highlight show plus a live pitch game, assumes human hosts.
- The machine version is a weekly recap generated from SEC numbers plus a playable game (Higher or Lower) built on real raises. Same format, no humans.

**D2: public brand "Raise Scoreboard", not "ESPN".**
- ESPN is a Disney trademark, and impersonating a real organization is off-limits.
- The repo keeps its working name `espn-of-venture` as instructed. `silicontank.com` (owned) is the domain candidate for later.

**D3: SEC data through two independent public mirrors; EDGAR direct is a key.**
- EDGAR returns HTTP 403 to every User-Agent without an email address. Tested on 2026-10-25 with repo-URL UAs; one diagnostic request with a reserved example.com address returned 200.
- Using Jack's personal email was ruled out, and inventing a contact would be deceptive, so EDGAR direct is built behind `EDGAR_CONTACT_EMAIL`.
- The default reads weio-ops/sec-form-d (CC BY 4.0, SHA-256 verified) and cross-checks XOOMAR/sec-form-d-offerings filing by filing: 100% agreement on 107,118 overlapping filings since 2025.
- A rebuild is refused below 99.5% agreement. Single-source filings are labelled provisional.

**D4: ranking metric = amount sold on new notices.**
- Amendments repeat cumulative figures, so ranking them would double count.
- Stale continuing offerings (first sale over 400 days before filing) and business-combination exchanges distort a weekly board, so they are shown on box scores but not ranked.

**D5: leagues from SEC industry groups; funds play separately.**
- Pooled investment funds (VC, PE, hedge) are big and different, so they get their own Fund League.
- "Other" stays its own Open League rather than being guessed into sectors, because a model guessing industries would be unverifiable.

**D6: weeks are ISO weeks by filing date, final once Friday's filings are in.**
- EDGAR accepts no Form D filings at weekends.
- Midweek, the home page shows "this week so far" separately from the last complete week.

**D7: company pages only above $1M (funds: $50M).**
- That gives about 20,000 pages with real content (rank, filings, peers) rather than 100,000 thin ones.
- It keeps the site at about 250 MB, well under Pages' 1 GB limit.

**D8: no data in git.**
- About 170 MB of mirror files are downloaded per build (a few seconds on a runner).
- Provenance (checksums, cross-check, commit) is published at `/data/source.json`, and scheduled runs compare against it to skip redundant deploys.
- The keep-alive workflow covers quiet periods.

**D9: no people, no promotion.**
- Related persons are never read.
- Every page carries the Form D disclaimer.
- No links to offering pages and no "invest" language.
- Peers are "similar raises", not recommendations.

**D10: templated recap sentences instead of AI commentary.**
- No API key is available in Actions, and generated prose about real companies risks errors.
- Every sentence is computed from the numbers, so there is no AI-written backlog to maintain.

## Questions for Jack (none block v1)
1. **Contact mailbox for EDGAR.** A real, monitored address (for example on a Persist domain) to set as `EDGAR_CONTACT_EMAIL`. This switches on same-day data and removes the mirror dependency.
2. **Is this the media arm of Startupathon or VibeRounds?** It is neutral until decided, and the brand is easy to change (`SITE` in `scoreboard/site.py`).
3. **Domain.** `silicontank.com` (owned, Namecheap), or register `raisescoreboard.com` (unregistered on 2026-10-25). See LAUNCH.md.
4. **Sponsor slot.** Whether to sell it, at what price, and on which host (GitHub Pages is non-commercial).
