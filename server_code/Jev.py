"""Jev requests: validation (shared by the playground and recipes), live runs through OpenRouter's
Decisions API, and the admin settings for them.

Live runs are off until an admin pastes an OpenRouter API key in Admin -> Jev API. The key lives in
app_settings (a server-only table) and never reaches the browser. Without it, the playground simulates
answers in the browser and says so. We log each live run's size and cost, never the state text.
"""
import re
import time
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
DEFAULTS = {"key": "", "model": DEFAULT_MODEL, "enabled": False, "daily_cap": 300, "per_user_hour": 30}


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


def _live(s):
    return bool(s["enabled"] and s["key"])


def _runs_since(seconds, user=None):
    since = C.now() - dt.timedelta(seconds=seconds)
    rows = app_tables.jev_runs.search(user=user) if user is not None else app_tables.jev_runs.search()
    return [r for r in rows if r["created"] and r["created"] >= since]


@anvil.server.callable
def jev_status():
    """Whether the playground can run real Jev calls (and what the visitor needs to do)."""
    s = settings()
    live = _live(s)
    out = {"live": live, "model": s["model"], "signed_in": C.me() is not None}
    if live:
        out["daily_left"] = max(0, int(s["daily_cap"]) - len(_runs_since(86400)))
    return out


# ------------------------------------------------------------------------------------------- live run
def _post(key, model, state, questions):
    body = {"model": model, "state": state, "questions": questions}
    headers = {"Authorization": "Bearer " + key, "X-Title": "Jev Buddy"}
    return anvil.http.request(ENDPOINT, method="POST", data=body, json=True, headers=headers, timeout=25)


def _error_text(e):
    status = getattr(e, "status", None)
    msg = {400: "Jev rejected the request (400). Check the question shapes.", 401: "The OpenRouter key was refused (401).",
           402: "The OpenRouter account is out of credits (402).", 413: "The request is too large (413).",
           429: "Rate limited by OpenRouter (429). Try again in a minute.", 524: "Jev timed out (524). Try again."}.get(status)
    detail = ""
    content = getattr(e, "content", None)
    if isinstance(content, dict):
        detail = ((content.get("error") or {}).get("message") or "")[:200]
    return msg or ("Jev didn't answer (%s). %s" % (status or "network", detail)).strip()


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
        reply = _clean_reply(_post(s["key"], s["model"], state, questions))
        error = None if reply else "Unexpected reply from the Decisions API."
    except Exception as e:  # anvil.http.HttpError and network errors
        reply, error = None, _error_text(e)
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
            "enabled": bool(s["enabled"]), "daily_cap": int(s["daily_cap"]), "per_user_hour": int(s["per_user_hour"]),
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
    key = C.text(data.get("key"), 300)
    if key:
        if not re.match(r"^[A-Za-z0-9_\-\.]{16,300}$", key):
            return C.fail("That doesn't look like an API key (OpenRouter keys start with sk-or-).")
        s["key"] = key
    model = C.text(data.get("model") or s["model"], 80)
    if not MODEL_RE.match(model):
        return C.fail("The model id looks wrong (for example typesafe/jev-1.13).")
    s["model"] = model
    try:
        cap, per = int(data.get("daily_cap", s["daily_cap"])), int(data.get("per_user_hour", s["per_user_hour"]))
    except (TypeError, ValueError):
        return C.fail("The limits must be whole numbers.")
    if not (1 <= cap <= 100000 and 1 <= per <= 1000):
        return C.fail("Daily cap 1-100000, per person per hour 1-1000.")
    s["daily_cap"], s["per_user_hour"] = cap, per
    s["enabled"] = bool(data.get("enabled")) and bool(s["key"])
    C.set_setting("jev", s)
    return C.ok(settings=_admin_view(s))


@anvil.server.callable(require_user=True)
def admin_clear_jev_key():
    C.require_admin()
    s = settings()
    s["key"], s["enabled"] = "", False
    C.set_setting("jev", s)
    return C.ok(settings=_admin_view(s))


@anvil.server.callable(require_user=True)
def admin_test_jev():
    """One tiny real call with the saved key, to check it works (logged like any run)."""
    me = C.require_admin()
    s = settings()
    if not s["key"]:
        return C.fail("Save an OpenRouter key first.")
    q = {"is_refund": {"type": "noul", "instructions": "Is the customer asking for a refund?",
                       "criteria": {"true": "They want money back.", "false": "They want something else."}}}
    t0 = time.time()
    try:
        reply = _clean_reply(_post(s["key"], s["model"], "Hi, I was charged twice last week. Can I get one payment back?", q))
        error = None if reply else "Unexpected reply from the Decisions API."
    except Exception as e:
        reply, error = None, _error_text(e)
    ms = int((time.time() - t0) * 1000)
    usage = (reply or {}).get("usage") or {}
    app_tables.jev_runs.add_row(user=me, created=C.now(), questions=1, ms=ms, ok=reply is not None,
                                input_tokens=usage.get("input_tokens") or 0, cost=usage.get("cost") or 0, error=error)
    if reply is None:
        return C.fail(error)
    return C.ok(response=reply, ms=ms)
