# -*- coding: utf-8 -*-
"""错题本核心:存储/权限/三层白名单/PII/只收权/撤销/TTL/capture/展示偏好边界。"""
import os
import sys
import stat
import tempfile
import unittest

from nb_base import NotebookTestBase, nb, REPO


class TestStorage(NotebookTestBase):
    # 任务测试 1:目录在仓库外 + 拒符号链接 + 权限收紧
    def test_state_dir_outside_repo_default(self):
        p = nb.record({"target": "report_order", "value": "a_first"})["entry"]
        self.assertEqual(p["id"], "L-1")
        path = os.path.join(self.tmp, "notebook.jsonl")
        self.assertTrue(os.path.exists(path))
        # 落在临时目录(仓库外),不在仓库内
        self.assertFalse(os.path.realpath(path).startswith(os.path.realpath(REPO) + os.sep))

    def test_reject_state_dir_inside_repo(self):
        os.environ["BOSS_ZHIPIN_STATE_DIR"] = os.path.join(REPO, "scratch_state")
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.record({"target": "report_order", "value": "a_first"})
        self.assertEqual(ctx.exception.reason_code, "state_dir_in_repo")
        self.assertFalse(os.path.exists(os.path.join(REPO, "scratch_state")))

    def test_reject_symlink_state_dir(self):
        realdir = tempfile.mkdtemp(prefix="nb-real-")
        link = os.path.join(tempfile.mkdtemp(prefix="nb-link-"), "state-link")
        os.symlink(realdir, link)
        os.environ["BOSS_ZHIPIN_STATE_DIR"] = link
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.record({"target": "report_order", "value": "a_first"})
        self.assertEqual(ctx.exception.reason_code, "symlink_rejected")

    @unittest.skipUnless(os.name == "posix", "POSIX perms only")
    def test_perms_tightened(self):
        nb.record({"target": "report_order", "value": "a_first"})
        dmode = stat.S_IMODE(os.stat(self.tmp).st_mode)
        fmode = stat.S_IMODE(os.stat(os.path.join(self.tmp, "notebook.jsonl")).st_mode)
        self.assertEqual(dmode, 0o700)
        self.assertEqual(fmode, 0o600)

    def test_import_does_not_create_dir(self):
        # 全新目录路径,仅 import 过 nb,未调写操作 → 不应存在
        fresh = os.path.join(self.tmp, "sub", "deeper")
        os.environ["BOSS_ZHIPIN_STATE_DIR"] = fresh
        self.assertFalse(os.path.exists(fresh))


class TestWhitelist(NotebookTestBase):
    # 任务测试 2:auto 白名单外 target 不能写 auto/confirm
    def test_unknown_target_rejected(self):
        self.assertRejected({"tier": "auto", "target": "totally_made_up", "value": "x"},
                            reason_code="target_not_whitelisted")

    def test_confirm_target_as_auto_is_expand(self):
        self.assertRejected({"tier": "auto", "target": "greeting_tone", "value": "warm"},
                            reason_code="expand_denied")

    def test_bad_value_rejected(self):
        self.assertRejected({"tier": "auto", "target": "report_order", "value": "sideways"},
                            reason_code="value_not_allowed")

    def test_report_detail_count_range(self):
        ok = nb.record({"tier": "auto", "target": "report_detail_count", "value": 12})["entry"]
        self.assertEqual(ok["value"], 12)
        self.assertRejected({"tier": "auto", "target": "report_detail_count", "value": 999},
                            reason_code="value_not_allowed")

    # 任务测试 3:note_only / 红线 / 公平性代理 永远写不成可执行
    def test_note_only_target_cannot_be_auto(self):
        for tgt in ("touch_policy", "budget_chat_cards", "pii_request", "salary",
                    "job_publish_close_delete", "phone_wechat_swap"):
            self.assertRejected({"tier": "auto", "target": tgt, "value": "hide"},
                                reason_code="note_only_not_executable")
            self.assertRejected({"tier": "confirm", "target": tgt, "value": "true"},
                                reason_code="note_only_not_executable")

    def test_fairness_proxy_cannot_be_executable(self):
        for tgt in ("school", "city", "region", "age", "gender", "marital",
                    "employment_gap", "company_fame"):
            self.assertRejected({"tier": "auto", "target": tgt, "value": "hide"},
                                reason_code="fairness_not_executable")
            self.assertRejected({"tier": "confirm", "target": tgt, "value": "true"},
                                reason_code="fairness_not_executable")

    def test_note_only_recorded_but_non_executable(self):
        # note_only 可作为不可执行建议记一笔(value 恒 flagged)
        r = nb.record({"tier": "note_only", "target": "touch_policy", "value": "flagged"})
        self.assertEqual(r["entry"]["tier"], "note_only")
        self.assertEqual(r["entry"]["value"], "flagged")
        # 但它绝不出现在"可自动应用"的 auto 集合里
        active_auto = [e for e in nb.list_entries(include="all")["entries"]
                       if e["tier"] == "auto"]
        self.assertEqual(active_auto, [])

    def test_note_only_value_must_be_flagged(self):
        self.assertRejected({"tier": "note_only", "target": "salary", "value": "60"},
                            reason_code="value_not_allowed")


class TestPII(NotebookTestBase):
    # 任务测试 4:疑似 PII 被拒不落盘
    def test_forbidden_key_name(self):
        self.assertRejected({"target": "report_order", "value": "a_first", "name": "somebody"},
                            reason_code="pii_detected")

    def test_phone_in_value(self):
        self.assertRejected({"target": "report_order", "value": "13800138000"},
                            reason_code="pii_detected")

    def test_cjk_in_value(self):
        self.assertRejected({"target": "report_order", "value": "张三"},
                            reason_code="pii_detected")

    def test_message_body_key(self):
        self.assertRejected({"target": "report_order", "value": "a_first",
                             "message": "hi there candidate"},
                            reason_code="pii_detected")

    def test_securityid_key(self):
        self.assertRejected({"target": "report_order", "value": "a_first",
                             "securityId": "abc123"},
                            reason_code="pii_detected")

    def test_unknown_field_rejected(self):
        self.assertRejected({"target": "report_order", "value": "a_first", "weird": 1},
                            reason_code="unknown_field")

    def test_nested_structure_rejected(self):
        self.assertRejected({"target": "report_order", "value": {"nested": 1}},
                            reason_code="bad_value")


class TestOnlyTighten(NotebookTestBase):
    # 任务测试 5:只收权,任何扩权条目被拒
    def test_expand_budget_denied(self):
        self.assertRejected({"tier": "auto", "target": "budget_chat_cards", "value": "hide"},
                            reason_code="note_only_not_executable")

    def test_unlock_pii_denied(self):
        self.assertRejected({"tier": "confirm", "target": "pii_request", "value": "true"},
                            reason_code="note_only_not_executable")

    def test_loosen_touch_policy_denied(self):
        self.assertRejected({"tier": "auto", "target": "touch_policy", "value": "default"},
                            reason_code="note_only_not_executable")


class TestRevertAndApply(NotebookTestBase):
    # 任务测试 9:auto 可撤销,撤销后下一次不再应用(应用 = list active)
    def test_revert_removes_from_active(self):
        e = nb.record({"tier": "auto", "target": "report_order", "value": "a_first"})["entry"]
        active = nb.list_entries()["entries"]
        self.assertEqual([x["id"] for x in active], [e["id"]])
        r = nb.revert(e["id"])
        self.assertTrue(r["changed"])
        self.assertEqual(nb.list_entries()["entries"], [])
        # 幂等:再撤销一次不报错、不再改
        r2 = nb.revert(e["id"])
        self.assertFalse(r2["changed"])

    def test_revert_missing_id(self):
        nb.record({"tier": "auto", "target": "report_order", "value": "a_first"})
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.revert("L-999")
        self.assertEqual(ctx.exception.reason_code, "not_found")


class TestTTL(NotebookTestBase):
    # 任务测试 10:platform_pitfall TTL 到期惰性失效
    def test_pitfall_lazy_expiry(self):
        nb.record({"tier": "auto", "target": "chat_route", "value": "left_menu_chat",
                   "kind": "platform_pitfall", "ttl_days": 30,
                   "reason_code": "platform_route_failure"},
                  now="2026-01-01T00:00:00Z")
        # 未到期:active
        day10 = nb.list_entries(now="2026-01-10T00:00:00Z")
        self.assertEqual(len(day10["entries"]), 1)
        # 到期:惰性过期,不再出现在 active
        day40 = nb.list_entries(now="2026-02-10T00:00:00Z")
        self.assertEqual(day40["entries"], [])
        self.assertIn("L-1", day40["expired_now"])
        # 过期被持久化(status=expired)
        allrows = nb.list_entries(include="all", now="2026-02-10T00:00:00Z")["entries"]
        self.assertEqual(allrows[0]["status"], "expired")

    def test_gc_expires(self):
        nb.record({"tier": "auto", "target": "chat_route", "value": "left_menu_chat",
                   "kind": "platform_pitfall", "ttl_days": 5,
                   "reason_code": "platform_route_failure"},
                  now="2026-01-01T00:00:00Z")
        res = nb.gc(now="2026-01-10T00:00:00Z")
        self.assertIn("L-1", res["expired"])
        self.assertEqual(res["active"], 0)


class TestCapture(NotebookTestBase):
    # 任务测试 11:capture off 不写;已 active 仍生效;管理命令仍可用
    def test_capture_off_does_not_persist(self):
        # 先写一条 active(采集开)
        nb.record({"tier": "auto", "target": "report_order", "value": "a_first"})
        before = nb.list_entries()["entries"]
        self.assertEqual(len(before), 1)
        # 采集关:不落盘
        r = nb.record({"tier": "auto", "target": "report_c_tier", "value": "hide"},
                      capture=False)
        self.assertFalse(r["persisted"])
        self.assertEqual(r["reason_code"], "capture_off")
        after = nb.list_entries()["entries"]
        self.assertEqual(len(after), 1)  # 仍只有原来那条,新的没写
        # 管理命令仍可用:撤销原有 active
        nb.revert(before[0]["id"])
        self.assertEqual(nb.list_entries()["entries"], [])


class TestConfirmPromotion(NotebookTestBase):
    # 任务测试 13:confirm 提议达阈值才出现;未确认不写 active(不能自动升级)
    def test_evidence_count_grows_without_auto_promote(self):
        nb.record({"tier": "auto", "target": "report_c_tier", "value": "hide"})
        nb.record({"tier": "auto", "target": "report_c_tier", "value": "hide"}, observe=True)
        last = nb.record({"tier": "auto", "target": "report_c_tier", "value": "hide"}, observe=True)
        self.assertEqual(last["entry"]["evidence_count"], 3)
        # 仍是 auto,没有被自动写成 confirm 默认
        self.assertEqual(last["entry"]["tier"], "auto")
        confirm_rows = [e for e in nb.list_entries(include="all")["entries"]
                        if e["tier"] == "confirm"]
        self.assertEqual(confirm_rows, [])

    def test_confirm_only_when_explicitly_recorded(self):
        # 固化成默认必须显式记 confirm 条目(default_skip_c_tier),用户点头后
        e = nb.record({"tier": "confirm", "target": "default_skip_c_tier", "value": "true"})["entry"]
        self.assertEqual(e["tier"], "confirm")
        self.assertEqual(e["status"], "active")


class TestDisplayPrefBoundary(NotebookTestBase):
    # 任务测试 14:展示偏好不能隐藏安全/成本/PII/异常/审计(结构性保证)
    def test_display_targets_are_only_presentation_or_routing(self):
        # auto 层只有呈现/内部路由/纪律 5 个 target,不含任何能压制安全/成本/PII 的键
        self.assertEqual(set(nb.AUTO_TARGETS.keys()),
                         {"report_order", "report_c_tier", "report_detail_count",
                          "chat_route", "resume_read_discipline"})

    def test_safety_cost_pii_targets_are_note_only(self):
        # 预算/花卡/PII/换微信电话/薪资/触达档 一律 note_only(不可执行)
        for tgt in ("budget_chat_cards", "budget_greets", "pii_request",
                    "phone_wechat_swap", "salary", "touch_policy"):
            self.assertEqual(nb.canonical_tier(tgt), "note_only")

    def test_whitelists_are_disjoint(self):
        a = set(nb.AUTO_TARGETS)
        c = set(nb.CONFIRM_TARGETS)
        n = set(nb.NOTE_ONLY_TARGETS)
        self.assertEqual(a & c, set())
        self.assertEqual(a & n, set())
        self.assertEqual(c & n, set())


class TestBadTTLSurvives(NotebookTestBase):
    # M1:ttl_days 语义损坏(合法 JSON、坏值,如 "abc"/1e20)→ list/gc/gate-action 都不许崩,
    # 归 corrupt、gate-action 仍 fail-closed。补 test_list_survives_corruption 的"语义坏行"缺口。
    def _write_rows(self, ttl_literal):
        path = os.path.join(self.tmp, "notebook.jsonl")
        good = ('{"id":"L-1","created_at":"2026-01-01T00:00:00Z","tier":"auto",'
                '"kind":"preference","target":"report_order","value":"a_first",'
                '"status":"active","evidence_count":1,"ttl_days":null,'
                '"reason_code":"user_preference","reverted_at":null,"expired_at":null}')
        bad = ('{"id":"L-2","created_at":"2026-01-01T00:00:00Z","tier":"auto",'
               '"kind":"platform_pitfall","target":"chat_route","value":"left_menu_chat",'
               '"status":"active","evidence_count":1,"ttl_days":%s,'
               '"reason_code":"platform_route_failure","reverted_at":null,"expired_at":null}'
               % ttl_literal)
        with open(path, "w", encoding="utf-8") as f:
            f.write(good + "\n")
            f.write(bad + "\n")

    def test_list_survives_bad_ttl_string(self):
        self._write_rows('"abc"')
        res = nb.list_entries(now="2026-06-01T00:00:00Z")   # 旧代码 int("abc") 会崩
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "corrupt")           # 坏行归 corrupt
        self.assertEqual(len(res["entries"]), 2)             # 好行仍用

    def test_gc_survives_bad_ttl_overflow(self):
        self._write_rows("1e20")
        res = nb.gc(now="2026-06-01T00:00:00Z")              # 旧代码 timedelta 会 OverflowError
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "corrupt")

    def test_gate_action_fail_closed_with_bad_ttl(self):
        for lit in ('"abc"', "1e20"):
            self._write_rows(lit)
            # 硬门放行的动作:坏 ttl 不放宽也不崩;notebook 归 corrupt
            r = nb.gate_action("greet", "unknown")
            self.assertEqual(r["decision"], "allowed")       # 初次 greet(硬门原样)
            self.assertEqual(r["notebook_status"], "corrupt")
            # 硬门阻断的动作:坏行绝不放宽
            r2 = nb.gate_action("request_resume", "no_interest")
            self.assertEqual(r2["decision"], "blocked")


class TestBoundaries(NotebookTestBase):
    # L4:payload 带控制键(account_id/capture/include)仍能 record(lint 前剥离,不再是死代码)
    def test_record_with_control_keys_still_records(self):
        r = nb.record({"target": "report_order", "value": "a_first",
                       "account_id": "acct1", "capture": "on", "include": "all"})
        self.assertTrue(r["persisted"])
        self.assertEqual(r["entry"]["target"], "report_order")
        # 控制键没被当成条目字段落盘
        self.assertNotIn("account_id", r["entry"])
        self.assertNotIn("capture", r["entry"])

    # L5:caller 传入的 id 非法格式(非 ^L-[0-9]+$)→ 拒绝、不落盘
    def test_bad_id_format_rejected(self):
        self.assertRejected({"target": "report_order", "value": "a_first", "id": "X-9"},
                            reason_code="bad_id")

    def test_good_id_format_accepted(self):
        e = nb.record({"target": "report_order", "value": "a_first", "id": "L-42"})["entry"]
        self.assertEqual(e["id"], "L-42")

    # L6:bad_account_id
    def test_bad_account_id_rejected(self):
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.notebook_filename("bad id!!")
        self.assertEqual(ctx.exception.reason_code, "bad_account_id")

    # L6:文件级 symlink 拒绝
    @unittest.skipUnless(os.name == "posix", "POSIX symlink only")
    def test_file_symlink_rejected(self):
        target = os.path.join(self.tmp, "real.jsonl")
        with open(target, "w", encoding="utf-8"):
            pass
        os.symlink(target, os.path.join(self.tmp, "notebook.jsonl"))
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.record({"target": "report_order", "value": "a_first"})
        self.assertEqual(ctx.exception.reason_code, "symlink_rejected")

    # L6:record 遇 notebook_unreadable(路径是目录 → 读时 OSError → status=error)
    def test_record_notebook_unreadable(self):
        os.mkdir(os.path.join(self.tmp, "notebook.jsonl"))
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.record({"target": "report_order", "value": "a_first"})
        self.assertEqual(ctx.exception.reason_code, "notebook_unreadable")

    # L6:revert 遇 notebook_corrupt(有损坏行 → 拒绝整写以免丢行)
    def test_revert_notebook_corrupt(self):
        path = os.path.join(self.tmp, "notebook.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("GARBAGE not json\n")
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.revert("L-1")
        self.assertEqual(ctx.exception.reason_code, "notebook_corrupt")

    # L6:非 platform_pitfall 带 ttl_days → bad_ttl
    def test_ttl_on_non_pitfall_rejected(self):
        self.assertRejected({"target": "report_order", "value": "a_first",
                             "kind": "preference", "ttl_days": 30},
                            reason_code="bad_ttl")


if __name__ == "__main__":
    unittest.main()
