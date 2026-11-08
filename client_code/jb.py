"""Python's door to the Jev Buddy engine (theme/assets/jb.js + jb-content.js, window.JB) and the playground's rules.

Engine output (code blocks with tabs + copy, answer cards, probability bars, tables, guide chapters, the open-source
sections) is HTML that Components/Rich shows. Data crosses as JSON (real Python dicts and lists, never JS proxies).

    examples(), example(slug), cats()          the 12 use cases and the recipe categories
    code(blocks, title), gen_blocks(req), req_json(req), answer_card(name, a), probs(p), callout(), table()
    simulate(state, questions)                 the in-browser simulator (keyword overlap, NOT Jev) -> response dict
    from_map / to_req / problems / blank       the playground's draft <-> a Jev request, with the same checks as before
"""
import json
import re

from anvil.js import window

PRICE_PER_M = 0.042   # USD per million input tokens on OpenRouter, Oct 2026 (output tokens are free); also in jb.js
MODEL = "typesafe/jev-1.13"
ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_ \-]{0,39}$")
_cache: dict = {}


def to_js(value):
    return window.JSON.parse(json.dumps(value))


def to_py(value):
    return json.loads(window.JSON.stringify(value))


def store_get(key, default=None):
    """This browser's storage as real Python values (UI.store.get gives JS proxies). Keys as in the JS version."""
    try:
        raw = window.localStorage.getItem("jevbuddy." + key)
        return default if raw is None else json.loads(raw)
    except Exception:
        return default


def store_set(key, value):
    try:
        window.localStorage.setItem("jevbuddy." + key, json.dumps(value))
    except Exception:
        pass


def n(x):
    """A number the way JavaScript prints it: 25 not 25.0, 1.5 stays 1.5."""
    x = float(x)
    return str(int(x)) if x == int(x) else repr(x)


def loose(value):
    """Hands a value through untyped (Anvil's validator can't follow some dynamic dicts and components)."""
    return value


def J():
    return window.JB


# ---------------------------------------------------------------- data
def examples():
    if "ex" not in _cache:
        _cache["ex"] = to_py(J().EXAMPLES)
    return _cache["ex"]


def example(slug):
    for e in examples():
        if e["slug"] == slug:
            return e
    return None


def cats():
    """{key: [label, icon]} in the engine's order."""
    if "cats" not in _cache:
        _cache["cats"] = to_py(J().CATS)
    return _cache["cats"]


def cat_keys():
    return ["support", "sales", "safety", "agents", "finance", "ops", "content", "other"]


def chapters():
    if "ch" not in _cache:
        _cache["ch"] = json.loads(J().chapterList())
    return _cache["ch"]


def os_data():
    if "os" not in _cache:
        _cache["os"] = json.loads(J().OS.list())
    return _cache["os"]


# ---------------------------------------------------------------- numbers
def money(x):
    return str(J().money(x))


def pct(x):
    return "%d%%" % int(round(x * 100))


def tokens(s):
    return max(1, int(round(len(s or "") / 4.0)))


def monthly(ex):
    return ex["volume"] * ex["tokens"] * PRICE_PER_M / 1e6


def thousands(n):
    """12345 -> '12,345' (en-US, like toLocaleString)."""
    s = str(int(round(n)))
    neg = s.startswith("-")
    s = s.lstrip("-")
    out = ""
    while len(s) > 3:
        out = "," + s[-3:] + out
        s = s[:-3]
    return ("-" if neg else "") + s + out


def num(x, d=2):
    return str(J().num(x, d))


# ---------------------------------------------------------------- engine HTML
def code(blocks, title=None):
    return str(J().code(to_js(blocks), title))


def gen_blocks(req):
    return to_py(J().genBlocks(to_js(req)))


def req_json(req):
    return str(J().reqJson(to_js(req)))


def answer_card(name, answer):
    return str(J().answerCard(name, to_js(answer)))


def probs(p, legend=None):
    return str(J().probs(to_js(p), to_js(legend) if legend else None))


def callout(html, kind="", icon=None):
    return str(J().callout(html, kind, icon))


def table(head, rows):
    return str(J().table(to_js(head), to_js(rows)))


def all_code(req):
    """JSON + Python + TypeScript + curl + SDK + Self-hosted tabs for one request."""
    return code([{"label": "JSON", "key": "json", "lang": "json", "code": req_json(req)}] + gen_blocks(req))


def simulate(state, questions):
    return to_py(J().simulate(to_js(state), to_js(questions)))


def pretty(value):
    """JSON with 2-space indents, written by the browser (numbers look exactly like the API's)."""
    return str(window.JSON.stringify(to_js(value), None, 2))


def esc(text):
    return str(window.UI.esc(text))


# ---------------------------------------------------------------- the playground's draft
def state_text(state):
    return state if isinstance(state, str) else json.dumps(state, indent=2)


def from_map(state, qs):
    """A request's {state, questions} -> the editable draft {state: text, qs: [...]}."""
    out = []
    for n, q in (qs or {}).items():
        c = q.get("criteria")
        t = q.get("type")
        out.append({
            "name": n, "type": t, "instructions": q.get("instructions") or "",
            "t": (c or {}).get("true") or "" if isinstance(c, dict) else "",
            "f": (c or {}).get("false") or "" if isinstance(c, dict) else "",
            "options": ([{"label": k, "desc": "" if v is None else str(v)} for k, v in (c or {}).items()] if t == "choice"
                        else [{"label": "yes", "desc": ""}, {"label": "no", "desc": ""}]),
            "levels": [str(x) for x in (c or [])] if t == "score" else ["Low", "Medium", "High"],
        })
    return {"state": state_text(state if state is not None else ""), "qs": out}


def parse_state(text):
    st = (text or "").strip()
    if st[:1] in ("[", "{"):
        try:
            return json.loads(st)
        except ValueError:
            return st
    return st


def to_req(d):
    questions = {}
    for q in d["qs"]:
        o = {"type": q["type"], "instructions": (q.get("instructions") or "").strip()}
        if q["type"] == "noul":
            o["criteria"] = {"true": (q.get("t") or "").strip(), "false": (q.get("f") or "").strip()}
        elif q["type"] == "choice":
            o["criteria"] = {}
            for x in q["options"]:
                if (x.get("label") or "").strip():
                    o["criteria"][x["label"].strip()] = (x.get("desc") or "").strip() or None
        else:
            o["criteria"] = [(l or "").strip() for l in q["levels"]]
        questions[(q.get("name") or "").strip()] = o
    return {"model": MODEL, "state": parse_state(d["state"]), "questions": questions}


def problems(d):
    out, seen = [], {}
    if not d["state"].strip():
        out.append("Add some state: the text Jev should decide about.")
    if len(d["state"]) > 12000:
        out.append("The state is over 12,000 characters. Trim it to what matters.")
    if not d["qs"]:
        out.append("Add at least one question.")
    if len(d["qs"]) > 12:
        out.append("Up to 12 questions per request here.")
    for i, q in enumerate(d["qs"]):
        name = (q.get("name") or "").strip()
        n = name or "question %d" % (i + 1)
        if not NAME_RE.match(name):
            out.append(n + ": names use lowercase letters, digits and _ (like is_refund).")
        if name in seen:
            out.append(n + ": two questions have the same name.")
        seen[name] = 1
        if len((q.get("instructions") or "").strip()) < 3:
            out.append(n + ": write the instructions.")
        if q["type"] == "noul" and (not (q.get("t") or "").strip() or not (q.get("f") or "").strip()):
            out.append(n + ": describe both the true and the false case.")
        if q["type"] == "choice":
            labels = [x["label"].strip() for x in q["options"] if (x.get("label") or "").strip()]
            if len(labels) < 2:
                out.append(n + ": a choice needs at least 2 options.")
            if any(not LABEL_RE.match(l) for l in labels):
                out.append(n + ": option labels are short words (letters, digits, _ or -).")
            if len(labels) != len(set(labels)):
                out.append(n + ": two options have the same label.")
        if q["type"] == "score":
            if len(q["levels"]) < 2 or len(q["levels"]) > 10:
                out.append(n + ": a score needs 2 to 10 levels.")
            if any(not (l or "").strip() for l in q["levels"]):
                out.append(n + ": describe every level.")
    return out


def blank(kind, d):
    base = {"choice": "category", "noul": "is_true", "score": "level"}[kind]
    name, i = base, 2
    while any(q["name"] == name for q in d["qs"]):
        name = "%s_%d" % (base, i)
        i += 1
    return {"name": name, "type": kind, "instructions": "", "t": "", "f": "",
            "options": [{"label": "option_a", "desc": ""}, {"label": "option_b", "desc": ""}],
            "levels": ["Low", "Medium", "High"]}


def state_kind(text):
    st = (text or "").strip()
    if st[:1] in ("[", "{"):
        try:
            json.loads(st)
            return "sent as JSON · ~%d tokens" % tokens(st)
        except ValueError:
            return "looks like JSON but doesn't parse: sent as text"
    return "text · ~%d tokens" % tokens(st)
