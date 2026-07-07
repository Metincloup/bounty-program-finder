import importlib.util
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "bounty-program-finder" / "scripts" / "bounty_program_finder.py"
FIXTURES = ROOT / "tests" / "fixtures" / "seed_records.json"


def load_module():
    spec = importlib.util.spec_from_file_location("bounty_program_finder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BountyProgramFinderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()
        cls.fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))

    def test_normalizes_supported_seed_platforms(self):
        normalizers = {
            "hackerone": self.mod.normalize_hackerone,
            "bugcrowd": self.mod.normalize_bugcrowd,
            "intigriti": self.mod.normalize_intigriti,
            "yeswehack": self.mod.normalize_yeswehack,
        }
        records = {name: normalizer(self.fixtures[name]) for name, normalizer in normalizers.items()}

        self.assertEqual(records["hackerone"]["program"]["platform"], "hackerone")
        self.assertTrue(records["hackerone"]["bounty"]["offered"])
        self.assertEqual(records["bugcrowd"]["bounty"]["max"], 7500)
        self.assertEqual(records["intigriti"]["bounty"]["currency"], "EUR")
        self.assertEqual(records["yeswehack"]["visibility"], "private")

    def test_seed_only_explicit_github_remains_candidate(self):
        record = self.mod.normalize_hackerone(self.fixtures["hackerone"])
        enricher = self.mod.GitHubEnricher(self.mod.Cache(Path(tempfile.mkdtemp())))
        repos = enricher._extract_explicit_repos(record)

        self.assertEqual(repos[0]["full_name"], "example/example-oss")
        self.assertEqual(repos[0]["match_type"], "explicit_scope")
        self.assertEqual(repos[0]["authorization_status"], "candidate_verification_required")

    def test_filters_exclude_private_by_default(self):
        public_record = self.mod.normalize_bugcrowd(self.fixtures["bugcrowd"])
        private_record = self.mod.normalize_yeswehack(self.fixtures["yeswehack"])

        filtered = self.mod.apply_basic_filters([public_record, private_record], {}, include_private=False)

        self.assertEqual([item["program"]["platform"] for item in filtered], ["bugcrowd"])

    def test_query_infers_oss_audit_filters(self):
        filters, profile = self.mod.infer_filters_from_query(
            "List popular bounty programs with open-source GitHub repositories above 1k stars"
        )

        self.assertEqual(profile, "oss_audit")
        self.assertTrue(filters["require_github"])
        self.assertTrue(filters["bounty_only"])
        self.assertEqual(filters["min_stars"], 1000)
        self.assertIn("source_code", filters["scope_types"])

    def test_query_infers_max_payout_profile(self):
        filters, profile = self.mod.infer_filters_from_query("highest payout HackerOne bounty programs above 5k USD")

        self.assertEqual(profile, "max_payout")
        self.assertEqual(filters["platforms"], ["hackerone"])
        self.assertTrue(filters["bounty_only"])
        self.assertEqual(filters["currency"], "USD")

    def test_explicit_filters_override_query_filters(self):
        query_filters, _ = self.mod.infer_filters_from_query("popular github bounty programs")
        merged = self.mod.merge_filters(query_filters, {"require_github": False, "platforms": ["bugcrowd"]})

        self.assertFalse(merged["require_github"])
        self.assertEqual(merged["platforms"], ["bugcrowd"])

    def test_credential_summary_reports_presence_without_values(self):
        with mock.patch.dict(
            "os.environ",
            {
                "GITHUB_TOKEN": "dummy-github-token",
                "HACKERONE_USERNAME": "researcher",
                "HACKERONE_TOKEN": "dummy-h1-token",
            },
            clear=True,
        ):
            summary = self.mod.credential_summary()

        self.assertTrue(summary["github"]["present"])
        self.assertTrue(summary["hackerone"]["present"])
        self.assertFalse(summary["bugcrowd"]["present"])
        serialized = json.dumps(summary)
        self.assertNotIn("dummy-github-token", serialized)
        self.assertNotIn("dummy-h1-token", serialized)

    def test_json_output_is_parseable_and_has_handoff(self):
        record = self.mod.normalize_hackerone(self.fixtures["hackerone"])
        record["github_repos"] = [
            {
                "full_name": "example/example-oss",
                "url": "https://github.com/example/example-oss",
                "match_type": "explicit_scope",
                "confidence": "high",
                "authorization_status": "candidate_verification_required",
                "source": "seed",
                "stars": 1200,
                "forks": 100,
                "language": "Python",
            }
        ]
        self.mod.score_records([record], "oss_audit")
        output = self.mod.output_document([record], {"require_github": True}, "oss_audit", {"seed": {}}, "json")
        payload = json.loads(output)

        self.assertEqual(payload["schema_version"], "1.0.0")
        self.assertEqual(payload["results"][0]["master_prompt_handoff"]["repository_url"], "https://github.com/example/example-oss")
        self.assertEqual(payload["master_prompt_handoff"][0]["authorization_status"], "candidate_verification_required")


if __name__ == "__main__":
    unittest.main()
