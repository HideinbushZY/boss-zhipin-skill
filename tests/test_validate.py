# -*- coding: utf-8 -*-
"""validate.py:真正执行 notebook 块取值范围 + 候选人 candidate_intent 枚举校验。"""
import os
import sys
import shutil
import tempfile
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VALIDATE = os.path.join(REPO, "validate.py")

BASE_STRATEGY = """\
name: t
rubric:
  must:
    - 有语音算法实战经验
budget:
  greets_per_day: 10
  chat_cards: 0
touch_policy: report_first
"""


class ValidateBase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="nb-val-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def write(self, strategy=BASE_STRATEGY, ledger=None):
        with open(os.path.join(self.d, "strategy.yaml"), "w", encoding="utf-8") as f:
            f.write(strategy)
        if ledger is not None:
            with open(os.path.join(self.d, "ledger.jsonl"), "w", encoding="utf-8") as f:
                f.write(ledger)

    def run_validate(self):
        return subprocess.run([sys.executable, VALIDATE, self.d + os.sep],
                              capture_output=True, text=True)


class TestNotebookBlock(ValidateBase):
    def test_valid_notebook_block_passes(self):
        self.write(BASE_STRATEGY + "notebook:\n  capture: on\n  "
                   "platform_pitfall_ttl_days: 30\n  confirm_after_n_repeats: 3\n")
        r = self.run_validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ttl_out_of_range_fails(self):
        self.write(BASE_STRATEGY + "notebook:\n  platform_pitfall_ttl_days: 200\n")
        r = self.run_validate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("platform_pitfall_ttl_days", r.stdout)

    def test_confirm_repeats_out_of_range_fails(self):
        self.write(BASE_STRATEGY + "notebook:\n  confirm_after_n_repeats: 1\n")
        r = self.run_validate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("confirm_after_n_repeats", r.stdout)

    def test_capture_off_valid(self):
        self.write(BASE_STRATEGY + "notebook:\n  capture: off\n")
        r = self.run_validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bad_capture_fails(self):
        self.write(BASE_STRATEGY + "notebook:\n  capture: sometimes\n")
        r = self.run_validate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("capture", r.stdout)


class TestCandidateIntent(ValidateBase):
    def test_valid_intent_passes(self):
        self.write(ledger='{"id":"c1","name":"x","status":"greeted","candidate_intent":"pending_intent_review"}\n')
        r = self.run_validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_invalid_intent_fails(self):
        self.write(ledger='{"id":"c1","name":"x","status":"greeted","candidate_intent":"maybe_keen"}\n')
        r = self.run_validate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("candidate_intent", r.stdout)


class TestExampleStrategyStillValid(unittest.TestCase):
    def test_shipped_example_passes(self):
        d = os.path.join(REPO, "strategies", "asr-engineer-example") + os.sep
        r = subprocess.run([sys.executable, VALIDATE, d], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
