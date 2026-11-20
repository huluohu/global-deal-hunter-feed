#!/usr/bin/env python3
"""GLOBAL DEAL HUNTER agent CLI (gdh.py) — 纯 Python 标准库，无第三方依赖。

让 agent（或人）通过命令行查询、筛选、标记、更新自托管版 GLOBAL DEAL HUNTER
的羊毛信息。两种模式：

- 服务端模式（推荐）：连你自托管的 Docker 版（GDH_BASE_URL），走它的登录与
  API，可查询/筛选/收藏/标记无效/提交线索/触发拉取更新。
- 货架模式（只读）：未配置服务端时，直接读公开数据货架 deals.json，
  只能查询/筛选，不能标记与更新。

配置目录：~/.config/gdh-cli/（可用环境变量 GDH_CLI_HOME 覆盖）
  config.json  {base_url, username, password}（0600；密码也可走 GDH_PASSWORD）
  cookies.txt  登录会话（0600）
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

    def request(self, method, path, json_body=None, form=None, raw=False):
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
            body = resp.read().decode("utf-8", "replace")
            return resp.status, body
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
        status, _ = self.request("POST", "/login", form={
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


# ---------------- 货架模式（只读） ----------------

def feed_deals(force=False):
    os.makedirs(HOME_DIR, exist_ok=True)
    if not force and os.path.exists(FEED_CACHE) and time.time() - os.path.getmtime(FEED_CACHE) < FEED_CACHE_TTL:
        try:
            return json.load(open(FEED_CACHE, encoding="utf-8"))
        except Exception:
            pass
    try:
        with urllib.request.urlopen(FEED_URL, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        die(f"读取公开货架失败：{e}")
    deals = data.get("deals", [])
    for d in deals:
        d.setdefault("saved", False)
        d.setdefault("invalid", False)
        d.setdefault("status", "active")
    payload = {"deals": deals, "categories": data.get("categories", []),
               "generatedAt": data.get("generatedAt", ""), "count": data.get("count", len(deals))}
    with open(FEED_CACHE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return payload


# ---------------- 筛选 ----------------

def parse_dt(s):
    if not s:
        return None
    try:
        t = str(s).replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
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
        out.sort(key=lambda d: (d.get("valueUsd") or 0, d.get("id") or 0), reverse=True)
    elif sort == "newest":
        out.sort(key=lambda d: d.get("firstSeenAt") or "", reverse=True)
    elif sort == "collected":
        out.sort(key=lambda d: d.get("collectedAt") or "", reverse=True)
    elif sort == "ending":
        out.sort(key=lambda d: (parse_dt(d.get("endsAt")) is None, parse_dt(d.get("endsAt")) or datetime.max.replace(tzinfo=timezone.utc)))
    return out


def table_of(deals):
    lines = []
    for d in deals:
        c = compact(d)
        flags = ("★" if c["saved"] else "") + ("✗无效" if c["invalid"] else "") + ("✓" if c["verified"] else "")
        end = f" 截止 {c['endsAt'][:10]}" if c["endsAt"] else ""
        lines.append(f"#{c['id'] if c['id'] is not None else '·'} [{c['category']}] {c['title']}｜{c['offer'][:60]}｜{c['valueText']}{end} {flags}\n    {c['accessUrl']}")
    return "\n".join(lines) if lines else "（无结果）"


# ---------------- 命令 ----------------

def get_source(cfg, need_write=False):
    """返回 (deals_payload, server_or_None)。写操作必须有服务端。"""
    if cfg.get("base_url"):
        srv = Server(cfg)
        data = srv.dashboard()
        return {"deals": data.get("deals", []), "categories": data.get("categories", []),
                "stats": data.get("stats", {}), "lastRun": data.get("lastRun")}, srv
    if need_write:
        die("当前是只读货架模式（未配置服务端）：标记/提交/更新需要先 gdh.py setup 配置自托管服务端", code=2)
    payload = feed_deals()
    payload["stats"] = {}
    return payload, None


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
        payload = feed_deals()
        emit({"ok": True, "mode": "feed-readonly", "feedGeneratedAt": payload.get("generatedAt"),
              "count": payload.get("count")})


def cmd_list(args):
    cfg = load_config()
    payload, _ = get_source(cfg)
    deals = apply_filters(payload["deals"], args)
    total = len(deals)
    offset = args.offset or 0
    page = deals[offset:offset + args.limit] if args.limit else deals[offset:]
    rows = [compact(d) for d in page]
    if args.table:
        emit({"ok": True}, table=table_of(page))
    else:
        emit({"ok": True, "total": total, "returned": len(rows), "deals": rows})


def cmd_show(args):
    cfg = load_config()
    payload, _ = get_source(cfg)
    for d in payload["deals"]:
        if d.get("id") == args.id:
            emit({"ok": True, "deal": d})
            return
    die(f"未找到 id={args.id} 的条目", code=2)


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


def _toggle(args, kind):
    """kind: saved|invalid。幂等：先看当前状态，需要才切换。"""
    cfg = load_config()
    payload, srv = get_source(cfg, need_write=True)
    target = None
    for d in payload["deals"]:
        if d.get("id") == args.id:
            target = d
            break
    if target is None:
        die(f"未找到 id={args.id} 的条目", code=2)
    want = args.action == "mark"
    current = bool(target.get(kind))
    if current == want:
        emit({"ok": True, "id": args.id, kind: current, "changed": False,
              "title": deal_title(target)})
        return
    path = "/api/toggle-saved" if kind == "saved" else "/api/toggle-invalid"
    res = srv.api("POST", path, json_body={"id": args.id})
    emit({"ok": True, "id": args.id, kind: bool(res.get(kind)), "changed": True,
          "title": deal_title(target)})


def cmd_submit(args):
    cfg = load_config()
    _, srv = get_source(cfg, need_write=True)
    body = {"title": args.title, "officialUrl": args.url}
    if args.category:
        body["category"] = args.category
    if args.offer:
        body["offer"] = args.offer
    if args.regions:
        body["regions"] = args.regions
    if args.market:
        body["market"] = args.market
    res = srv.api("POST", "/api/submit", json_body=body)
    emit({"ok": True, "submitted": res, "note": "提交的是未核实线索（verified=false），请勿据此付款或充值"})


def cmd_refresh(args):
    cfg = load_config()
    _, srv = get_source(cfg, need_write=True)
    res = srv.api("POST", "/api/sync/pull")
    emit({"ok": True, "pull": res})


def main():
    ap = argparse.ArgumentParser(prog="gdh.py", description="GLOBAL DEAL HUNTER agent CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("setup", help="配置服务端地址与账号并登录")
    p.add_argument("--base-url"); p.add_argument("--username")
    p.set_defaults(fn=cmd_setup)

    p = sub.add_parser("status", help="连接与数据概况")
    p.set_defaults(fn=cmd_status)

    for name in ("list", "search"):
        p = sub.add_parser(name, help="查询/筛选羊毛")
        if name == "search":
            p.add_argument("query")
        p.add_argument("--category"); p.add_argument("--market")
        p.add_argument("--region", help="地区代码，如 cn/us/global（见 categories 或文档）")
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

    p = sub.add_parser("show", help="看一条羊毛的完整详情")
    p.add_argument("id", type=int)
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("categories", help="分类清单与在架数量")
    p.set_defaults(fn=cmd_categories)

    for name, kind in (("save", "saved"), ("invalid", "invalid")):
        p = sub.add_parser(name, help=("收藏/取消收藏" if kind == "saved" else "标记无效/恢复有效"))
        p.add_argument("id", type=int)
        p.add_argument("--off", action="store_true", help="取消标记（默认为打上标记）")
        p.set_defaults(fn=lambda a, k=kind: _toggle(type("A", (), {"id": a.id, "action": "unmark" if a.off else "mark"})(), k))

    p = sub.add_parser("submit", help="提交一条羊毛线索（未核实）")
    p.add_argument("--title", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--category"); p.add_argument("--offer")
    p.add_argument("--regions"); p.add_argument("--market")
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("refresh", help="触发服务端从数据货架拉取最新羊毛")
    p.set_defaults(fn=cmd_refresh)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
