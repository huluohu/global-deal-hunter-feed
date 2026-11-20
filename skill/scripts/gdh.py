#!/usr/bin/env python3
"""GLOBAL DEAL HUNTER agent CLI (gdh.py) — 纯 Python 标准库，无第三方依赖。

让 agent（或人）通过命令行查询、筛选、标记、更新 GLOBAL DEAL HUNTER 的羊毛信息。

两种模式（标记都可持久化，区别只在存哪）：
- 服务端模式：连自托管 Docker 版（GDH_BASE_URL），标记存服务端账号下，
  与网页端互通、多设备同步；可提交线索到服务端、触发服务端拉取更新。
- 货架模式（只连公开数据）：读公开货架 deals.json；收藏/无效标记与自提线索
  存在 agent 本机的 ~/.config/gdh-cli/marks.json 与 local-deals.json，
  以条目的有效链接（officialUrl/accessUrl/sourceUrl）为键，跨会话持久有效；
  refresh 为强制重新拉取货架。本地标记只对本机 agent 有效，不同步到服务端。

配置目录：~/.config/gdh-cli/（环境变量 GDH_CLI_HOME 可覆盖）
  config.json / cookies.txt / csrf.txt（均 0600）
环境变量 GDH_BASE_URL / GDH_USERNAME / GDH_PASSWORD 优先于配置文件。
"""
import argparse
import getpass
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.cookiejar import MozillaCookieJar

FEED_URL = "https://raw.githubusercontent.com/huluohu/global-deal-hunter-feed/main/deals.json"
HOME_DIR = os.environ.get("GDH_CLI_HOME") or os.path.join(os.path.expanduser("~"), ".config", "gdh-cli")
CONFIG_PATH = os.path.join(HOME_DIR, "config.json")
COOKIE_PATH = os.path.join(HOME_DIR, "cookies.txt")
CSRF_PATH = os.path.join(HOME_DIR, "csrf.txt")
FEED_CACHE = os.path.join(HOME_DIR, "feed-cache.json")
MARKS_PATH = os.path.join(HOME_DIR, "marks.json")
LOCAL_DEALS_PATH = os.path.join(HOME_DIR, "local-deals.json")
FEED_CACHE_TTL = 600


def die(msg, code=1, **extra):
    out = {"ok": False, "error": msg}
    out.update(extra)
    print(json.dumps(out, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def emit(obj, table=None):
    if table is not None:
        print(table)
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2))


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def deal_key(d):
    """条目的稳定身份：有效链接（官方优先，其次 accessUrl/sourceUrl）。"""
    return d.get("officialUrl") or d.get("accessUrl") or d.get("sourceUrl") or ""


# ---------------- 配置 ----------------

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
        except Exception:
            cfg = {}
    for env_key, cfg_key in (("GDH_BASE_URL", "base_url"), ("GDH_USERNAME", "username"), ("GDH_PASSWORD", "password")):
        if os.environ.get(env_key):
            cfg[cfg_key] = os.environ[env_key]
    if cfg.get("base_url"):
        cfg["base_url"] = cfg["base_url"].rstrip("/")
    return cfg


def save_config(cfg):
    os.makedirs(HOME_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


# ---------------- 本地持久化（货架模式的标记与自提线索） ----------------

def _load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(path, data):
    os.makedirs(HOME_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(path, 0o600)


def load_marks():
    m = _load_json(MARKS_PATH, {})
    m.setdefault("saved", {})
    m.setdefault("invalid", {})
    return m


def load_local_deals():
    return _load_json(LOCAL_DEALS_PATH, [])


def apply_local_state(payload):
    """把本地标记与自提线索合并进货架数据（读时计算，不写回缓存）。"""
    marks = load_marks()
    for d in payload["deals"]:
        k = deal_key(d)
        d["saved"] = k in marks["saved"]
        d["invalid"] = k in marks["invalid"]
    seen = {deal_key(d) for d in payload["deals"]}
    for ld in load_local_deals():
        if deal_key(ld) not in seen:
            payload["deals"].append(ld)
    return payload


# ---------------- 服务端会话 ----------------

class Server:
    def __init__(self, cfg):
        self.base = cfg.get("base_url")
        self.username = cfg.get("username")
        self.password = cfg.get("password")
        self.jar = MozillaCookieJar(COOKIE_PATH)
        if os.path.exists(COOKIE_PATH):
            try:
                self.jar.load(ignore_discard=True, ignore_expires=True)
            except Exception:
                pass
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""
        if os.path.exists(CSRF_PATH):
            self.csrf = open(CSRF_PATH, encoding="utf-8").read().strip()

    def _save_session(self):
        os.makedirs(HOME_DIR, exist_ok=True)
        self.jar.save(ignore_discard=True, ignore_expires=True)
        os.chmod(COOKIE_PATH, 0o600)
        with open(CSRF_PATH, "w", encoding="utf-8") as f:
            f.write(self.csrf)
        os.chmod(CSRF_PATH, 0o600)

    def request(self, method, path, json_body=None, form=None):
        url = self.base + path
        data = None
        headers = {}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if method in ("POST", "DELETE") and self.csrf and form is None:
            headers["X-CSRF-Token"] = self.csrf
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            resp = self.opener.open(req, timeout=30)
            return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def login(self):
        if not self.base:
            die("未配置服务端地址（GDH_BASE_URL 或 gdh.py setup）", code=2)
        if not self.username or not self.password:
            die("未配置账号密码（GDH_USERNAME/GDH_PASSWORD 或 gdh.py setup）", code=2)
        status, html = self.request("GET", "/login")
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        if not m:
            die(f"登录页未取到 CSRF 令牌（HTTP {status}），服务端地址可能不对")
        self.request("POST", "/login", form={
            "username": self.username, "password": self.password, "csrf_token": m.group(1)})
        status, html = self.request("GET", "/")
        m = re.search(r'name="csrf-token" content="([^"]+)"', html)
        if not m:
            die("登录失败：用户名或密码不正确，或会话未建立")
        self.csrf = m.group(1)
        self._save_session()
        return True

    def api(self, method, path, json_body=None, retry=True):
        status, body = self.request(method, path, json_body=json_body)
        if status == 401 and retry:
            self.login()
            return self.api(method, path, json_body=json_body, retry=False)
        try:
            data = json.loads(body) if body else {}
        except Exception:
            die(f"服务端返回非 JSON（HTTP {status}）：{body[:200]}")
        if status >= 400:
            die(f"请求失败 HTTP {status}：{data.get('error', body[:200])}")
        return data

    def dashboard(self):
        return self.api("GET", "/api/dashboard")


# ---------------- 货架数据 ----------------

def feed_payload(force=False):
    os.makedirs(HOME_DIR, exist_ok=True)
    payload = None
    if not force and os.path.exists(FEED_CACHE) and time.time() - os.path.getmtime(FEED_CACHE) < FEED_CACHE_TTL:
        payload = _load_json(FEED_CACHE, None)
    if payload is None:
        try:
            with urllib.request.urlopen(FEED_URL, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            die(f"读取公开货架失败：{e}")
        deals = data.get("deals", [])
        for d in deals:
            d.setdefault("status", "active")
        payload = {"deals": deals, "categories": data.get("categories", []),
                   "generatedAt": data.get("generatedAt", ""), "count": data.get("count", len(deals))}
        with open(FEED_CACHE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    return apply_local_state(payload)


# ---------------- 筛选 ----------------

def parse_dt(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def deal_title(d):
    return d.get("titleZh") or d.get("title") or ""


def compact(d):
    return {
        "id": d.get("id"),
        "key": deal_key(d),
        "title": deal_title(d),
        "titleEn": d.get("titleEn") or "",
        "vendor": d.get("vendor") or "",
        "category": d.get("category") or "",
        "market": d.get("market") or "",
        "regions": d.get("regionsZh") or d.get("regions") or "",
        "regionCodes": d.get("regionCodes") or [],
        "freeType": d.get("freeType") or "",
        "offer": d.get("offerZh") or d.get("offer") or "",
        "valueText": d.get("valueTextZh") or d.get("valueText") or "",
        "valueUsd": d.get("valueUsd"),
        "verified": bool(d.get("verified")),
        "saved": bool(d.get("saved")),
        "invalid": bool(d.get("invalid")),
        "status": d.get("status") or "active",
        "origin": d.get("origin") or "",
        "endsAt": d.get("endsAt") or "",
        "collectedAt": d.get("collectedAt") or "",
        "accessUrl": d.get("accessUrl") or d.get("officialUrl") or d.get("sourceUrl") or "",
        "linkType": d.get("linkType") or "",
        "sourceName": d.get("sourceName") or "",
    }


def apply_filters(deals, args):
    out = []
    now = datetime.now(timezone.utc)
    q = (getattr(args, "query", "") or "").lower()
    for d in deals:
        if getattr(args, "all", False) is not True:
            if d.get("status") != "active":
                continue
            if (getattr(args, "include_invalid", False) is not True
                    and getattr(args, "invalid_only", False) is not True
                    and d.get("invalid")):
                continue
        if q:
            hay = " ".join(str(d.get(k) or "") for k in
                           ("title", "titleZh", "titleEn", "vendor", "offer", "offerZh", "offerEn", "sourceName")).lower()
            if q not in hay:
                continue
        if getattr(args, "category", None) and d.get("category") != args.category:
            continue
        if getattr(args, "market", None) and d.get("market") != args.market:
            continue
        if getattr(args, "region", None) and args.region not in (d.get("regionCodes") or []):
            continue
        if getattr(args, "free_type", None) and d.get("freeType") != args.free_type:
            continue
        if getattr(args, "verified_only", False) and not d.get("verified"):
            continue
        if getattr(args, "unverified_only", False) and d.get("verified"):
            continue
        if getattr(args, "saved_only", False) and not d.get("saved"):
            continue
        if getattr(args, "invalid_only", False) and not d.get("invalid"):
            continue
        if getattr(args, "min_value", None) is not None and (d.get("valueUsd") or 0) < args.min_value:
            continue
        if getattr(args, "expiring", None) is not None:
            end = parse_dt(d.get("endsAt"))
            if not end or end < now - timedelta(hours=12) or end > now + timedelta(days=args.expiring):
                continue
        out.append(d)
    sort = getattr(args, "sort", "value") or "value"
    if sort == "value":
        out.sort(key=lambda d: (d.get("valueUsd") or 0), reverse=True)
    elif sort == "newest":
        out.sort(key=lambda d: d.get("firstSeenAt") or "", reverse=True)
    elif sort == "collected":
        out.sort(key=lambda d: d.get("collectedAt") or "", reverse=True)
    elif sort == "ending":
        out.sort(key=lambda d: (parse_dt(d.get("endsAt")) is None,
                                parse_dt(d.get("endsAt")) or datetime.max.replace(tzinfo=timezone.utc)))
    return out


def table_of(deals):
    lines = []
    for d in deals:
        c = compact(d)
        flags = ("★" if c["saved"] else "") + ("✗无效" if c["invalid"] else "") + ("✓" if c["verified"] else "")
        end = f" 截止 {c['endsAt'][:10]}" if c["endsAt"] else ""
        ref = c["id"] if c["id"] is not None else "·"
        lines.append(f"#{ref} [{c['category']}] {c['title']}｜{c['offer'][:60]}｜{c['valueText']}{end} {flags}\n    {c['accessUrl']}")
    return "\n".join(lines) if lines else "（无结果）"


def resolve_ref(deals, ref):
    """按引用找条目：纯数字 → 服务端 id；否则按有效链接精确匹配，再退而求其次唯一子串匹配。"""
    ref = str(ref).strip()
    if ref.isdigit():
        for d in deals:
            if d.get("id") == int(ref):
                return d
    for d in deals:
        if deal_key(d) == ref:
            return d
    hits = [d for d in deals if ref and ref in deal_key(d)]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        die(f"引用 {ref} 命中多条，请用完整链接", code=2)
    die(f"未找到引用 {ref} 对应的条目", code=2)


# ---------------- 数据源 ----------------

def get_source(cfg):
    """返回 (payload, server_or_None)。服务端模式 payload 来自 dashboard；货架模式来自公开 feed + 本地状态。"""
    if cfg.get("base_url"):
        srv = Server(cfg)
        data = srv.dashboard()
        return {"deals": data.get("deals", []), "categories": data.get("categories", []),
                "stats": data.get("stats", {}), "lastRun": data.get("lastRun")}, srv
    payload = feed_payload()
    payload["stats"] = {}
    return payload, None


# ---------------- 命令 ----------------

def cmd_setup(args):
    cfg = load_config()
    base = args.base_url or cfg.get("base_url") or input("服务端地址（如 http://192.168.1.10:3003）: ").strip()
    user = args.username or cfg.get("username") or input("用户名: ").strip()
    pw = os.environ.get("GDH_PASSWORD") or cfg.get("password") or getpass.getpass("密码（输入不回显）: ")
    cfg.update({"base_url": base.rstrip("/"), "username": user, "password": pw})
    save_config(cfg)
    srv = Server(cfg)
    srv.login()
    status = srv.api("GET", "/api/sync/status")
    emit({"ok": True, "message": "配置已保存并登录成功", "base_url": cfg["base_url"],
          "username": user, "appVersion": status.get("appVersion"), "total": status.get("total")})


def cmd_status(args):
    cfg = load_config()
    if cfg.get("base_url"):
        srv = Server(cfg)
        st = srv.api("GET", "/api/sync/status")
        dash = srv.dashboard()
        emit({"ok": True, "mode": "server", "base_url": cfg["base_url"],
              "appVersion": st.get("appVersion"), "total": st.get("total"),
              "byOrigin": st.get("byOrigin"), "stats": dash.get("stats", {}),
              "lastRun": dash.get("lastRun")})
    else:
        payload = feed_payload()
        marks = load_marks()
        emit({"ok": True, "mode": "feed-local", "feedGeneratedAt": payload.get("generatedAt"),
              "count": payload.get("count"),
              "localMarks": {"saved": len(marks["saved"]), "invalid": len(marks["invalid"])},
              "localDeals": len(load_local_deals()),
              "marksFile": MARKS_PATH})


def cmd_list(args):
    cfg = load_config()
    payload, _ = get_source(cfg)
    deals = apply_filters(payload["deals"], args)
    total = len(deals)
    offset = args.offset or 0
    page = deals[offset:offset + args.limit] if args.limit else deals[offset:]
    if args.table:
        emit({"ok": True}, table=table_of(page))
    else:
        emit({"ok": True, "total": total, "returned": len(page), "deals": [compact(d) for d in page]})


def cmd_show(args):
    cfg = load_config()
    payload, _ = get_source(cfg)
    d = resolve_ref(payload["deals"], args.ref)
    emit({"ok": True, "deal": d})


def cmd_categories(args):
    cfg = load_config()
    payload, _ = get_source(cfg)
    counts = {}
    for d in payload["deals"]:
        if d.get("status") == "active":
            counts[d.get("category") or ""] = counts.get(d.get("category") or "", 0) + 1
    cats = [{"key": c.get("key"), "zh": c.get("zh"), "en": c.get("en"), "active": counts.get(c.get("key"), 0)}
            for c in payload.get("categories", [])]
    emit({"ok": True, "categories": cats})


def cmd_mark(args, kind):
    """收藏（saved）/ 无效（invalid）标记，幂等。服务端模式走 API，货架模式写本地 marks.json。"""
    cfg = load_config()
    payload, srv = get_source(cfg)
    target = resolve_ref(payload["deals"], args.ref)
    want = not args.off
    current = bool(target.get(kind))
    if srv is not None:
        if target.get("id") is None:
            die("该条目不在服务端库中，无法写服务端标记", code=2)
        if current == want:
            emit({"ok": True, "mode": "server", "id": target["id"], kind: current,
                  "changed": False, "title": deal_title(target)})
            return
        path = "/api/toggle-saved" if kind == "saved" else "/api/toggle-invalid"
        res = srv.api("POST", path, json_body={"id": target["id"]})
        emit({"ok": True, "mode": "server", "id": target["id"], kind: bool(res.get(kind)),
              "changed": True, "title": deal_title(target)})
        return
    key = deal_key(target)
    if not key:
        die("该条目没有可用链接，无法建立本地标记", code=2)
    marks = load_marks()
    changed = False
    if want and key not in marks[kind]:
        marks[kind][key] = {"at": now_iso(), "title": deal_title(target)}
        changed = True
    elif not want and key in marks[kind]:
        del marks[kind][key]
        changed = True
    if changed:
        _save_json(MARKS_PATH, marks)
    emit({"ok": True, "mode": "local", "key": key, kind: want if changed else current,
          "changed": changed, "title": deal_title(target), "marksFile": MARKS_PATH})


def cmd_marks(args):
    marks = load_marks()
    emit({"ok": True, "marksFile": MARKS_PATH,
          "saved": [{"key": k, **v} for k, v in marks["saved"].items()],
          "invalid": [{"key": k, **v} for k, v in marks["invalid"].items()]})


def cmd_submit(args):
    cfg = load_config()
    if cfg.get("base_url"):
        srv = Server(cfg)
        body = {"title": args.title, "officialUrl": args.url}
        for attr, field in (("category", "category"), ("offer", "offer"), ("regions", "regions"), ("market", "market")):
            if getattr(args, attr):
                body[field] = getattr(args, attr)
        res = srv.api("POST", "/api/submit", json_body=body)
        emit({"ok": True, "mode": "server", "submitted": res,
              "note": "提交的是未核实线索（verified=false），请勿据此付款或充值"})
        return
    locals_ = load_local_deals()
    if any(deal_key(d) == args.url for d in locals_):
        die("本地线索里已有同一链接", code=2)
    payload = feed_payload()
    if any(deal_key(d) == args.url for d in payload["deals"]):
        die("货架上已有同一链接的条目", code=2)
    deal = {
        "title": args.title, "titleZh": args.title, "vendor": "",
        "category": args.category or "other", "market": args.market or "global",
        "offer": args.offer or "", "offerZh": args.offer or "",
        "valueText": "", "valueUsd": None, "freeType": "mixed",
        "conditions": "本地提交线索，待核实", "regions": args.regions or "待核实",
        "regionCodes": [], "startsAt": None, "endsAt": None, "steps": [],
        "officialUrl": args.url, "accessUrl": args.url, "linkType": "official",
        "sourceName": "本地提交", "sourceUrl": args.url, "verified": False,
        "status": "active", "saved": False, "invalid": False,
        "firstSeenAt": now_iso(), "collectedAt": now_iso(),
        "riskNote": "本地线索未经核实，不要据此付款或充值", "origin": "local",
    }
    locals_.append(deal)
    _save_json(LOCAL_DEALS_PATH, locals_)
    emit({"ok": True, "mode": "local", "submitted": {"key": args.url, "verified": False},
          "note": "已存为本地线索（仅本机可见），未核实，请勿据此付款或充值"})


def cmd_refresh(args):
    cfg = load_config()
    if cfg.get("base_url"):
        srv = Server(cfg)
        res = srv.api("POST", "/api/sync/pull")
        emit({"ok": True, "mode": "server", "pull": res})
    else:
        payload = feed_payload(force=True)
        emit({"ok": True, "mode": "feed-local", "count": payload.get("count"),
              "feedGeneratedAt": payload.get("generatedAt"), "note": "已强制重新拉取公开货架"})


def main():
    ap = argparse.ArgumentParser(prog="gdh.py", description="GLOBAL DEAL HUNTER agent CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("setup", help="配置服务端地址与账号并登录（可选，不配则为货架+本地标记模式）")
    p.add_argument("--base-url"); p.add_argument("--username")
    p.set_defaults(fn=cmd_setup)

    p = sub.add_parser("status", help="连接与数据概况")
    p.set_defaults(fn=cmd_status)

    for name in ("list", "search"):
        p = sub.add_parser(name, help="查询/筛选羊毛")
        if name == "search":
            p.add_argument("query")
        p.add_argument("--category"); p.add_argument("--market")
        p.add_argument("--region", help="地区代码，如 cn/us/global")
        p.add_argument("--free-type", dest="free_type")
        p.add_argument("--verified-only", action="store_true")
        p.add_argument("--unverified-only", action="store_true")
        p.add_argument("--saved-only", action="store_true")
        p.add_argument("--invalid-only", action="store_true")
        p.add_argument("--include-invalid", action="store_true", help="包含已标记无效的条目")
        p.add_argument("--all", action="store_true", help="包含已归档与无效条目")
        p.add_argument("--expiring", type=float, help="N 天内到期")
        p.add_argument("--min-value", type=float, dest="min_value", help="最低估值（USD）")
        p.add_argument("--sort", choices=["value", "newest", "collected", "ending"], default="value")
        p.add_argument("--limit", type=int, default=20)
        p.add_argument("--offset", type=int, default=0)
        p.add_argument("--table", action="store_true", help="人类可读表格输出")
        p.set_defaults(fn=cmd_list)

    p = sub.add_parser("show", help="看一条羊毛的完整详情（引用：服务端 id 或链接）")
    p.add_argument("ref")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("categories", help="分类清单与在架数量")
    p.set_defaults(fn=cmd_categories)

    for name, kind in (("save", "saved"), ("invalid", "invalid")):
        p = sub.add_parser(name, help=("收藏/取消收藏" if kind == "saved" else "标记无效/恢复有效"))
        p.add_argument("ref", help="服务端 id 或条目链接（list 输出的 key/accessUrl）")
        p.add_argument("--off", action="store_true", help="取消标记（默认为打上标记）")
        p.set_defaults(fn=lambda a, k=kind: cmd_mark(a, k))

    p = sub.add_parser("marks", help="查看本地标记清单（货架模式）")
    p.set_defaults(fn=cmd_marks)

    p = sub.add_parser("submit", help="提交一条羊毛线索（未核实；无服务端时存本地）")
    p.add_argument("--title", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--category"); p.add_argument("--offer")
    p.add_argument("--regions"); p.add_argument("--market")
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("refresh", help="更新数据：服务端模式触发拉取，货架模式强制刷新货架缓存")
    p.set_defaults(fn=cmd_refresh)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
