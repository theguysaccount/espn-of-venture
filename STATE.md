# STATE: 2026-10-25

**Before this repo:** one Apple Note ("ESPN of Venture: … silicon tank vibes") with a reel link. No code, no data, no design.

**Works now:**
- Live scoreboard built from every Form D since January 2024: 164k filings, 68k ranked raises and 20,091 company box scores.
- 95 weekly recaps, 8 league pages and 55 state pages, plus season leaders, the Higher or Lower game, embeds, JSON/CSV exports and 160 share images.
- Daily deploy with checksum verification, a two-mirror cross-check, a data guard and skip-if-unchanged. Weekly self-test and keep-alive. 33 tests.

**Data path:**
- EDGAR returns 403 to any client without a contact email, verified 2026-10-25.
- The default path is two independent Hugging Face mirrors of the SEC data, which agree on 100% of 107,118 overlapping filings.
- Direct EDGAR pulls are built and switch on with `EDGAR_CONTACT_EMAIL`. That path is unit-tested on the documented XML structure but has not run against live EDGAR.

**Known gaps:**
- Freshness is about one business day behind EDGAR through the mirrors.
- Industry leagues depend on the filer's self-chosen industry group; "Other" (the Open League) holds many tech startups.
- The ranking metric is "amount sold" as reported. It can include debt or convertibles and is cumulative for an offering.
- Analytics are off until a GoatCounter key is set; there is no custom domain.

**Worth reusing:**
- `scoreboard/sources.py`: a mirror plus cross-check plus guard pattern for SEC data without an EDGAR email.
- `scripts/indexnow.py`: priority plus daily rotation for sites over 10,000 URLs.
