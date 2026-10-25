# PRODUCT

**User.**
- Founders, operators, investors, scouts and startup fans who follow venture like a sport.
- Second audience: reporters and newsletter writers looking for "who raised this week", plus the search and AI engines that answer "<company> funding" and "biggest raises this week".

**Painful job.** Seeing every private raise this week, not just the ones with press releases, sorted and comparable by sector and state. Today that means paid databases (PitchBook, Crunchbase Pro) or scattered news. Form D data is public, but raw EDGAR is unreadable.

**Promise.** A free scoreboard, rebuilt daily from SEC filings:
- who raised the most this week, ranked;
- which sectors and states are winning the season;
- a box score for every company, linked to the filing.

**Wedge.**
- Sports framing (leagues, standings, rookies, box scores) makes dry filings shareable.
- 20,000 company pages answer long-tail funding searches.
- Embeddable weekly leaderboards spread to other sites.

**Why now.**
- Form D data is clean, public and mirrored, so a machine can run the whole thing.
- Mega-rounds (AI labs, infrastructure) have made private raises mainstream news.
- TBPN and All-In cover venture as entertainment but publish no data product a stranger can query.

**Activation metric.** `boxscore_open`: a visitor opens a company box score from a leaderboard. The scoreboard is the hook; the box score is the value. Secondary: `share`, `embed_copy`, `game_over` (streak). All are instrumented in `site/assets/*.js` and count once `SB_GOATCOUNTER` is set.

**First revenue event.** A sponsor buys the weekly scoreboard slot (`SB_SPONSOR_URL`; move hosting off GitHub Pages first, because Pages is non-commercial). Later: a daily alert email by league and state, which needs a mail provider.

**What v1 deliberately won't do.**
- Publish people: executives, directors, promoters.
- Promote offerings, link to offering pages, or imply investment merit.
- Estimate valuations.
- Use non-public data.
- Run live video shows or pitch events (no humans in the loop).
- Brand itself "ESPN" (Disney trademark).
