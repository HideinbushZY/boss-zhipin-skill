#!/usr/bin/env python3
"""
boss-zhipin 策略/账本校验器 —— 跑一轮寻访前先校验,把配置错误挡在早期
(不是等跑到一半才 "linked_job undefined")。

用法:
    python3 validate.py strategies/<name>/          # 校验该策略的 strategy.yaml + ledger.jsonl
    python3 validate.py strategies/asr-engineer-example/

依赖:仅 PyYAML(pip install pyyaml)+ 标准库,不需要 jsonschema。
退出码:0=全过,1=有错。schemas/ 下有对应 JSON Schema 作正式规格参考。
"""
import sys, os, json

try:
    import yaml
except ImportError:
    print("ERROR: 需要 PyYAML —— pip install pyyaml", file=sys.stderr)
    sys.exit(2)

TOUCH_POLICIES = {"report_first", "greet_A_capped", "greet_custom", "full"}
SOURCES = {"recommend", "search", "interaction", "inbound"}
TIERS = {"A", "B", "C", "unscored", "A*", "A*_salary_sensitive", None}
STATUSES = {
    "found", "scored", "greeted", "chatted", "pending-reply", "replied",
    "resume_received", "resume_requested", "contact_exchanged", "interview",
    "hired", "unfit", "no_reply", "unscored", "inbound_msg",
}
errors, warnings = [], []


def err(m): errors.append(m)
def warn(m): warnings.append(m)


def validate_strategy(path):
    with open(path, encoding="utf-8") as f:
        try:
            s = yaml.safe_load(f)
        except yaml.YAMLError as e:
            err(f"strategy.yaml 不是合法 YAML: {e}")
            return None
    if not isinstance(s, dict):
        err("strategy.yaml 顶层应是一个映射(键值对)")
        return None

    if not s.get("name"):
        err("strategy.yaml: 缺 `name`(策略名,必填)")
    mode = s.get("mode")
    if mode is not None and mode != "once":
        err(f"strategy.yaml: `mode`='{mode}' 暂不支持——现只有 once(单次+手动);心跳是阶段三,别提前配")
    if not s.get("linked_job"):
        warn("strategy.yaml: 缺 `linked_job` —— 推荐通道将不可用(§1.5 预检会禁用推荐、只走搜索);确认是有意的")

    hf = s.get("hard_filters")
    if hf is not None and not isinstance(hf, dict):
        err("strategy.yaml: `hard_filters` 应是映射(city/degree/experience …)")

    kw = s.get("keywords")
    if kw is not None and not (isinstance(kw, list) and all(isinstance(g, list) for g in kw)):
        err("strategy.yaml: `keywords` 应是关键词矩阵(list of list),每组是一簇近义词")

    r = s.get("rubric")
    if not isinstance(r, dict):
        err("strategy.yaml: 缺 `rubric`(打分标准,必填,含 must/nice/reject)")
    else:
        if not (isinstance(r.get("must"), list) and r.get("must")):
            err("strategy.yaml: `rubric.must` 应是非空列表(缺一即封顶 B 的硬项)")
        for k in ("nice", "reject"):
            if r.get(k) is not None and not isinstance(r.get(k), list):
                err(f"strategy.yaml: `rubric.{k}` 应是列表")

    tp = s.get("touch_policy", "full")
    if tp not in TOUCH_POLICIES:
        err(f"strategy.yaml: `touch_policy`='{tp}' 非法,应是 {sorted(TOUCH_POLICIES)} 之一")

    b = s.get("budget")
    if not isinstance(b, dict):
        err("strategy.yaml: 缺 `budget`(必填;内部 greets_per_day/chat_cards 等字段有默认值)")
    else:
        for k in ("greets_per_day", "chat_cards"):
            if k in b and not isinstance(b[k], int):
                err(f"strategy.yaml: `budget.{k}` 应是整数")
        # 🔴 畅聊卡 PII 捆绑同意闸:chat_cards>0 必须显式 authorize_card_pii_bundle: true
        if isinstance(b.get("chat_cards"), int) and b["chat_cards"] > 0 and b.get("authorize_card_pii_bundle") is not True:
            err("strategy.yaml: `budget.chat_cards`>0 必须同时设 `budget.authorize_card_pii_bundle: true` —— "
                "开聊会自动索要简历/微信/电话(PII 捆绑,碰红线),用户须显式知情授权;不授权就把 chat_cards 设 0")
        bsr = b.get("base_salary_range")
        if bsr is not None and not (isinstance(bsr, list) and len(bsr) == 2 and all(isinstance(x, (int, float)) for x in bsr)):
            err("strategy.yaml: `budget.base_salary_range` 应是 [min,max] 两个数(K)")
        bsfp = b.get("salary_flexibility_pct")
        if bsfp is not None and not (isinstance(bsfp, (int, float)) and 0 <= bsfp <= 50):
            err(f"strategy.yaml: `budget.salary_flexibility_pct` 应是 0-50 的数字,当前:{bsfp}")

    tq = s.get("target_qualified")
    if tq is not None and not isinstance(tq, int):
        err("strategy.yaml: `target_qualified` 应是整数")

    sl = s.get("shared_ledger")
    if sl is not None and not isinstance(sl, str):
        err("strategy.yaml: `shared_ledger` 应是路径字符串(如 strategies/_shared/ledger.jsonl,§12 多岗共享账本)")

    intel = s.get("intelligence")
    if intel is not None:
        if not isinstance(intel, dict):
            err("strategy.yaml: `intelligence` 应是映射(custom_greetings/feedback/salary_leverage)")
        else:
            for feat in ("custom_greetings", "feedback", "salary_leverage", "card_prescreen"):
                f = intel.get(feat)
                if f is not None:
                    if not isinstance(f, dict):
                        err(f"strategy.yaml: `intelligence.{feat}` 应是映射")
                    elif "enabled" in f and not isinstance(f["enabled"], bool):
                        err(f"strategy.yaml: `intelligence.{feat}.enabled` 应是 true/false")
            sl = intel.get("salary_leverage")
            if isinstance(sl, dict) and sl.get("enabled") is True:
                if not (isinstance(s.get("budget"), dict) and s["budget"].get("base_salary_range")):
                    err("strategy.yaml: 开了 salary_leverage 就必须给 `budget.base_salary_range`(破格框架的基准)")
            # 🔴 红线闸:定制招呼语外发必审,require_user_confirmation 恒 true 不可关(schema const:true)
            cg = intel.get("custom_greetings")
            if isinstance(cg, dict):
                if "require_user_confirmation" in cg and cg.get("require_user_confirmation") is not True:
                    err("strategy.yaml: `intelligence.custom_greetings.require_user_confirmation` 恒为 true,不可设 false"
                        "(红线:外发内容逐条用户确认,schema 里是 const:true)")
                if cg.get("enabled") is True and cg.get("require_user_confirmation") is not True:
                    err("strategy.yaml: 开了 custom_greetings 必须显式 `require_user_confirmation: true` —— "
                        "定制招呼语要真实外发,红线要求每条先给用户过目(Y/N/编辑),缺省/false 都不行")
    return s


def validate_ledger(path):
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError as e:
                err(f"ledger.jsonl 第 {i} 行不是合法 JSON: {e}")
                continue
            if not isinstance(c, dict):
                err(f"ledger.jsonl 第 {i} 行应是 JSON 对象,实际是 {type(c).__name__}(半截写坏的行?)")
                continue
            who = c.get("name") or c.get("id") or f"第{i}行"
            for k in ("id", "name", "status"):
                if k not in c:
                    err(f"ledger [{who}]: 缺字段 `{k}`")
            if c.get("tier") not in TIERS:
                err(f"ledger [{who}]: tier='{c.get('tier')}' 非法,应是 {sorted(str(t) for t in TIERS)} 之一")
            if "status" in c and c["status"] not in STATUSES:
                warn(f"ledger [{who}]: status='{c['status']}' 不在已知状态机里({sorted(STATUSES)}) —— 拼错还是新状态?")
            if "score" in c and c["score"] is not None and not isinstance(c["score"], (int, float)):
                err(f"ledger [{who}]: score 应是数字或 null")
            src = c.get("source")
            if src is not None and src not in SOURCES:
                warn(f"ledger [{who}]: source='{src}' 不在已知来源里({sorted(SOURCES)})—— 拼错还是新通道?")
            if "masked" in c and not isinstance(c["masked"], bool):
                err(f"ledger [{who}]: masked 应是 true/false")
            acts = c.get("actions")
            if acts is not None:
                if not isinstance(acts, list):
                    err(f"ledger [{who}]: actions 应是列表")
                else:
                    for j, a in enumerate(acts):
                        if not isinstance(a, dict) or not {"t", "act"} <= set(a):
                            err(f"ledger [{who}]: actions[{j}] 应含至少 {{t, act}}")
                        elif a.get("greeting_mode") is not None and a["greeting_mode"] not in {"custom", "default"}:
                            warn(f"ledger [{who}]: actions[{j}].greeting_mode='{a['greeting_mode']}' 应是 custom/default(§11.1)")
            # §12 多岗共享账本字段(可选,但形状要对——跨岗去重靠它们)
            tj = c.get("touched_jobs")
            if tj is not None:
                if not isinstance(tj, list):
                    err(f"ledger [{who}]: touched_jobs 应是列表([{{job,status,date}}],§12)")
                else:
                    for j, t in enumerate(tj):
                        if not isinstance(t, dict) or not {"job", "status"} <= set(t):
                            err(f"ledger [{who}]: touched_jobs[{j}] 应含至少 {{job, status}}(建议带 date,24h 去重靠它)")
            sg = c.get("status_global")
            if sg is not None and not isinstance(sg, str):
                err(f"ledger [{who}]: status_global 应是字符串(跨岗全局状态,§12)")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    d = sys.argv[1]
    sp = os.path.join(d, "strategy.yaml")
    lp = os.path.join(d, "ledger.jsonl")
    lpe = os.path.join(d, "ledger.example.jsonl")

    s = None
    if os.path.exists(sp):
        s = validate_strategy(sp)
    else:
        err(f"找不到 {sp}")
    if os.path.exists(lp):
        validate_ledger(lp)
    elif os.path.exists(lpe):
        validate_ledger(lpe)
    else:
        warn(f"未找到 ledger.jsonl(首轮会自动建空,可忽略)")

    # §12 共享账本:路径按 skill 根目录解析(= validate.py 自身所在目录,与跑脚本的 cwd 无关),存在则一并校验
    sl = (s or {}).get("shared_ledger")
    if isinstance(sl, str):
        if not sl.strip():
            warn("strategy.yaml: `shared_ledger` 是空字符串——要么删掉该键,要么给真实路径(§12)")
        else:
            root = os.path.dirname(os.path.abspath(__file__))
            slp = sl if os.path.isabs(sl) else os.path.join(root, sl)
            if os.path.isdir(slp):
                err(f"strategy.yaml: `shared_ledger` 指向的是目录不是文件:{sl}(应是 .jsonl 文件路径,§12)")
            elif os.path.exists(slp):
                validate_ledger(slp)
            else:
                warn(f"shared_ledger 指向的 {sl} 尚不存在(首轮会自动建;先确认路径没拼错,§12)")

    for w in warnings:
        print(f"⚠  {w}")
    if errors:
        print(f"\n❌ 校验未过,{len(errors)} 个错误:")
        for e in errors:
            print(f"   • {e}")
        sys.exit(1)
    print(f"\n✅ 校验通过{'(有 %d 条提示)' % len(warnings) if warnings else ''}。")
    sys.exit(0)


if __name__ == "__main__":
    main()
