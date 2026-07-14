#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
boss-zhipin 错题本(精简版) —— 本地 · per-user · PII-free 的习惯清单。

设计一句话:错题本 = 一个本地、可读、不含候选人信息的习惯清单;
agent 开跑前读它、照着调**安全的东西**(呈现/内部路由/纪律),被纠正时写它,
每轮报告透明列出"改了啥、怎么撤"。**agent 就是解释器,这里只负责存储 + 校验 + 供给。**

铁律(见 SAFETY.md「错题本红线」):
  · 三层自治:auto(自动应用可逆安全项)/ confirm(会话内一句确认)/ note_only(永不执行,只记建议)。
  · 只收权不扩权:note_only/红线/公平性代理永远写不成 auto/confirm;扩权条目一律拒绝、不落盘。
  · PII-free:候选人姓名/手机/微信/简历/消息正文/securityId 一律拒绝、不落盘。
  · 候选人硬门独立:gate-action 先跑候选人硬门(不依赖错题本),再跑错题本(只会收紧,绝不放宽);
    错题本缺失/损坏 → 外发/花卡/PII 动作 fail-closed(不放宽)。

依赖:仅标准库(不用 SQLite / 第三方)。CLI 只做解析呈现,逻辑都在函数里,默认输出 JSON。
存储:BOSS_ZHIPIN_STATE_DIR → 否则 ~/.boss-zhipin-skill/(**必须在 Skill/仓库目录之外**);
      文件 notebook.jsonl(人类可读、追加写);可选按不透明 account_id 分文件 notebook.<account>.jsonl。
      POSIX 下目录 0700 / 文件 0600;拒绝符号链接;导入模块不建目录;doctor 默认只读。

子命令:init | list | record | revert | gc | reset | gate-action | doctor
时间源可注入(--now ISO / 环境变量 BOSS_ZHIPIN_NOTEBOOK_NOW)便于离线测试。
"""
import sys
import os
import io
import re
import json
import stat
import argparse
import tempfile
import datetime

# ─────────────────────────── 白名单(单一事实来源,与 schemas/notebook-entry.schema.json 对齐) ───────────────────────────

# ① auto —— 自动应用,可逆,绝不外发/绝不花钱(只影响"用户自己看到的" + 内部安全路由)
AUTO_TARGETS = {
    "report_order": {"a_first", "default"},
    "report_c_tier": {"show", "hide"},
    "report_detail_count": "__int_1_50__",          # 整数 1–50
    "chat_route": {"direct_url", "left_menu_chat"},  # 仅在预定义安全路由间选择
    "resume_read_discipline": {"full_read_before_touch", "default"},
}

# ② confirm —— 会话内问一次,用户"好"即固化(改长期默认 或 涉及外发文案)
CONFIRM_TARGETS = {
    "greeting_tone": {"warm", "concise", "formal", "default"},
    "default_skip_c_tier": {"true", "false"},
}

# 公平性代理(永远只能 note_only)
FAIRNESS_PROXIES = {
    "school", "company_fame", "city", "region", "age", "gender", "marital", "employment_gap",
}

# ③ note_only —— 永不可执行,只作报告建议(红线 + 公平性代理都归此层;value 恒 "flagged",不留任何可驱动行为的语义)
NOTE_ONLY_TARGETS = {
    "budget_chat_cards", "budget_greets", "touch_policy",
    "pii_request", "phone_wechat_swap",
    "job_publish_close_delete", "interview_arrange", "salary",
    "contact_selection", "search_keywords", "rubric", "scoring",
} | FAIRNESS_PROXIES

REASON_CODES = {
    "user_preference", "platform_route_failure", "wrong_recipient",
    "duplicate_contact", "message_tone", "report_format",
}
KINDS = {"preference", "platform_pitfall", "correction", "habit"}

# 错题本条目允许出现的字段(additionalProperties:false 的函数层镜像)
ALLOWED_ENTRY_KEYS = {
    "id", "created_at", "reverted_at", "expired_at", "tier", "kind",
    "target", "value", "status", "evidence_count", "ttl_days", "reason_code",
}

# 显式禁字段:自由文本 / 候选人 PII 的常见键名(命中即拒,给清晰原因码)
FORBIDDEN_KEYS = {
    "name", "phone", "mobile", "tel", "telephone", "wechat", "weixin", "wx", "qq", "email",
    "resume", "cv", "message", "msg", "text", "content", "body", "note", "notes",
    "summary", "metadata", "meta", "securityid", "security_id", "secid", "sid",
    "candidate", "geek", "other", "raw", "feedback", "comment", "observed", "expected",
}

PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")   # 中国大陆手机号

# 候选人硬门(独立于错题本)
PROTECTED_ACTIONS = {"greet", "send_custom_message", "follow_up", "request_resume", "use_chat_card"}
# 未确认 interested 前 fail-closed 的四类(初次 greet 不在其列)
POST_CONTACT_ACTIONS = {"send_custom_message", "follow_up", "request_resume", "use_chat_card"}
CANDIDATE_INTENTS = {
    "unknown", "pending_intent_review", "interested", "reject", "no_interest", "do_not_contact",
}
HARD_BLOCK_INTENTS = {"reject", "no_interest", "do_not_contact"}

ACCOUNT_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_DECISION_RANK = {"blocked": 0, "needs_review": 1, "allowed": 2}


class NotebookError(Exception):
    """带原因码的拒绝/错误。reason_code 是稳定机读码,message 面向人。"""

    def __init__(self, reason_code, message):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


# ─────────────────────────── 时间源(可注入) ───────────────────────────

def _now(now=None):
    if isinstance(now, datetime.datetime):
        return now if now.tzinfo else now.replace(tzinfo=datetime.timezone.utc)
    if isinstance(now, str) and now.strip():
        return _parse_dt(now)
    env = os.environ.get("BOSS_ZHIPIN_NOTEBOOK_NOW")
    if env:
        return _parse_dt(env)
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_dt(s):
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(s)
    except ValueError:
        raise NotebookError("bad_time", "无法解析时间(需 ISO8601):%r" % s)
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def _iso(dt):
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────── 存储解析(Skill 目录之外 · 拒符号链接 · 私有权限) ───────────────────────────

def _skill_root():
    # scripts/notebook.py → 上两级 = 仓库/Skill 根
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_state_dir():
    """返回状态目录(不创建)。拒绝落在 Skill/仓库目录之内。"""
    env = os.environ.get("BOSS_ZHIPIN_STATE_DIR")
    if env and env.strip():
        base = os.path.abspath(os.path.expanduser(env.strip()))
    else:
        base = os.path.abspath(os.path.join(os.path.expanduser("~"), ".boss-zhipin-skill"))
    root = os.path.realpath(_skill_root())
    real_base = os.path.realpath(base)
    if real_base == root or real_base.startswith(root + os.sep):
        raise NotebookError(
            "state_dir_in_repo",
            "错题本目录不得落在 Skill/仓库内(更新 Skill 会清掉你的错题本):%s" % base,
        )
    return base


def _guard_state_dir(state_dir):
    """符号链接的状态目录一律拒绝(防止预置软链把写入引到别处)。"""
    if os.path.lexists(state_dir) and os.path.islink(state_dir):
        raise NotebookError("symlink_rejected", "状态目录是符号链接,拒绝:%s" % state_dir)


def ensure_state_dir(state_dir=None):
    """写操作专用:创建目录(0700)、收紧权限。导入模块不会走到这里。"""
    if state_dir is None:
        state_dir = resolve_state_dir()
    _guard_state_dir(state_dir)
    if not os.path.isdir(state_dir):
        os.makedirs(state_dir, mode=0o700, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(state_dir, 0o700)
        except OSError:
            pass
    return state_dir


def notebook_filename(account_id=None):
    if account_id in (None, "", "default"):
        return "notebook.jsonl"
    if not ACCOUNT_RE.match(account_id):
        raise NotebookError("bad_account_id", "account_id 非法(仅 A-Za-z0-9._-,≤64):%r" % account_id)
    return "notebook.%s.jsonl" % account_id


def resolve_notebook_path(account_id=None, state_dir=None):
    if state_dir is None:
        state_dir = resolve_state_dir()
    return os.path.join(state_dir, notebook_filename(account_id))


# ─────────────────────────── 读/写 JSONL ───────────────────────────

def _guard_file(path):
    if os.path.lexists(path) and os.path.islink(path):
        raise NotebookError("symlink_rejected", "错题本文件是符号链接,拒绝:%s" % path)


def _load_raw(path):
    """返回 (entries, status)。status ∈ ok|missing|corrupt|error。损坏时仍返回可解析的好行。"""
    _guard_file(path)
    if not os.path.exists(path):
        return [], "missing"
    entries, corrupt = [], False
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    corrupt = True
                    continue
                if isinstance(obj, dict):
                    entries.append(obj)
                else:
                    corrupt = True
    except (OSError, UnicodeDecodeError):
        return [], "error"
    return entries, ("corrupt" if corrupt else "ok")


def _atomic_write(path, entries):
    _guard_file(path)
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".nb-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
        if os.name == "posix":
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _append_entry(path, entry):
    _guard_file(path)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    if os.name == "posix":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


# ─────────────────────────── PII / 自由文本拦截 ───────────────────────────

def lint_pii(payload):
    """写入前实拦疑似 PII / 自由文本 / 白名单外字段。命中即抛 NotebookError,绝不落盘。"""
    if not isinstance(payload, dict):
        raise NotebookError("bad_payload", "错题本条目应是 JSON 对象")
    for k, v in payload.items():
        kl = str(k).strip().lower()
        if kl in FORBIDDEN_KEYS:
            raise NotebookError("pii_detected", "疑似 PII/自由文本字段被拒(不落盘):%s" % k)
        if kl not in ALLOWED_ENTRY_KEYS:
            raise NotebookError("unknown_field", "白名单外字段被拒(不落盘):%s" % k)
        _scan_value(k, v)


def _scan_value(key, v):
    if isinstance(v, (dict, list)):
        raise NotebookError("bad_value", "字段 %s 不接受嵌套结构(防结构化夹带)" % key)
    if isinstance(v, str):
        if any(ord(ch) > 0x7F for ch in v):
            raise NotebookError("pii_detected", "字段 %s 含非 ASCII 文本(疑似候选人姓名/正文),拒绝" % key)
        if PHONE_RE.search(v):
            raise NotebookError("pii_detected", "字段 %s 含疑似手机号,拒绝" % key)
        if "@" in v:
            raise NotebookError("pii_detected", "字段 %s 含疑似邮箱,拒绝" % key)
        if len(v) > 40:
            raise NotebookError("pii_detected", "字段 %s 过长(疑似消息正文/简历),拒绝" % key)


# ─────────────────────────── 归一化 + 三层白名单 + 只收权 ───────────────────────────

def canonical_tier(target):
    """target 的最高可执行层(= 唯一允许层)。未知 target → None。"""
    if target in AUTO_TARGETS:
        return "auto"
    if target in CONFIRM_TARGETS:
        return "confirm"
    if target in NOTE_ONLY_TARGETS:
        return "note_only"
    return None


def _validate_value(target, value):
    """按 target 校验 value(auto/confirm);返回归一化后的 value。"""
    if target == "report_detail_count":
        try:
            iv = int(value)
        except (TypeError, ValueError):
            raise NotebookError("value_not_allowed", "report_detail_count 需整数 1–50,得到 %r" % value)
        if not (1 <= iv <= 50):
            raise NotebookError("value_not_allowed", "report_detail_count 超范围(1–50):%r" % iv)
        return iv
    allowed = AUTO_TARGETS.get(target) or CONFIRM_TARGETS.get(target)
    sv = value
    if isinstance(sv, bool):
        sv = "true" if sv else "false"
    sv = str(sv)
    if sv not in allowed:
        raise NotebookError(
            "value_not_allowed",
            "target=%s 的 value 只能是 %s,得到 %r" % (target, sorted(allowed), value),
        )
    return sv


def normalize_entry(payload, now=None, next_id=None):
    """把(已过 PII 拦截的)payload 归一化成合法条目;三层白名单 + 只收权在此强制。"""
    target = payload.get("target")
    if not isinstance(target, str) or not target:
        raise NotebookError("missing_target", "缺 target(必须来自白名单)")
    ct = canonical_tier(target)
    if ct is None:
        raise NotebookError("target_not_whitelisted", "target=%r 不在任何白名单里,拒绝" % target)

    req_tier = payload.get("tier", ct)
    if req_tier not in ("auto", "confirm", "note_only"):
        raise NotebookError("bad_tier", "tier 非法:%r" % req_tier)

    # 🔴 只收权不扩权:请求的 tier 不得比该 target 的 canonical 层"更可执行"
    exec_rank = {"note_only": 0, "confirm": 1, "auto": 2}
    if exec_rank[req_tier] > exec_rank[ct]:
        if ct == "note_only":
            reason = "fairness_not_executable" if target in FAIRNESS_PROXIES else "note_only_not_executable"
            raise NotebookError(reason, "target=%s 属 note_only/红线,永远写不成可执行(auto/confirm)" % target)
        raise NotebookError("expand_denied", "拒绝把 target=%s 提到更高自治层(%s>%s),只收权不扩权" % (target, req_tier, ct))
    # 收紧(req_tier < canonical)也不允许错配到别的 target 的层:tier 必须等于 canonical
    if req_tier != ct:
        raise NotebookError("tier_target_mismatch", "target=%s 只能在 %s 层,不能记为 %s" % (target, ct, req_tier))

    tier = ct
    # value
    if tier == "note_only":
        v = payload.get("value", "flagged")
        if v not in (None, "flagged"):
            raise NotebookError("value_not_allowed", "note_only 的 value 恒为 'flagged'(不留可驱动语义),得到 %r" % v)
        value = "flagged"
    else:
        if "value" not in payload:
            raise NotebookError("missing_value", "缺 value")
        value = _validate_value(target, payload["value"])

    kind = payload.get("kind", "preference")
    if kind not in KINDS:
        raise NotebookError("bad_kind", "kind 非法:%r(应是 %s)" % (kind, sorted(KINDS)))

    reason_code = payload.get("reason_code", "user_preference")
    if reason_code not in REASON_CODES:
        raise NotebookError("bad_reason_code", "reason_code 非法:%r(应是 %s)" % (reason_code, sorted(REASON_CODES)))

    # ttl_days 仅 platform_pitfall 用
    ttl_days = payload.get("ttl_days", None)
    if kind == "platform_pitfall":
        if ttl_days is None:
            ttl_days = 30
        try:
            ttl_days = int(ttl_days)
        except (TypeError, ValueError):
            raise NotebookError("bad_ttl", "ttl_days 需整数 1–90:%r" % ttl_days)
        if not (1 <= ttl_days <= 90):
            raise NotebookError("bad_ttl", "ttl_days 超范围(1–90):%r" % ttl_days)
    else:
        if ttl_days is not None:
            raise NotebookError("bad_ttl", "ttl_days 只对 platform_pitfall 有效")
        ttl_days = None

    ev = payload.get("evidence_count", 1)
    try:
        ev = int(ev)
    except (TypeError, ValueError):
        raise NotebookError("bad_evidence", "evidence_count 需整数 ≥1:%r" % ev)
    if ev < 1:
        raise NotebookError("bad_evidence", "evidence_count 需 ≥1:%r" % ev)

    now_dt = _now(now)
    entry = {
        "id": payload.get("id") or next_id or "L-1",
        "created_at": _iso(now_dt),
        "reverted_at": None,
        "expired_at": None,
        "tier": tier,
        "kind": kind,
        "target": target,
        "value": value,
        "status": "active",
        "evidence_count": ev,
        "ttl_days": ttl_days,
        "reason_code": reason_code,
    }
    return entry


def _natural_key(entry):
    return (entry["tier"], entry["target"], str(entry["value"]))


def _next_id(entries):
    mx = 0
    for e in entries:
        m = re.match(r"^L-(\d+)$", str(e.get("id", "")))
        if m:
            mx = max(mx, int(m.group(1)))
    return "L-%d" % (mx + 1)


# ─────────────────────────── 惰性过期 ───────────────────────────

def _apply_lazy_expiry(entries, now=None):
    """platform_pitfall 到期 → status=expired(读取时惰性)。返回被过期的 id 列表。"""
    now_dt = _now(now)
    expired = []
    for e in entries:
        if e.get("status") != "active":
            continue
        if e.get("kind") != "platform_pitfall":
            continue
        ttl = e.get("ttl_days")
        if not ttl:
            continue
        try:
            created = _parse_dt(e["created_at"])
        except Exception:
            continue
        if now_dt >= created + datetime.timedelta(days=int(ttl)):
            e["status"] = "expired"
            e["expired_at"] = _iso(now_dt)
            expired.append(e.get("id"))
    return expired


def load_notebook(account_id=None, expire=True, persist=False, now=None):
    """加载(可惰性过期)。返回 {path,status,entries,expired}。status=corrupt/error 时上层按 fail-closed 处理。"""
    state_dir = resolve_state_dir()
    _guard_state_dir(state_dir)
    path = resolve_notebook_path(account_id, state_dir=state_dir)
    entries, status = _load_raw(path)
    expired = []
    if expire and status in ("ok", "corrupt"):
        expired = _apply_lazy_expiry(entries, now=now)
        # 只在文件完好时把惰性过期写回;损坏文件不重写以免丢数据
        if persist and expired and status == "ok":
            ensure_state_dir(state_dir)
            _atomic_write(path, entries)
    return {"path": path, "status": status, "entries": entries, "expired": expired}


# ─────────────────────────── 命令实现(逻辑层,CLI 只调用) ───────────────────────────

def cmd_init(account_id=None):
    state_dir = ensure_state_dir()
    path = resolve_notebook_path(account_id, state_dir=state_dir)
    _guard_file(path)
    created = False
    if not os.path.exists(path):
        with io.open(path, "a", encoding="utf-8"):
            pass
        if os.name == "posix":
            os.chmod(path, 0o600)
        created = True
    return {"ok": True, "state_dir": state_dir, "path": path, "created": created}


def record(payload, account_id=None, capture=True, observe=False, now=None):
    """归一化 → 三层白名单/只收权/PII 强制 → 幂等追加。capture=off 则校验但不落盘。"""
    lint_pii(payload)                       # PII / 自由文本 / 白名单外字段:先拦,命中不落盘
    # 预归一化(不含最终 id):先做全部校验
    entry = normalize_entry(payload, now=now, next_id="L-0")
    if not capture:
        return {"ok": True, "persisted": False, "reason_code": "capture_off", "entry": entry}

    state_dir = ensure_state_dir()
    path = resolve_notebook_path(account_id, state_dir=state_dir)
    entries, status = _load_raw(path)
    if status == "error":
        raise NotebookError("notebook_unreadable", "错题本不可读,拒绝写入:%s" % path)

    # 幂等:显式 id 已存在 → 原样返回
    pid = payload.get("id")
    if pid:
        for e in entries:
            if e.get("id") == pid:
                return {"ok": True, "persisted": True, "idempotent": True, "entry": e}

    # 幂等:同 (tier,target,value) 的 active 条目已存在 → 不重复落行(仅在文件完好时就地合并,
    # 损坏文件不整写以免丢掉损坏行 → 退化为追加一行,保留原损坏行待用户手动修)
    key = _natural_key(entry)
    for e in entries:
        if status == "ok" and e.get("status") == "active" and _natural_key(e) == key:
            old = int(e.get("evidence_count", 1))
            new = old
            if "evidence_count" in payload:
                new = max(old, int(payload["evidence_count"]))
            elif observe:
                new = old + 1
            if new != old:
                e["evidence_count"] = new
                _atomic_write(path, entries)
                return {"ok": True, "persisted": True, "idempotent": False, "updated": True, "entry": e}
            return {"ok": True, "persisted": True, "idempotent": True, "entry": e}

    # 新条目:分配 id、追加
    entry["id"] = payload.get("id") or _next_id(entries)
    _append_entry(path, entry)
    return {"ok": True, "persisted": True, "idempotent": False, "entry": entry}


def revert(entry_id, account_id=None, now=None):
    if not entry_id:
        raise NotebookError("missing_id", "revert 需要 id(如 L-3)")
    state_dir = resolve_state_dir()
    _guard_state_dir(state_dir)
    path = resolve_notebook_path(account_id, state_dir=state_dir)
    entries, status = _load_raw(path)
    if status in ("missing",):
        raise NotebookError("not_found", "错题本不存在,无 %s 可撤销" % entry_id)
    if status == "error":
        raise NotebookError("notebook_unreadable", "错题本不可读,拒绝改写")
    if status == "corrupt":
        # 整写会丢掉损坏行 → 拒绝,让用户先手动修/删那行(人类可读就是为这个)
        raise NotebookError("notebook_corrupt", "错题本有损坏行,请先手动修复该行再撤销:%s" % path)
    for e in entries:
        if e.get("id") == entry_id:
            if e.get("status") == "reverted":
                return {"ok": True, "changed": False, "entry": e}       # 幂等
            e["status"] = "reverted"
            e["reverted_at"] = _iso(_now(now))
            ensure_state_dir(state_dir)
            _atomic_write(path, entries)
            return {"ok": True, "changed": True, "entry": e}
    raise NotebookError("not_found", "未找到条目 %s" % entry_id)


def gc(account_id=None, now=None):
    state_dir = resolve_state_dir()
    _guard_state_dir(state_dir)
    path = resolve_notebook_path(account_id, state_dir=state_dir)
    entries, status = _load_raw(path)
    if status == "missing":
        return {"ok": True, "expired": [], "active": 0, "status": status}
    if status == "error":
        raise NotebookError("notebook_unreadable", "错题本不可读,gc 跳过")
    expired = _apply_lazy_expiry(entries, now=now)
    if expired and status == "ok":
        ensure_state_dir(state_dir)
        _atomic_write(path, entries)
    active = sum(1 for e in entries if e.get("status") == "active")
    return {"ok": True, "expired": expired, "active": active, "status": status}


def reset(account_id=None):
    state_dir = resolve_state_dir()
    _guard_state_dir(state_dir)
    path = resolve_notebook_path(account_id, state_dir=state_dir)
    _guard_file(path)
    removed = []
    if os.path.exists(path):
        os.remove(path)
        removed.append(path)
    return {"ok": True, "reset": True, "removed": removed}


def list_entries(account_id=None, include="active", now=None):
    nb = load_notebook(account_id, expire=True, persist=True, now=now)
    entries = nb["entries"]
    if include == "all":
        shown = entries
    else:
        shown = [e for e in entries if e.get("status") == "active"]
    return {
        "ok": True,
        "status": nb["status"],
        "path": nb["path"],
        "count": len(shown),
        "expired_now": nb["expired"],
        "entries": shown,
    }


def gate_action(action, candidate_intent, account_id=None, now=None):
    """五类受保护动作的统一判定:先候选人硬门(独立于错题本),再错题本(只会收紧)。

    候选人硬门(独立、错题本解不开):
      reject|no_interest|do_not_contact → blocked(全部五类)
      unknown|pending_intent_review     → 四类后接触动作 needs_review(未确认 interested 前 fail-closed);初次 greet 放行
      interested                        → 硬门放行
    错题本层:只能把 allowed 往 needs_review/blocked 收;绝不放宽。
      错题本缺失/损坏 → 不施加任何收紧、更不放宽硬门(fail-closed)。
    """
    if action not in PROTECTED_ACTIONS:
        raise NotebookError("unknown_action", "未知受保护动作:%r(应是 %s)" % (action, sorted(PROTECTED_ACTIONS)))
    intent = candidate_intent or "unknown"

    # ── 候选人硬门(完全不读错题本) ──
    if intent not in CANDIDATE_INTENTS:
        hard = ("blocked", "invalid_intent")               # 非法意图 → fail-closed
    elif intent in HARD_BLOCK_INTENTS:
        hard = ("blocked", "candidate_intent_hard_block")
    elif intent == "interested":
        hard = ("allowed", "intent_interested")
    else:  # unknown / pending_intent_review
        if action == "greet" and intent == "unknown":
            hard = ("allowed", "initial_greet_ok")
        else:
            hard = ("needs_review", "intent_not_confirmed_interested")

    decision, reason = hard
    layer = "candidate_hard"

    # ── 错题本层(只收紧;fail-closed on error) ──
    notebook_status = "not_consulted"
    try:
        nb = load_notebook(account_id, expire=True, persist=False, now=now)
        notebook_status = nb["status"]
        tighten = _notebook_tightening(nb["entries"], action) if notebook_status in ("ok",) else None
        if tighten is not None:
            t_decision, t_reason = tighten
            if _DECISION_RANK[t_decision] < _DECISION_RANK[decision]:   # 只允许更严
                decision, reason, layer = t_decision, t_reason, "notebook"
        # corrupt/error:不施加收紧,也绝不放宽 → 硬门结论原样保留(fail-closed)
    except NotebookError as e:
        notebook_status = "error:%s" % e.reason_code                    # 硬门结论不受影响

    return {
        "ok": True,
        "action": action,
        "candidate_intent": intent,
        "decision": decision,
        "reason_code": reason,
        "decided_by": layer,
        "hard_gate": {"decision": hard[0], "reason_code": hard[1]},
        "notebook_status": notebook_status,
    }


def _notebook_tightening(entries, action):
    """错题本可施加的收紧(设计上永远只收不放)。当前安全白名单里没有能阻断五类外发的可执行条目,
    故恒返回 None;保留此钩子以显式表达"错题本只能收紧、绝不放宽"的不变式。"""
    return None


def doctor(account_id=None, now=None):
    """默认只读健康检查:不创建任何目录/文件。"""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # 状态目录
    try:
        state_dir = resolve_state_dir()
        add("state_dir_outside_repo", True, state_dir)
    except NotebookError as e:
        add("state_dir_outside_repo", False, e.message)
        return {"ok": False, "checks": checks}

    add("state_dir_exists", os.path.isdir(state_dir), state_dir)
    is_link = os.path.lexists(state_dir) and os.path.islink(state_dir)
    add("state_dir_not_symlink", not is_link, "symlink" if is_link else "regular/absent")
    if os.path.isdir(state_dir) and os.name == "posix":
        mode = stat.S_IMODE(os.stat(state_dir).st_mode)
        add("state_dir_perms_0700", mode == 0o700, oct(mode))

    # 文件
    try:
        path = resolve_notebook_path(account_id, state_dir=state_dir)
    except NotebookError as e:
        add("account_id_valid", False, e.message)
        return {"ok": all(c["ok"] for c in checks), "checks": checks}

    file_link = os.path.lexists(path) and os.path.islink(path)
    add("notebook_not_symlink", not file_link, "symlink" if file_link else "regular/absent")
    if not os.path.exists(path):
        add("notebook_present", True, "缺失(首轮正常,尚未记录任何习惯)")
        overall = all(c["ok"] for c in checks)
        return {"ok": overall, "state_dir": state_dir, "path": path, "checks": checks,
                "counts": {"active": 0, "expired": 0, "reverted": 0}}

    entries, status = _load_raw(path)
    add("notebook_parseable", status in ("ok", "missing"), status)
    if os.name == "posix" and not file_link:
        mode = stat.S_IMODE(os.stat(path).st_mode)
        add("notebook_perms_0600", mode == 0o600, oct(mode))
    counts = {
        "active": sum(1 for e in entries if e.get("status") == "active"),
        "expired": sum(1 for e in entries if e.get("status") == "expired"),
        "reverted": sum(1 for e in entries if e.get("status") == "reverted"),
    }
    overall = all(c["ok"] for c in checks)
    return {"ok": overall, "state_dir": state_dir, "path": path, "status": status,
            "checks": checks, "counts": counts}


# ─────────────────────────── CLI(只做解析呈现,不放逻辑) ───────────────────────────

def _read_input(arg):
    if not arg:
        return {}
    if arg == "-":
        raw = sys.stdin.read()
    else:
        with io.open(arg, "r", encoding="utf-8") as f:
            raw = f.read()
    raw = raw.strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise NotebookError("bad_payload", "--input 应是 JSON 对象")
    return data


def _emit(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2))
    return code


def _capture_flag(payload, args):
    cap = getattr(args, "capture", None)
    if cap is not None:
        return cap != "off"
    v = payload.get("capture")
    if v in (False, "off"):
        return False
    return True


def build_parser():
    p = argparse.ArgumentParser(prog="notebook.py", description="boss-zhipin 错题本(本地 · PII-free)")
    p.add_argument("--now", help="注入当前时间(ISO8601),测试用")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, with_input=True):
        if with_input:
            sp.add_argument("--input", help="JSON 载荷:'-'=stdin 或文件路径(不接受原始反馈作位置参数)")
        sp.add_argument("--account", help="不透明 account_id(多账号分文件)")

    common(sub.add_parser("init", help="创建状态目录 + 空错题本(幂等)"))
    lp = sub.add_parser("list", help="列出 active(--all 含全部)")
    common(lp)
    lp.add_argument("--all", action="store_true", help="含 reverted/expired")

    rp = sub.add_parser("record", help="归一化并追加一条(幂等,受三层白名单强制)")
    common(rp)
    rp.add_argument("--capture", choices=["on", "off"], help="off 则校验但不落盘")
    rp.add_argument("--observe", action="store_true", help="同键 active 条目 evidence_count +1(观察计数)")

    vp = sub.add_parser("revert", help="撤销一条(status=reverted,幂等)")
    common(vp)
    vp.add_argument("--id", help="条目 id,如 L-3")

    common(sub.add_parser("gc", help="惰性过期 platform_pitfall(写 status=expired)"))
    common(sub.add_parser("reset", help="删除错题本文件(清空,幂等)"))

    gp = sub.add_parser("gate-action", help="五类受保护动作判定:先硬门后错题本")
    common(gp)
    gp.add_argument("--action", choices=sorted(PROTECTED_ACTIONS))
    gp.add_argument("--intent", choices=sorted(CANDIDATE_INTENTS))

    common(sub.add_parser("doctor", help="只读健康检查(不建目录)"))
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        payload = _read_input(getattr(args, "input", None))
        account = getattr(args, "account", None) or payload.get("account_id")
        now = args.now

        if args.cmd == "init":
            return _emit(cmd_init(account))
        if args.cmd == "list":
            inc = "all" if getattr(args, "all", False) or payload.get("include") == "all" else "active"
            return _emit(list_entries(account, include=inc, now=now))
        if args.cmd == "record":
            return _emit(record(payload, account_id=account,
                                 capture=_capture_flag(payload, args),
                                 observe=getattr(args, "observe", False), now=now))
        if args.cmd == "revert":
            eid = getattr(args, "id", None) or payload.get("id")
            return _emit(revert(eid, account_id=account, now=now))
        if args.cmd == "gc":
            return _emit(gc(account, now=now))
        if args.cmd == "reset":
            return _emit(reset(account))
        if args.cmd == "gate-action":
            action = getattr(args, "action", None) or payload.get("action")
            intent = getattr(args, "intent", None) or payload.get("candidate_intent")
            if not action:
                raise NotebookError("missing_action", "gate-action 需 --action 或 input.action")
            return _emit(gate_action(action, intent, account_id=account, now=now))
        if args.cmd == "doctor":
            return _emit(doctor(account, now=now))
        raise NotebookError("unknown_command", "未知命令:%s" % args.cmd)
    except NotebookError as e:
        return _emit({"ok": False, "reason_code": e.reason_code, "error": e.message}, code=1)
    except json.JSONDecodeError as e:
        return _emit({"ok": False, "reason_code": "bad_json", "error": str(e)}, code=1)


if __name__ == "__main__":
    sys.exit(main())
