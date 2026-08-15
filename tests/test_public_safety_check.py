from __future__ import annotations

import unittest

from scripts.public_safety_check import scan_text


class PublicSafetyCheckTests(unittest.TestCase):
    def assert_problem(self, expected: str, text: str) -> None:
        problems = scan_text("fixture.txt", text)
        self.assertTrue(any(item.startswith(expected + ":") for item in problems), problems)

    def test_private_project_identifier_is_blocked(self):
        self.assert_problem("private_identifier", "cannabis" + "-social-media")

    def test_private_campaign_identifier_is_blocked(self):
        self.assert_problem("private_identifier", "diamond" + "-documentary")

    def test_personal_path_is_blocked(self):
        self.assert_problem("personal_path", "C:" + "\\Users\\example\\project")

    def test_service_token_is_blocked(self):
        self.assert_problem("service_token", "sk" + "-abcdefghijklmnop")

    def test_github_token_is_blocked(self):
        self.assert_problem("service_token", "ghp_" + "a" * 24)

    def test_aws_access_key_is_blocked(self):
        self.assert_problem("service_token", "AKIA" + "A" * 16)

    def test_private_key_is_blocked(self):
        self.assert_problem("private_key", "-----BEGIN " + "PRIVATE KEY-----")

    def test_nonempty_credential_assignment_is_blocked(self):
        self.assert_problem("credential_assignment", 'api_' + 'key="not-a-real-secret"')

    def test_empty_env_example_is_allowed(self):
        self.assertEqual(scan_text(".env.example", "ANTHROPIC_API_KEY=\nSMH_WORKSPACE=\n"), [])

    def test_synthetic_example_is_allowed(self):
        self.assertEqual(
            scan_text("example.md", "synthetic-social-project/sample-documentary"), []
        )


if __name__ == "__main__":
    unittest.main()