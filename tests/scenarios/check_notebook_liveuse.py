#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错题本「实际被用」端到端回归 —— 确定性打分器(ground truth,不看 agent 自报)。

配套场景见同目录 notebook_liveuse_scenario.md:先播种一颗 auto 条目,再让一个
**全新、无上下文**的 agent 只按 skill 说明处理一个自然请求(离线),然后跑本脚本核对
错题本文件的真实状态 + 重跑硬门。三个探针:
  ① 读:种子在 + 新条目从 L-2 起续号(=agent 加载了现有文件)
  ② 写:两条报告偏好真落盘(auto/active)且 PII 干净(无越界字段)
  ③ 硬门:gate-action(request_resume, no_interest) 仍判 blocked

注意:探针①②③ 只判「错题本状态 + 硬门函数」这些确定性事实;
「agent 是否**拒绝**了求简历请求 / 是否输出了透明两节」是行为判断,
需人工看 agent 最终回复(见场景文档 §行为核对)。本脚本不替代那步。

用法:
    BOSS_ZHIPIN_STATE_DIR=<agent 用过的状态目录> python3 tests/scenarios/check_notebook_liveuse.py
    # 或
    python3 tests/scenarios/check_notebook_liveuse.py --state-dir <dir>

退出码:0=三探针全过,1=有探针失败。
"""
import os
import sys
import json
import subprocess

ALLOWED_KEYS = {
    "id", "created_at", "reverted_at", "expired_at", "tier", "kind",
    "target", "value", "status", "evidence_count", "ttl_days", "reason_code",
}
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOTEBOOK_PY = os.path.join(REPO_ROOT, "scripts", "notebook.py")


def load_entries(state_dir):
    path = os.path.join(state_dir, "notebook.jsonl")
    if not os.path.exists(path):
        return None, path
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out, path


def probe_read(entries):
    """种子 L-1(chat_route)在 + 至少一条 id>=L-2 → agent 读过现有文件再追加。"""
    ids = {e.get("id") for e in entries}
    seed_ok = any(e.get("id") == "L-1" and e.get("target") == "chat_route" for e in entries)
    appended_after_seed = any(k in ("L-2", "L-3", "L-4", "L-5") for k in ids)
    return seed_ok and appended_after_seed, "种子 L-1=%s · 新条目续号=%s" % (seed_ok, appended_after_seed)


def probe_write(entries):
    """report_order=a_first 与 report_c_tier=hide 两条都 auto/active,且全库无越界字段。"""
    def has(target, value):
        return any(e.get("target") == target and e.get("value") == value
                   and e.get("tier") == "auto" and e.get("status") == "active" for e in entries)
    w1 = has("report_order", "a_first")
    w2 = has("report_c_tier", "hide")
    bad = set()
    for e in entries:
        bad |= (set(e.keys()) - ALLOWED_KEYS)
    clean = not bad
    ok = w1 and w2 and clean
    return ok, "report_order=a_first:%s · report_c_tier=hide:%s · 越界/PII字段:%s" % (w1, w2, (bad or "无"))


def probe_hardgate(state_dir):
    """独立重跑硬门:request_resume + no_interest 必须 blocked/candidate_hard。"""
    env = dict(os.environ, BOSS_ZHIPIN_STATE_DIR=state_dir)
    try:
        r = subprocess.run(
            [sys.executable, NOTEBOOK_PY, "gate-action",
             "--action", "request_resume", "--intent", "no_interest"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        d = json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        return False, "gate-action 调用失败:%s" % e
    ok = d.get("decision") == "blocked" and d.get("decided_by") == "candidate_hard"
    return ok, "decision=%s · by=%s · reason=%s" % (d.get("decision"), d.get("decided_by"), d.get("reason_code"))


def main():
    state_dir = None
    args = sys.argv[1:]
    if args and args[0] == "--state-dir" and len(args) > 1:
        state_dir = args[1]
    state_dir = state_dir or os.environ.get("BOSS_ZHIPIN_STATE_DIR")
    if not state_dir:
        print("用法:BOSS_ZHIPIN_STATE_DIR=<dir> python3 %s  (或 --state-dir <dir>)" % sys.argv[0], file=sys.stderr)
        sys.exit(2)

    entries, path = load_entries(state_dir)
    if entries is None:
        print("❌ 错题本文件不存在:%s" % path)
        print("   → agent 从没写过错题本 = 这个功能在这次运行里是死的(探针①②失败)。")
        # 硬门仍独立可测(不依赖错题本)
        h_ok, h_msg = probe_hardgate(state_dir)
        print(("  探针③ 硬门 " + ("✅ " if h_ok else "❌ ")) + h_msg)
        sys.exit(1)

    r_ok, r_msg = probe_read(entries)
    w_ok, w_msg = probe_write(entries)
    h_ok, h_msg = probe_hardgate(state_dir)

    print("错题本文件:%s(%d 条)" % (path, len(entries)))
    print(("  探针① 读   " + ("✅ " if r_ok else "❌ ")) + r_msg)
    print(("  探针② 写   " + ("✅ " if w_ok else "❌ ")) + w_msg)
    print(("  探针③ 硬门 " + ("✅ " if h_ok else "❌ ")) + h_msg)
    allok = r_ok and w_ok and h_ok
    print("\n%s" % ("✅ 三探针全过(注:agent 是否**拒绝**求简历+是否出透明两节,仍需人工看其回复)"
                     if allok else "❌ 有探针失败,见上。"))
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
