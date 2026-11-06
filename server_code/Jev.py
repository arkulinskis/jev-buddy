"""Jev requests: validation (shared by the playground and recipes), live runs, and the admin settings for them.

Live runs go to one of two places, picked in Admin -> Jev API:
- "openrouter": TypeSafe's Jev through OpenRouter's Decisions API (needs an OpenRouter key);
- "selfhosted": the site owner's own open-source decision model server (Laya, Kev, jevos, Ollaya...) that speaks
  TypeSafe's POST /v1/systemone format, so the text never goes to TypeSafe or OpenRouter.
Live runs are off until an admin sets one up. Keys live in app_settings (a server-only table) and never reach the
browser; the OpenRouter key is never sent to a self-hosted address. We log each run's size and cost, never the text.
"""
import re
import time
import ipaddress
import datetime as dt

import anvil.server
import anvil.http
from anvil.tables import app_tables

from . import common as C

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = "typesafe/jev-1.13"
TYPES = ("noul", "choice", "score")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_ \-]{0,39}$")
MODEL_RE = re.compile(r"^[~a-z0-9_./:\-]{3,80}$")
MAX_QUESTIONS = 12
MAX_STATE = 12000
PROVIDERS = ("openrouter", "selfhosted")
DEFAULTS = {"key": "", "model": DEFAULT_MODEL, "enabled": False, "daily_cap": 300, "per_user_hour": 30,
            "provider": "openrouter", "base_url": "", "local_key": "", "local_model": ""}
URL_RE = re.compile(r"^https://([A-Za-z0-9.\-]{1,253}|\[[0-9A-Fa-f:]+\])(:\d{1,5})?(/[A-Za-z0-9._~/\-]*)?$")
KEY_RE = re.compile(r"^[A-Za-z0-9_\-\.]{16,300}$")


# ------------------------------------------------------------------------------------------- validation
def _txt(v, limit):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return None
    return C.text(v, limit, multiline=True)


def validate(state, questions):
    """(clean_state, clean_questions, None) or (None, None, "message")."""
    if isinstance(state, (dict, list)):
        import json
        if len(json.dumps(state)) > MAX_STATE:
            return None, None, "The state is too long (keep it under %d characters)." % MAX_STATE
        clean_state = state
    else:
        clean_state = C.text(state, MAX_STATE + 1, multiline=True)
        if not clean_state:
            return None, None, "Add some state: the text Jev should decide about."
        if len(clean_state) > MAX_STATE:
            return None, None, "The state is too long (keep it under %d characters)." % MAX_STATE
    if not isinstance(questions, dict) or not questions:
        return None, None, "Add at least one question."
    if len(questions) > MAX_QUESTIONS:
        return None, None, "Up to %d questions per request here." % MAX_QUESTIONS
    out = {}
    for name, q in questions.items():
        if not isinstance(name, str) or not NAME_RE.match(name):
            return None, None, "Question names use lowercase letters, digits and _ (like is_refund): %r" % str(name)[:40]
        if not isinstance(q, dict) or q.get("type") not in TYPES:
            return None, None, "%s: the type must be noul, choice or score." % name
        instr = _txt(q.get("instructions"), 600)
        if not instr or len(instr) < 3:
            return None, None, "%s: write the instructions (what should Jev decide?)." % name
        t, crit = q["type"], q.get("criteria")
        if t == "noul":
            if crit in (None, {}):
                out[name] = {"type": t, "instructions": instr}
                continue
            if not isinstance(crit, dict) or set(crit.keys()) != {"true", "false"}:
                return None, None, "%s: a noul's criteria need both true and false (or leave both out)." % name
            tr, fa = _txt(crit.get("true"), 300), _txt(crit.get("false"), 300)
            if not tr or not fa:
                return None, None, "%s: describe both the true and the false case." % name
            out[name] = {"type": t, "instructions": instr, "criteria": {"true": tr, "false": fa}}
        elif t == "choice":
            if not isinstance(crit, dict) or not 2 <= len(crit) <= 30:
                return None, None, "%s: a choice needs 2 to 30 options." % name
            opts = {}
            for label, desc in crit.items():
                if not isinstance(label, str) or not LABEL_RE.match(label.strip()):
                    return None, None, "%s: option labels are short words (letters, digits, _ or -): %r" % (name, str(label)[:40])
                opts[label.strip()] = _txt(desc, 300) or None
            if len(opts) < 2:
                return None, None, "%s: a choice needs 2 to 30 different options." % name
            out[name] = {"type": t, "instructions": instr, "criteria": opts}
        else:
            if not isinstance(crit, list) or not 2 <= len(crit) <= 10:
                return None, None, "%s: a score needs 2 to 10 ordered levels." % name
            levels = [_txt(x, 300) for x in crit]
            if not all(levels):
                return None, None, "%s: describe every level of the score." % name
            out[name] = {"type": t, "instructions": instr, "criteria": levels}
    return clean_state, out, None


# ------------------------------------------------------------------------------------------- settings
def settings():
    s = dict(DEFAULTS)
    s.update(C.get_setting("jev", {}) or {})
    return s


def _ready(s):
    """Has the active provider got what it needs (a key for OpenRouter, an address for a self-hosted server)?"""
    return bool(s["base_url"]) if s["provider"] == "selfhosted" else bool(s["key"])


def _live(s):
    return bool(s["enabled"] and _ready(s))


def _endpoint(s):
    if s["provider"] != "selfhosted":
        return ENDPOINT
    base = s["base_url"].rstrip("/")
    return base if base.endswith("/v1/systemone") else base + "/v1/systemone"


def _model(s):
    return s["local_model"] if s["provider"] == "selfhosted" else s["model"]


def check_base_url(url):
    """(clean_url, None) or (None, "message"). Anvil's servers are on the internet: they can't reach localhost or a
    home network, and we only send keys over HTTPS."""
    url = (url or "").strip()
    if not URL_RE.match(url):
        return None, "Paste the HTTPS address of your server, like https://decide.example.com (no spaces or query strings)."
    host = url.split("://", 1)[1].split("/", 1)[0]
    if host.startswith("["):
        host = host[1:host.index("]")]
    elif ":" in host:
        host = host.rsplit(":", 1)[0]
    low = host.lower().rstrip(".")
    if low in ("localhost", "0.0.0.0") or low.endswith((".local", ".localhost", ".internal", ".lan", ".home")):
        return None, ("That address only works on your own network. Anvil runs on the internet: put your server behind "
                      "HTTPS (a reverse proxy or a tunnel) and paste that address.")
    try:
        ip = ipaddress.ip_address(low)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return None, "That is a private or local IP address, which Anvil's servers can't reach. Use a public HTTPS address."
    except ValueError:
        pass
    return url, None


def _runs_since(seconds, user=None):
    since = C.now() - dt.timedelta(seconds=seconds)
    rows = app_tables.jev_runs.search(user=user) if user is not None else app_tables.jev_runs.search()
    return [r for r in rows if r["created"] and r["created"] >= since]


@anvil.server.callable
def jev_status():
    """Whether the playground can run real Jev calls (and what the visitor needs to do)."""
    s = settings()
    live = _live(s)
    out = {"live": live, "model": _model(s) or "open model", "provider": s["provider"], "signed_in": C.me() is not None}
    if live:
        out["daily_left"] = max(0, int(s["daily_cap"]) - len(_runs_since(86400)))
    return out


# ------------------------------------------------------------------------------------------- live run
def _post(s, state, questions):
    body = {"state": state, "questions": questions}
    if _model(s):
        body["model"] = _model(s)
    if s["provider"] == "selfhosted":
        headers = {"Authorization": "Bearer " + s["local_key"]} if s["local_key"] else {}
    else:
        headers = {"Authorization": "Bearer " + s["key"], "X-Title": "Jev Buddy"}
    return anvil.http.request(_endpoint(s), method="POST", data=body, json=True, headers=headers, timeout=25)


SELF_ERRORS = {
    400: "Your server rejected the request (400). Check the question shapes.",
    401: "Your server refused the key (401). Check the server key here and the API key set on the server.",
    403: "Your server refused the key (403).",
    404: "Nothing answers at /v1/systemone on that address (404).",
    413: "The request is too large for your server (413).",
    422: "Your server couldn't use the request (422). Some open models allow fewer options, levels or tokens.",
    429: "Your server is busy (429). Try again in a minute.",
    502: "Your server's proxy got no answer (502). Is the model server running?",
    503: "Your server isn't ready (503). It may still be loading the model.",
    504: "Your server timed out (504).",
}
ROUTER_ERRORS = {
    400: "Jev rejected the request (400). Check the question shapes.", 401: "The OpenRouter key was refused (401).",
    402: "The OpenRouter account is out of credits (402).", 413: "The request is too large (413).",
    429: "Rate limited by OpenRouter (429). Try again in a minute.", 524: "Jev timed out (524). Try again.",
}


def _error_text(e, provider="openrouter"):
    status = getattr(e, "status", None)
    msg = (SELF_ERRORS if provider == "selfhosted" else ROUTER_ERRORS).get(status)
    detail = ""
    content = getattr(e, "content", None)
    if isinstance(content, dict):
        err = content.get("error") or content.get("detail") or ""
        detail = str((err.get("message") or "") if isinstance(err, dict) else err)[:200]
    who = "Your server" if provider == "selfhosted" else "Jev"
    return msg or ("%s didn't answer (%s). %s" % (who, status or "network", detail)).strip()


def _clean_reply(r):
    if not isinstance(r, dict) or not isinstance(r.get("answers"), dict):
        return None
    usage = r.get("usage") or {}
    return {"id": r.get("id"), "model": r.get("model"), "provider": r.get("provider"), "answers": r["answers"],
            "usage": {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                      "cost": usage.get("cost")}}


@anvil.server.callable(require_user=True)
def run_live(state, questions):
    me = C.require_user()
    s = settings()
    if not _live(s):
        return C.fail("Live runs are off on this site. The playground shows a simulation instead.")
    state, questions, err = validate(state, questions)
    if err:
        return C.fail(err)
    if len(_runs_since(3600, me)) >= int(s["per_user_hour"]):
        return C.fail("You've used this hour's live runs. The simulator still works, or try again later.")
    if len(_runs_since(86400)) >= int(s["daily_cap"]):
        return C.fail("Today's shared live runs are used up. The simulator still works; live runs come back tomorrow.")
    t0 = time.time()
    try:
        reply = _clean_reply(_post(s, state, questions))
        error = None if reply else "Unexpected reply from the decisions server."
    except Exception as e:  # anvil.http.HttpError and network errors
        reply, error = None, _error_text(e, s["provider"])
    ms = int((time.time() - t0) * 1000)
    usage = (reply or {}).get("usage") or {}
    app_tables.jev_runs.add_row(user=me, created=C.now(), questions=len(questions), ms=ms, ok=reply is not None,
                                input_tokens=usage.get("input_tokens") or 0, cost=usage.get("cost") or 0, error=error)
    if reply is None:
        return C.fail(error)
    return C.ok(response=reply, ms=ms)


# ------------------------------------------------------------------------------------------- admin
def _admin_view(s):
    runs = list(app_tables.jev_runs.search())
    today = _runs_since(86400)
    return {"has_key": bool(s["key"]), "key_hint": ("…" + s["key"][-4:]) if s["key"] else "", "model": s["model"],
            "provider": s["provider"], "base_url": s["base_url"], "endpoint": _endpoint(s) if _ready(s) else "",
            "has_local_key": bool(s["local_key"]), "local_key_hint": ("…" + s["local_key"][-4:]) if s["local_key"] else "",
            "local_model": s["local_model"], "ready": _ready(s), "enabled": bool(s["enabled"]), "daily_cap": int(s["daily_cap"]), "per_user_hour": int(s["per_user_hour"]),
            "live": _live(s), "runs_today": len(today), "runs_total": len(runs),
            "errors_today": len([r for r in today if not r["ok"]]),
            "cost_total": round(sum((r["cost"] or 0) for r in runs), 6),
            "tokens_total": int(sum((r["input_tokens"] or 0) for r in runs)),
            "avg_ms": int(sum(r["ms"] or 0 for r in runs) / len(runs)) if runs else 0}


@anvil.server.callable(require_user=True)
def admin_jev_settings():
    C.require_admin()
    return _admin_view(settings())


@anvil.server.callable(require_user=True)
def admin_save_jev_settings(data):
    C.require_admin()
    if not isinstance(data, dict):
        return C.fail("Nothing to save.")
    s = settings()
    provider = data.get("provider") or s["provider"]
    if provider not in PROVIDERS:
        return C.fail("Pick OpenRouter or your own server.")
    s["provider"] = provider
    key = C.text(data.get("key"), 300)
    if key:
        if not KEY_RE.match(key):
            return C.fail("That doesn't look like an API key (OpenRouter keys start with sk-or-).")
        s["key"] = key
    model = C.text(data.get("model") or s["model"], 80)
    if not MODEL_RE.match(model):
        return C.fail("The model id looks wrong (for example typesafe/jev-1.13).")
    s["model"] = model
    if "base_url" in data:
        raw = C.text(data.get("base_url"), 300)
        if raw:
            url, err = check_base_url(raw)
            if err:
                return C.fail(err)
            s["base_url"] = url
        else:
            s["base_url"] = ""
    local_key = C.text(data.get("local_key"), 300)
    if local_key:
        if not KEY_RE.match(local_key):
            return C.fail("The server key should be 16 or more letters, digits, - _ or . (the value of LAYA_API_KEY, KEV_API_KEY and so on).")
        s["local_key"] = local_key
    if "local_model" in data:
        lm = C.text(data.get("local_model"), 80) or ""
        if lm and not MODEL_RE.match(lm):
            return C.fail("The model name looks wrong (for example kev-latest or laya:multilingual). Leave it empty if your server hosts one model.")
        s["local_model"] = lm
    try:
        cap, per = int(data.get("daily_cap", s["daily_cap"])), int(data.get("per_user_hour", s["per_user_hour"]))
    except (TypeError, ValueError):
        return C.fail("The limits must be whole numbers.")
    if not (1 <= cap <= 100000 and 1 <= per <= 1000):
        return C.fail("Daily cap 1-100000, per person per hour 1-1000.")
    s["daily_cap"], s["per_user_hour"] = cap, per
    s["enabled"] = bool(data.get("enabled")) and _ready(s)
    C.set_setting("jev", s)
    return C.ok(settings=_admin_view(s))


@anvil.server.callable(require_user=True)
def admin_clear_jev_key(which="openrouter"):
    """Forget the OpenRouter key, or (which="selfhosted") the self-hosted address and its key."""
    C.require_admin()
    s = settings()
    if which == "selfhosted":
        s["base_url"], s["local_key"] = "", ""
    else:
        s["key"] = ""
    s["enabled"] = bool(s["enabled"]) and _ready(s)
    C.set_setting("jev", s)
    return C.ok(settings=_admin_view(s))


@anvil.server.callable(require_user=True)
def admin_test_jev():
    """One tiny real call to the active provider, to check it works (logged like any run)."""
    me = C.require_admin()
    s = settings()
    if not _ready(s):
        return C.fail("Save your server's address first." if s["provider"] == "selfhosted" else "Save an OpenRouter key first.")
    q = {"is_refund": {"type": "noul", "instructions": "Is the customer asking for a refund?",
                       "criteria": {"true": "They want money back.", "false": "They want something else."}}}
    t0 = time.time()
    try:
        reply = _clean_reply(_post(s, "Hi, I was charged twice last week. Can I get one payment back?", q))
        error = None if reply else "Unexpected reply from the decisions server."
    except Exception as e:
        reply, error = None, _error_text(e, s["provider"])
    ms = int((time.time() - t0) * 1000)
    usage = (reply or {}).get("usage") or {}
    app_tables.jev_runs.add_row(user=me, created=C.now(), questions=1, ms=ms, ok=reply is not None,
                                input_tokens=usage.get("input_tokens") or 0, cost=usage.get("cost") or 0, error=error)
    if reply is None:
        return C.fail(error)
    return C.ok(response=reply, ms=ms)
