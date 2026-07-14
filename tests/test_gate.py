# -*- coding: utf-8 -*-
"""候选人硬门 + gate-action:先硬门后错题本、无旁路、fail-closed。"""
import os
import unittest

from nb_base import NotebookTestBase, nb

FIVE = sorted(nb.PROTECTED_ACTIONS)
BLOCK_INTENTS = ["reject", "no_interest", "do_not_contact"]


class TestHardGate(NotebookTestBase):
    # 任务测试 6:reject/no_interest/do_not_contact 硬门在错题本缺失/损坏时仍阻断五类,且错题本解不开
    def test_block_intents_block_all_five_no_notebook(self):
        for intent in BLOCK_INTENTS:
            for act in FIVE:
                r = nb.gate_action(act, intent)
                self.assertEqual(r["decision"], "blocked", "%s/%s" % (act, intent))
                self.assertEqual(r["decided_by"], "candidate_hard")
                self.assertEqual(r["reason_code"], "candidate_intent_hard_block")
                self.assertEqual(r["notebook_status"], "missing")

    def test_block_intents_block_with_corrupt_notebook(self):
        path = os.path.join(self.tmp, "notebook.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"id":"L-1","tier":"auto","target":"report_order","value":"a_first","status":"active"}\n')
            f.write("this is not json at all }{\n")   # 损坏行
        for intent in BLOCK_INTENTS:
            for act in FIVE:
                r = nb.gate_action(act, intent)
                self.assertEqual(r["decision"], "blocked", "%s/%s" % (act, intent))
                self.assertEqual(r["hard_gate"]["decision"], "blocked")
                # 损坏错题本绝不放宽硬门
                self.assertNotEqual(r["decision"], "allowed")

    def test_notebook_cannot_unlock_hard_block(self):
        # 即使错题本里堆满 active 条目,也无法把 blocked 变 allowed
        for _ in range(3):
            nb.record({"tier": "auto", "target": "report_order", "value": "a_first"})
        r = nb.gate_action("request_resume", "do_not_contact")
        self.assertEqual(r["decision"], "blocked")


class TestPendingReviewFailClosed(NotebookTestBase):
    # 任务测试 7:新回复 pending;未确认 interested 前 四类 fail-closed
    def test_four_actions_fail_closed_before_interested(self):
        four = ["send_custom_message", "follow_up", "request_resume", "use_chat_card"]
        for intent in ("unknown", "pending_intent_review"):
            for act in four:
                r = nb.gate_action(act, intent)
                self.assertEqual(r["decision"], "needs_review", "%s/%s" % (act, intent))
                self.assertEqual(r["reason_code"], "intent_not_confirmed_interested")

    def test_initial_greet_allowed_when_unknown(self):
        r = nb.gate_action("greet", "unknown")
        self.assertEqual(r["decision"], "allowed")
        self.assertEqual(r["reason_code"], "initial_greet_ok")

    def test_greet_pending_review_needs_review(self):
        # L2:初次 greet 仅 unknown 放行;pending_intent_review 下即使 greet 也 needs_review
        r = nb.gate_action("greet", "pending_intent_review")
        self.assertEqual(r["decision"], "needs_review")
        self.assertEqual(r["reason_code"], "intent_not_confirmed_interested")

    def test_interested_passes_hard_gate(self):
        for act in FIVE:
            r = nb.gate_action(act, "interested")
            self.assertEqual(r["decision"], "allowed", act)
            self.assertEqual(r["hard_gate"]["reason_code"], "intent_interested")


class TestGateCoverage(NotebookTestBase):
    # 任务测试 8:覆盖五类动作,无旁路;非法/缺失意图 fail-closed
    def test_all_five_actions_recognized(self):
        self.assertEqual(FIVE, sorted(
            ["greet", "send_custom_message", "follow_up", "request_resume", "use_chat_card"]))

    def test_unknown_action_rejected(self):
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.gate_action("delete_job", "interested")
        self.assertEqual(ctx.exception.reason_code, "unknown_action")

    def test_missing_intent_defaults_fail_closed(self):
        # 缺意图 → unknown → 四类后接触动作 needs_review(不放行)
        r = nb.gate_action("request_resume", None)
        self.assertEqual(r["candidate_intent"], "unknown")
        self.assertEqual(r["decision"], "needs_review")

    def test_invalid_intent_blocked(self):
        r = nb.gate_action("request_resume", "he_seems_keen")
        self.assertEqual(r["decision"], "blocked")
        self.assertEqual(r["reason_code"], "invalid_intent")


class TestReadContinuesOnCorruption(NotebookTestBase):
    # 任务测试 12:损坏时只读报告继续 + 报异常;外发/花钱不被放宽
    def test_list_survives_corruption(self):
        path = os.path.join(self.tmp, "notebook.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"id":"L-1","tier":"auto","kind":"preference","target":"report_order",'
                    '"value":"a_first","status":"active","created_at":"2026-01-01T00:00:00Z",'
                    '"reason_code":"report_format","evidence_count":1,"ttl_days":null,'
                    '"reverted_at":null,"expired_at":null}\n')
            f.write("GARBAGE\n")
        res = nb.list_entries()
        self.assertTrue(res["ok"])                 # 只读报告继续
        self.assertEqual(res["status"], "corrupt")  # 报告异常
        self.assertEqual(len(res["entries"]), 1)    # 好行仍可用

    def test_interested_stays_allowed_but_notebook_flagged_corrupt(self):
        # 损坏错题本不能"放宽",但也不能凭空把硬门放行的变阻断以外——关键是不放宽
        path = os.path.join(self.tmp, "notebook.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not-json\n")
        r = nb.gate_action("use_chat_card", "interested")
        # 硬门放行(interested),错题本损坏未施加收紧;核心不变式:损坏≠放宽被硬门挡下的动作
        self.assertEqual(r["hard_gate"]["decision"], "allowed")
        self.assertEqual(r["notebook_status"], "corrupt")

    def test_corrupt_notebook_never_relaxes_block(self):
        path = os.path.join(self.tmp, "notebook.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("still-not-json\n")
        r = nb.gate_action("use_chat_card", "no_interest")
        self.assertEqual(r["decision"], "blocked")


if __name__ == "__main__":
    unittest.main()
