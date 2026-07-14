# -*- coding: utf-8 -*-
"""端到端 3 用例(A 候选人拒绝硬门 / B 习惯自动调+撤销 / C 平台坑带 TTL)+ CLI 冒烟。"""
import os
import sys
import json
import subprocess
import unittest

from nb_base import NotebookTestBase, nb, REPO, SCRIPTS

NB = os.path.join(SCRIPTS, "notebook.py")


class TestE2E_A_HardGate(NotebookTestBase):
    """A:新回复→pending→用户设 no_interest→无错题本也硬阻断五类→只记结构化审计。"""

    def test_reject_hard_block_end_to_end(self):
        # 新回复:候选人先进 pending_intent_review(意图未定)
        for act in ("request_resume", "follow_up", "send_custom_message", "use_chat_card"):
            self.assertEqual(nb.gate_action(act, "pending_intent_review")["decision"],
                             "needs_review")
        # 用户明确判定 no_interest → 五类全部硬阻断,且错题本此时完全为空(缺失)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "notebook.jsonl")))
        for act in sorted(nb.PROTECTED_ACTIONS):
            r = nb.gate_action(act, "no_interest")
            self.assertEqual(r["decision"], "blocked", act)
            self.assertEqual(r["decided_by"], "candidate_hard")
        # 结构化审计只落候选人账本(intent 字段),错题本不存候选人任何信息:仍然没有错题本文件
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "notebook.jsonl")))


class TestE2E_B_HabitAutoRevert(NotebookTestBase):
    """B:用户三次要'A 类先行'→auto 应用+报告标注→撤销→下轮不再应用。"""

    def test_habit_apply_then_revert(self):
        r1 = nb.record({"tier": "auto", "target": "report_order", "value": "a_first",
                        "kind": "habit", "reason_code": "report_format"})
        nb.record({"tier": "auto", "target": "report_order", "value": "a_first",
                   "kind": "habit", "reason_code": "report_format"}, observe=True)
        r3 = nb.record({"tier": "auto", "target": "report_order", "value": "a_first",
                        "kind": "habit", "reason_code": "report_format"}, observe=True)
        lid = r1["entry"]["id"]
        self.assertEqual(r3["entry"]["evidence_count"], 3)
        # 开跑读取 → active auto 条目被"应用"(出现在 active 列表)
        applied = nb.list_entries()["entries"]
        self.assertEqual([e["id"] for e in applied], [lid])
        self.assertEqual(applied[0]["target"], "report_order")
        self.assertEqual(applied[0]["value"], "a_first")
        # 撤销 L-x → 下一轮读取不再出现
        nb.revert(lid)
        self.assertEqual(nb.list_entries()["entries"], [])


class TestE2E_C_PitfallTTL(NotebookTestBase):
    """C:两次 platform_route_failure→写 chat_route=left_menu_chat(auto)→报告标注→30 天惰性过期。"""

    def test_pitfall_ttl_end_to_end(self):
        nb.record({"tier": "auto", "target": "chat_route", "value": "left_menu_chat",
                   "kind": "platform_pitfall", "ttl_days": 30,
                   "reason_code": "platform_route_failure"},
                  now="2026-03-01T00:00:00Z")
        again = nb.record({"tier": "auto", "target": "chat_route", "value": "left_menu_chat",
                           "kind": "platform_pitfall",
                           "reason_code": "platform_route_failure"},
                          observe=True, now="2026-03-02T00:00:00Z")
        self.assertEqual(again["entry"]["evidence_count"], 2)
        # 30 天内:生效(应用聊天页走左侧菜单)
        mid = nb.list_entries(now="2026-03-20T00:00:00Z")["entries"]
        self.assertEqual(len(mid), 1)
        self.assertEqual(mid[0]["value"], "left_menu_chat")
        # 30 天后:惰性过期,不再应用
        after = nb.list_entries(now="2026-04-05T00:00:00Z")
        self.assertEqual(after["entries"], [])
        self.assertIn("L-1", after["expired_now"])


class TestCLISmoke(NotebookTestBase):
    """CLI 连线冒烟:record → list → revert(临时状态目录 + 合成数据)。"""

    def _run(self, args, stdin=None):
        env = dict(os.environ)
        env["BOSS_ZHIPIN_STATE_DIR"] = self.tmp
        p = subprocess.run([sys.executable, NB] + args, input=stdin,
                           capture_output=True, text=True, env=env)
        return p

    def test_record_list_revert_cli(self):
        payload = json.dumps({"tier": "auto", "target": "report_order", "value": "a_first"})
        r = self._run(["record", "--input", "-"], stdin=payload)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out["persisted"])
        lid = out["entry"]["id"]

        r = self._run(["list"])
        self.assertEqual(json.loads(r.stdout)["count"], 1)

        r = self._run(["revert", "--id", lid])
        self.assertTrue(json.loads(r.stdout)["changed"])

        r = self._run(["list"])
        self.assertEqual(json.loads(r.stdout)["count"], 0)

    def test_doctor_with_context_fixture(self):
        fixture = os.path.join(REPO, "tests", "fixtures", "context.json")
        with open(fixture, "r", encoding="utf-8") as f:
            r = self._run(["doctor", "--input", "-"], stdin=f.read())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertIn("checks", out)

    def test_cli_pii_rejected_nonzero(self):
        payload = json.dumps({"target": "report_order", "value": "a_first", "name": "x"})
        r = self._run(["record", "--input", "-"], stdin=payload)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["reason_code"], "pii_detected")


if __name__ == "__main__":
    unittest.main()
