import unittest

from scoreboard import sources

DAILY_INDEX = """Description:           Daily Index of EDGAR Dissemination Feed by Form Type
Last Data Received:    Oct 23, 2026
Form Type   Company Name                                                  CIK         Date Filed  File Name
---------------------------------------------------------------------------------------------------------------------------------------------
10-K        SOME CO                                                       1234567     20261023    edgar/data/1234567/0001234567-26-000001.txt
D           MODAL LABS, INC.                                              2088132     20261023    edgar/data/2088132/0002088132-26-000003.txt
D/A         ACME FUND II, L.P.                                            1999999     20261023    edgar/data/1999999/0001999999-26-000002.txt
DEF 14A     OTHER CO                                                      7654321     20261023    edgar/data/7654321/0007654321-26-000009.txt
"""

PRIMARY_DOC = """<?xml version="1.0"?>
<edgarSubmission xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <schemaVersion>X0708</schemaVersion><submissionType>D</submissionType>
  <primaryIssuer>
    <cik>0002088132</cik><entityName>Modal Labs, Inc.</entityName>
    <issuerAddress><street1>REDACTED</street1><city>NEW YORK</city><stateOrCountry>NY</stateOrCountry><zipCode>10001</zipCode></issuerAddress>
    <issuerPhoneNumber>555</issuerPhoneNumber><jurisdictionOfInc>DELAWARE</jurisdictionOfInc>
    <entityType>Corporation</entityType><yearOfInc><withinFiveYears>true</withinFiveYears><value>2021</value></yearOfInc>
  </primaryIssuer>
  <relatedPersonsList><relatedPersonInfo><relatedPersonName><firstName>Jane</firstName><lastName>Doe</lastName></relatedPersonName></relatedPersonInfo></relatedPersonsList>
  <offeringData>
    <industryGroup><industryGroupType>Other Technology</industryGroupType></industryGroup>
    <issuerSize><revenueRange>Decline to Disclose</revenueRange></issuerSize>
    <federalExemptionsExclusions><item>06b</item></federalExemptionsExclusions>
    <typeOfFiling><newOrAmendment><isAmendment>false</isAmendment></newOrAmendment><dateOfFirstSale><value>2026-10-10</value></dateOfFirstSale></typeOfFiling>
    <durationOfOffering><moreThanOneYear>false</moreThanOneYear></durationOfOffering>
    <typesOfSecuritiesOffered><isEquityType>true</isEquityType><isOptionToAcquireType>true</isOptionToAcquireType></typesOfSecuritiesOffered>
    <businessCombinationTransaction><isBusinessCombinationTransaction>false</isBusinessCombinationTransaction></businessCombinationTransaction>
    <minimumInvestmentAccepted>0</minimumInvestmentAccepted>
    <offeringSalesAmounts><totalOfferingAmount>800000000</totalOfferingAmount><totalAmountSold>602000000</totalAmountSold><totalRemaining>198000000</totalRemaining></offeringSalesAmounts>
    <investors><hasNonAccreditedInvestors>false</hasNonAccreditedInvestors><totalNumberAlreadyInvested>18</totalNumberAlreadyInvested></investors>
  </offeringData>
</edgarSubmission>"""


class NormaliseTests(unittest.TestCase):
    def test_to_int_and_bools(self):
        self.assertEqual(sources.to_int("3425000.00"), "3425000")
        self.assertEqual(sources.to_int("Indefinite"), "")
        self.assertEqual(sources.to_int(""), "")
        self.assertEqual(sources.norm_bool("Y"), "true")
        self.assertEqual(sources.norm_bool(""), "")

    def test_exemptions_normalise_across_mirrors(self):
        self.assertEqual(sources.norm_exemptions("06b, 3C, 3C.7"), sources.norm_exemptions("06b;3C;3C.7"))

    def test_weio_and_xoomar_rows_agree_on_compared_fields(self):
        w = sources.weio_row({"accession_number": "0001-26-1", "filing_date": "2026-10-20", "form_type": "D", "cik": "2088132",
                              "entity_name": "Modal Labs, Inc.", "issuer_state_or_country": "NY", "industry_group": "Other Technology",
                              "total_offering_amount": "800000000", "total_amount_sold": "602000000",
                              "federal_exemptions": "06b", "filing_index_url": ""})
        x = sources.xoomar_row({"accession_no": "0001-26-1", "cik": "0002088132", "issuer_name": "Modal Labs, Inc.", "state": "NY",
                                "industry_group": "Other Technology", "is_amendment": "false", "total_offering_amount": "800000000.00",
                                "total_amount_sold": "602000000.00", "exemptions": "06b", "filed_at": "2026-10-20",
                                "security_types": "equity, options"})
        for f in sources.COMPARE:
            self.assertEqual(w[f], x[f], f)
        self.assertEqual(x["securities"], "Equity;Option/Warrant")
        self.assertEqual(w["filing_url"], "https://www.sec.gov/Archives/edgar/data/2088132/0001261/")

    def test_no_personal_fields_are_kept(self):
        for banned in ("first_name", "last_name", "related_persons", "phone", "street", "zip"):
            self.assertFalse(any(banned in f for f in sources.FIELDS), banned)


class EdgarTests(unittest.TestCase):
    def test_daily_index_keeps_only_form_d(self):
        rows = sources.parse_daily_index(DAILY_INDEX)
        self.assertEqual([r["form_type"] for r in rows], ["D", "D/A"])
        self.assertEqual(rows[0]["accession"], "0002088132-26-000003")
        self.assertEqual(rows[0]["filing_date"], "2026-10-23")
        self.assertEqual(rows[1]["cik"], "1999999")

    def test_primary_doc_parses_to_the_common_row(self):
        ir = sources.parse_daily_index(DAILY_INDEX)[0]
        r = sources.parse_primary_doc(PRIMARY_DOC, ir)
        self.assertEqual(r["cik"], "2088132")
        self.assertEqual(r["amount_sold"], "602000000")
        self.assertEqual(r["offering_amount"], "800000000")
        self.assertEqual(r["state"], "NY")
        self.assertEqual(r["year_of_inc"], "2021")
        self.assertEqual(r["securities"], "Equity;Option/Warrant")
        self.assertEqual(r["business_combination"], "false")
        self.assertEqual(r["source"], "edgar")
        self.assertNotIn("Doe", repr(r))  # related persons are never read

    def test_contact_email_goes_in_the_user_agent(self):
        self.assertIn("ops@example.org", sources.edgar_ua("ops@example.org"))


class MergeGuardTests(unittest.TestCase):
    def mk(self, acc, sold, src):
        r = {f: "" for f in sources.FIELDS}
        r.update({"accession": acc, "filing_date": "2026-10-20", "amount_sold": str(sold), "cik": "1", "state": "CA",
                  "industry": "Other", "offering_amount": "", "source": src})
        return r

    def test_merge_prefers_weio_and_marks_confirmed(self):
        out = sources.merge([self.mk("a", 5, "weio")], [self.mk("a", 5, "xoomar"), self.mk("b", 7, "xoomar")], [])
        by = {r["accession"]: r for r in out}
        self.assertEqual(by["a"]["source"], "weio")
        self.assertEqual(by["a"]["confirmed"], "true")
        self.assertEqual(by["b"]["confirmed"], "false")

    def test_cross_check_counts_mismatches(self):
        cc = sources.cross_check([self.mk("a", 5, "weio"), self.mk("b", 6, "weio")], [self.mk("a", 5, "x"), self.mk("b", 9, "x")])
        self.assertEqual(cc["overlap"], 2)
        self.assertEqual(cc["agree"], 1)
        self.assertEqual(cc["mismatches"]["amount_sold"], 1)

    def test_guard(self):
        good = {"complete_through": "2026-10-23", "rows": 1000, "cross_check": {"overlap": 5000, "agreement": 1.0}}
        self.assertEqual(sources.guard(good, None), [])
        self.assertEqual(sources.guard(good, {"complete_through": "2026-10-22", "rows": 990}), [])
        self.assertTrue(sources.guard(dict(good, complete_through="2026-10-20"), {"complete_through": "2026-10-22", "rows": 990}))
        self.assertTrue(sources.guard(dict(good, rows=900), {"complete_through": "2026-10-22", "rows": 1000}))
        self.assertTrue(sources.guard(dict(good, cross_check={"overlap": 5000, "agreement": 0.98}), None))
        self.assertTrue(sources.guard(dict(good, cross_check={"overlap": 10, "agreement": 1.0}), None))


if __name__ == "__main__":
    unittest.main()
