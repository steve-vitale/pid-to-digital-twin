"""Controls for scripts/check_claims.py: the committed tree agrees with the README, a wrong README is caught, and a
missing evidence file fails loudly. Reads only committed files; the README is patched in memory, never on disk."""
import contextlib
import dataclasses
import io
import unittest

import check_claims as cc


def readme():
    return cc.README.read_text(encoding="utf-8")


class CommittedTree(unittest.TestCase):
    def test_every_non_te_claim_passes(self):
        bad = [r for r in cc.run(readme_text=readme()) if not r["te"] and r["status"] == "FAIL"]
        self.assertEqual(bad, [], [(r["id"], r["detail"]) for r in bad])

    def test_te_claims_run_and_say_why_when_they_fail(self):
        # TE outputs can be mid-rebuild, so a disagreement is reported here rather than failing the suite.
        for r in cc.run(readme_text=readme()):
            if r["te"]:
                self.assertIn(r["status"], ("ok", "FAIL"))
                if r["status"] == "FAIL":
                    print(f"NOTE TE claim {r['id']}: {r['detail']}")

    def test_only_the_figure_10_first_run_is_prose_only(self):
        prose = [r["id"] for r in cc.run(readme_text=readme()) if r["status"] == "prose only"]
        self.assertEqual(prose, ["B-fig10-first"])

    def test_claim_ids_are_unique(self):
        ids = [c.id for c in cc.CLAIMS]
        self.assertEqual(len(ids), len(set(ids)))


class Drift(unittest.TestCase):
    def test_edited_readme_number_is_noticed(self):
        patched = readme().replace("**20.1**", "**21.4**")
        self.assertNotEqual(patched, readme())
        results = {r["id"]: r for r in cc.run(readme_text=patched)}
        self.assertEqual(results["A-gpt-load-r5"]["status"], "FAIL")
        self.assertIn("README no longer contains", results["A-gpt-load-r5"]["detail"])
        self.assertEqual(results["A-claude-load-r5"]["status"], "ok")

    def test_wrong_stated_value_is_caught_even_if_phrase_present(self):
        claim = next(c for c in cc.CLAIMS if c.id == "Q-red")
        result = cc.run([dataclasses.replace(claim, stated=378)], readme())[0]
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("README says 378, evidence says 377", result["detail"])

    def test_rounding_is_at_readme_precision(self):
        claim = next(c for c in cc.CLAIMS if c.id == "A-gpt-load-r5")
        self.assertEqual(cc.run([dataclasses.replace(claim, stated=20.0)], readme())[0]["status"], "FAIL")
        close = dataclasses.replace(claim, derive=lambda: 20.0615)    # rounds to the README's 20.1
        self.assertEqual(cc.run([close], readme())[0]["status"], "ok")

    def test_exit_status_is_one_on_a_failure(self):
        original = cc.CLAIMS
        try:
            cc.CLAIMS = [dataclasses.replace(original[0], stated=0.5)]
            printed = io.StringIO()  # a deliberate failure: keep its FAIL table out of the test log
            with contextlib.redirect_stdout(printed):
                self.assertEqual(cc.main(["--quiet", "--no-write"]), 1)
            self.assertIn("FAIL", printed.getvalue())
        finally:
            cc.CLAIMS = original


class MissingEvidence(unittest.TestCase):
    def test_missing_file_fails_and_names_the_file(self):
        claim = next(c for c in cc.CLAIMS if c.id == "Q-red")
        gone = dataclasses.replace(claim, derive=lambda: cc.load_json("out/no_such_result.json"))
        result = cc.run([gone], readme())[0]
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("out/no_such_result.json", result["detail"])

    def test_missing_field_fails_loudly(self):
        claim = next(c for c in cc.CLAIMS if c.id == "X-median")
        bad = dataclasses.replace(claim, derive=lambda: cc.at(cc.load_json(cc.FAULTS), ["no_such_field"], cc.FAULTS))
        result = cc.run([bad], readme())[0]
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("no field no_such_field", result["detail"])

    def test_missing_prose_sentence_is_not_a_pass(self):
        claim = next(c for c in cc.CLAIMS if c.id == "B-fig10-first")
        gone = dataclasses.replace(claim, derive=lambda: cc.prose_in_doc(cc.BAYER_DOC, r"no such sentence (\d+)"))
        self.assertNotEqual(cc.run([gone], readme())[0]["status"], "ok")


class Counts(unittest.TestCase):
    def test_te_row_counts_match_the_reports_own_totals(self):
        self.assertEqual(cc.count_statuses(cc.TOPOLOGY_CHECK, "confirmed"), cc.totals_line(cc.TOPOLOGY_CHECK, "confirmed"))
        self.assertEqual(cc.count_statuses(cc.TOPOLOGY_CHECK, "corrected"), cc.totals_line(cc.TOPOLOGY_CHECK, "corrected"))
        self.assertEqual(cc.count_statuses(cc.SOURCE_CHECK, "confirmed"), cc.totals_line(cc.SOURCE_CHECK, "confirmed"))


if __name__ == "__main__":
    unittest.main()
