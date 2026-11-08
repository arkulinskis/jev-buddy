"""Server tests against the strict mock of Anvil (tools/testing/mock).

    python tools/testing/test_server.py          (no -I: reads anvil.yaml)          -> prints ALL OK, or the first failure

call(name, ...) runs a server function the way the browser does: by name, with require_user enforced,
and the reply must be JSON (a datetime or a row in a reply fails here, like it would break the page).
Add tests for every new server function: the happy path, bad input, and someone who isn't allowed.
"""
import datetime as dt
import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(PROJECT / "server_code", _tmp / "app")
(_tmp / "app" / "__init__.py").write_text("")
os.environ["ANVIL_APP_YAML"] = str(PROJECT / "anvil.yaml")  # the mock's tables follow the app's own schema
sys.path[:0] = [str(HERE / "mock"), str(_tmp)]
import anvil.server  # noqa: E402
import anvil.users  # noqa: E402
from anvil.tables import app_tables as T  # noqa: E402

M = {p.stem: importlib.import_module("app." + p.stem) for p in sorted((PROJECT / "server_code").glob("*.py"))}
now = dt.datetime.now(dt.timezone.utc)


def call(name, *args):
    r = anvil.server.call(name, *args)
    json.dumps(r)  # strict: must be JSON-able
    return r


def as_user(row):
    anvil.users.CURRENT[0] = row
    anvil.server.session.use(row.get_id() if row is not None else None)


def denied(name, *args):
    try:
        call(name, *args)
    except anvil.server.PermissionDenied:
        return True
    return False


def ok(r, msg=""):
    assert isinstance(r, dict) and r.get("ok"), (msg, r)
    return r


def bad(r, msg=""):
    assert isinstance(r, dict) and r.get("ok") is False and r.get("error"), (msg, r)
    return r


def person(email, name=None, **kw):
    return T.users.add_row(email=email, enabled=True, signed_up=now, display_name=name, **kw)


# ---------------------------------------------------------------------------------- accounts
admin = person("arkulinskis@gmail.com", "The Admin")
ana = person("ana@example.com", "Ana")
bob = person("bob@example.com")

as_user(None)
assert call("get_me") is None
assert denied("update_profile", "X")
as_user(admin)
assert call("get_me")["is_admin"] is True, "ADMIN_EMAILS become admins on first sign-in"
as_user(ana)
me = call("get_me")
assert me["name"] == "Ana" and me["is_admin"] is False
assert ana["last_seen"] is not None
as_user(bob)
assert call("get_me")["name"] == "Bob", "a name comes from the email when none is set"
bad(call("update_profile", " x "))
assert ok(call("update_profile", "  Bob   Stone "))["me"]["name"] == "Bob Stone"

# ---------------------------------------------------------------------------------- feedback
as_user(None)
bad(call("submit_feedback", "bug", "hi"))
ok(call("submit_feedback", "bug", "The button is broken", "guest@example.com", {"page": "#home", "evil": "x" * 9999}))
fb = T.feedback.search()[0]
assert fb["name"] == "Guest" and fb["email"] == "guest@example.com" and "evil" not in fb["context"] and fb["status"] == "new"
for i in range(4):
    ok(call("submit_feedback", "idea", "Idea number %d" % i))
bad(call("submit_feedback", "idea", "One too many this hour"), "rate limit")
as_user(ana)
ok(call("submit_feedback", "nonsense-kind", "Signed-in feedback"))
assert T.feedback.get(message="Signed-in feedback")["kind"] == "other"
assert denied("list_feedback")
as_user(admin)
lst = call("list_feedback")
assert lst["counts"]["new"] == 6 and len(lst["items"]) == 6
fid = lst["items"][0]["id"]
ok(call("set_feedback_status", fid, "done", "Fixed it"))
assert call("list_feedback", "done")["items"][0]["note"] == "Fixed it"
bad(call("set_feedback_status", fid, "weird"))
bad(call("set_feedback_status", "nope", "done"))
ok(call("delete_feedback", fid))
assert len(call("list_feedback")["items"]) == 5

# ---------------------------------------------------------------------------------- admin
as_user(ana)
for fn, args in [("admin_overview", ()), ("list_users", ()), ("set_admin", (bob.get_id(), True)), ("demo_load", ()), ("demo_remove", ())]:
    assert denied(fn, *args), fn
as_user(admin)
ov = call("admin_overview")
assert ov["users"] == 3 and ov["admins"] == 1 and ov["feedback_new"] == 5
assert len(call("list_users")["users"]) == 3 and len(call("list_users", "bob")["users"]) == 1
ok(call("set_admin", bob.get_id(), True))
assert bob["is_admin"] is True
bad(call("set_admin", admin.get_id(), False), "can't remove your own admin")
ok(call("set_enabled", bob.get_id(), False))
assert bob["enabled"] is False
bad(call("set_enabled", admin.get_id(), False))
ok(call("set_enabled", bob.get_id(), True))
ok(call("set_admin", bob.get_id(), False))
assert bob["is_admin"] is False

# ---------------------------------------------------------------------------------- demo data + recipes
import anvil.http as H  # noqa: E402

as_user(None)
lst = call("list_recipes")
n_demo = len(M["DemoData"].DEMO_RECIPES)
assert M["DemoData"].state() == "loaded" and lst["total"] == n_demo, "demo loads on first visit"
assert lst["items"][0]["likes"] >= lst["items"][-1]["likes"], "community sorts by likes"
assert all(not i["mine"] and not i["liked"] for i in lst["items"])
assert call("list_recipes", "community", "safety")["total"] == 2
assert call("list_recipes", "community", None, "injection")["total"] == 1
bad(call("list_recipes", "mine"), "guests have no recipes")
demo_id = lst["items"][0]["id"]
full = ok(call("get_recipe", demo_id))["recipe"]
assert full["state"] and full["questions"] and not full["can_delete"]
bad(call("get_recipe", "nope"))
assert denied("save_recipe", {})
assert denied("toggle_like", demo_id)

GOOD = {"title": "Ana's triage", "summary": "Mine", "category": "support", "is_public": False,
        "state": "My parcel never arrived",
        "questions": {"team": {"type": "choice", "instructions": "Which team?", "criteria": {"shipping": "Parcels", "billing": None}},
                      "angry": {"type": "noul", "instructions": "Is the customer angry?"},
                      "urgency": {"type": "score", "instructions": "How urgent?", "criteria": ["Low", "High"]}}}
as_user(ana)
bad(call("save_recipe", dict(GOOD, title="x")), "short title")
bad(call("save_recipe", dict(GOOD, state=" ")), "no state")
bad(call("save_recipe", dict(GOOD, questions={})), "no questions")
bad(call("save_recipe", dict(GOOD, questions={"Bad Name": GOOD["questions"]["angry"]})), "bad question name")
bad(call("save_recipe", dict(GOOD, questions={"q": {"type": "maybe", "instructions": "Hmm?"}})), "bad type")
bad(call("save_recipe", dict(GOOD, questions={"q": {"type": "choice", "instructions": "Pick", "criteria": {"one": "x"}}})), "one option")
bad(call("save_recipe", dict(GOOD, questions={"q": {"type": "score", "instructions": "Rate", "criteria": ["a"] * 11}})), "11 levels")
bad(call("save_recipe", dict(GOOD, questions={"q": {"type": "noul", "instructions": "Yes?", "criteria": {"true": "y"}}})), "half a noul")
mine = ok(call("save_recipe", GOOD))["recipe"]
assert mine["mine"] and mine["can_delete"] and mine["category"] == "support" and mine["questions"]["team"]["criteria"]["billing"] is None
assert call("list_recipes", "mine")["total"] == 1
assert call("list_recipes")["total"] == n_demo, "private recipes stay out of the community list"
ok(call("save_recipe", dict(GOOD, title="Ana's triage v2", is_public=True), mine["id"]))
assert call("list_recipes")["total"] == n_demo + 1
bad(call("toggle_like", mine["id"]), "can't like your own")
lk = ok(call("toggle_like", demo_id))
assert lk["liked"] is True and lk["likes"] == full["likes"] + 1
assert ok(call("toggle_like", demo_id))["liked"] is False
fork = ok(call("save_recipe", dict(GOOD, title="Fork of demo"), None, demo_id))["recipe"]
assert fork["forked_from"] and T.recipes.get_by_id(demo_id)["forks"] == full["forks"] + 1
as_user(bob)
bad(call("get_recipe", fork["id"]), "someone else's private recipe is hidden")
bad(call("save_recipe", GOOD, mine["id"]), "can't edit someone else's recipe")
bad(call("delete_recipe", mine["id"]), "can't delete someone else's recipe")
ok(call("toggle_like", mine["id"]))
assert denied("admin_list_recipes") and denied("admin_set_recipe_hidden", mine["id"], True)
as_user(admin)
assert any(i["id"] == mine["id"] for i in call("admin_list_recipes")["items"])
assert not any(i["id"] == fork["id"] for i in call("admin_list_recipes")["items"]), "admins don't see private recipes"
ok(call("admin_set_recipe_hidden", mine["id"], True))
as_user(None)
assert call("list_recipes")["total"] == n_demo, "hidden recipes leave the gallery"
bad(call("get_recipe", mine["id"]))
as_user(ana)
assert ok(call("get_recipe", mine["id"]))["recipe"]["hidden"] is True, "the owner still sees a hidden recipe"

as_user(admin)
ok(call("demo_remove"))
assert M["DemoData"].state() == "removed" and not T.users.search(is_demo=True)
assert T.recipes.get_by_id(fork["id"])["forked_from"] is None, "forks of demo recipes survive its removal"
as_user(None)
call("list_recipes")
assert M["DemoData"].state() == "removed", "removed demo data doesn't come back by itself"
as_user(admin)
ok(call("demo_load"))
ok(call("demo_load"))
as_user(ana)
assert call("list_recipes")["total"] == n_demo, "reloading replaces the demo instead of doubling it (Ana's is hidden)"
as_user(admin)
ok(call("delete_recipe", mine["id"]), "admins can delete anything")
as_user(ana)
ok(call("delete_recipe", fork["id"]))
assert call("list_recipes", "mine")["total"] == 0

# ---------------------------------------------------------------------------------- Jev: status, live runs, admin settings
as_user(None)
st = call("jev_status")
assert st["live"] is False and st["model"] == "typesafe/jev-1.13" and st["signed_in"] is False
assert denied("run_live", "x", {})
as_user(ana)
bad(call("run_live", "Charged twice", GOOD["questions"]), "live is off without a key")
for fn, args in [("admin_jev_settings", ()), ("admin_save_jev_settings", ({},)), ("admin_clear_jev_key", ()), ("admin_test_jev", ())]:
    assert denied(fn, *args), fn
as_user(admin)
assert call("admin_jev_settings")["has_key"] is False
bad(call("admin_test_jev"), "no key yet")
bad(call("admin_save_jev_settings", {"key": "short", "enabled": True}))
bad(call("admin_save_jev_settings", {"model": "Not A Model!"}))
bad(call("admin_save_jev_settings", {"daily_cap": 0}))
sv = ok(call("admin_save_jev_settings", {"enabled": True}))["settings"]
assert sv["enabled"] is False, "can't enable without a key"
sv = ok(call("admin_save_jev_settings", {"key": "sk-or-v1-0123456789abcdef0123", "enabled": True, "daily_cap": 3, "per_user_hour": 2}))["settings"]
assert sv["live"] and sv["key_hint"].endswith("0123") and "sk-or" not in json.dumps(sv), "the key never goes back to the browser"
assert "sk-or" not in json.dumps(call("jev_status"))

seen = []


def fake(url, method, data):
    seen.append(data)
    return {"id": "gen-dec-1", "model": "typesafe/jev-1.13-20260917", "provider": "TypeSafe",
            "answers": {k: {"type": "noul", "noul": 0.9} for k in data["questions"]},
            "usage": {"input_tokens": 120, "output_tokens": 0, "cost": 0.000005}}


H.REPLIES["https://openrouter.ai/api/alpha/decisions"] = fake
r = ok(call("admin_test_jev"))
assert r["response"]["answers"]["is_refund"]["noul"] == 0.9
as_user(ana)
assert call("jev_status")["live"] is True and call("jev_status")["daily_left"] == 2
bad(call("run_live", "", GOOD["questions"]), "empty state")
r = ok(call("run_live", "Charged twice", GOOD["questions"]))
assert seen[-1]["model"] == "typesafe/jev-1.13" and set(seen[-1]["questions"]) == {"team", "angry", "urgency"}
assert r["response"]["usage"]["cost"] == 0.000005
run = T.jev_runs.search(user=ana)[0]
assert run["ok"] and run["input_tokens"] == 120
H.REPLIES["https://openrouter.ai/api/alpha/decisions"] = H.HttpError(402, {"error": {"message": "Insufficient credits"}})
assert "credits" in bad(call("run_live", "Charged twice", GOOD["questions"]))["error"]
bad(call("run_live", "Charged twice", GOOD["questions"]), "per-person hourly limit (2) reached")
as_user(bob)
H.REPLIES["https://openrouter.ai/api/alpha/decisions"] = fake
bad(call("run_live", "Charged twice", GOOD["questions"]), "daily cap (3) reached")
as_user(admin)
sv = call("admin_jev_settings")
assert sv["runs_today"] == 3 and sv["errors_today"] == 1 and sv["tokens_total"] == 240, sv
ok(call("admin_clear_jev_key"))
assert call("jev_status")["live"] is False
ov = call("admin_overview")
assert ov["runs_today"] == 3 and ov["live"] is False and "recipes" in ov

# ---------------------------------------------------------------------------------- Jev: a self-hosted open-source server
for u in ["http://decide.example.com", "https://localhost:8000", "https://127.0.0.1", "https://192.168.1.20:8000",
          "https://10.0.0.5", "https://[::1]:8000", "https://my-box.local", "https://decide.example.com/?x=1", "ftp://x.com"]:
    bad(call("admin_save_jev_settings", {"provider": "selfhosted", "base_url": u}), u)
bad(call("admin_save_jev_settings", {"provider": "somewhere"}))
bad(call("admin_save_jev_settings", {"provider": "selfhosted", "local_key": "short"}))
bad(call("admin_save_jev_settings", {"provider": "selfhosted", "local_model": "Bad Model!"}))
ok(call("admin_save_jev_settings", {"key": "sk-or-v1-0123456789abcdef0123"}))   # an OpenRouter key is saved too
sv = ok(call("admin_save_jev_settings", {"provider": "selfhosted", "enabled": True}))["settings"]
assert sv["enabled"] is False and sv["ready"] is False, "can't enable a self-hosted server without its address"
bad(call("admin_test_jev"), "no address yet")
sv = ok(call("admin_save_jev_settings", {"provider": "selfhosted", "base_url": "https://decide.example.com/", "local_key": "laya-secret-0123456789",
                                         "local_model": "", "enabled": True, "daily_cap": 50, "per_user_hour": 20}))["settings"]
assert sv["live"] and sv["endpoint"] == "https://decide.example.com/v1/systemone" and sv["local_key_hint"].endswith("6789")
assert "laya-secret" not in json.dumps(sv) and "sk-or" not in json.dumps(sv)
local_seen = []


def local(url, method, data):
    local_seen.append(data)
    return {"model": "laya", "answers": {k: {"type": "noul", "noul": 0.8} for k in data["questions"]},
            "usage": {"input_tokens": 50, "output_tokens": 0}}


H.REPLIES["https://decide.example.com/v1/systemone"] = local
H.REPLIES["https://openrouter.ai/api/alpha/decisions"] = H.HttpError(500, {"error": {"message": "must not be called"}})
ok(call("admin_test_jev"))
assert "model" not in local_seen[-1], "no model sent when the server hosts one"
last = H.CALLS[-1]
assert last["url"] == "https://decide.example.com/v1/systemone" and last["headers"] == {"Authorization": "Bearer laya-secret-0123456789"}
assert "sk-or" not in json.dumps(H.CALLS[-1]), "the OpenRouter key never goes to a self-hosted server"
as_user(bob)
st = call("jev_status")
assert st["live"] is True and st["provider"] == "selfhosted" and "laya-secret" not in json.dumps(st)
r = ok(call("run_live", "Charged twice", GOOD["questions"]))
assert r["response"]["answers"]["team"]["noul"] == 0.8 and r["response"]["usage"]["cost"] is None
as_user(admin)
ok(call("admin_save_jev_settings", {"provider": "selfhosted", "local_model": "laya:multilingual"}))
ok(call("admin_test_jev"))
assert local_seen[-1]["model"] == "laya:multilingual"
H.REPLIES["https://decide.example.com/v1/systemone"] = H.HttpError(503, {"detail": "loading"})
assert "isn't ready" in bad(call("admin_test_jev"))["error"]
H.REPLIES["https://decide.example.com/v1/systemone"] = local
sv = ok(call("admin_save_jev_settings", {"provider": "selfhosted", "base_url": "https://decide.example.com:8443/v1/systemone"}))["settings"]
assert sv["endpoint"] == "https://decide.example.com:8443/v1/systemone"
as_user(ana)
assert denied("admin_clear_jev_key", "selfhosted")
as_user(admin)
sv = ok(call("admin_clear_jev_key", "selfhosted"))["settings"]
assert sv["base_url"] == "" and sv["has_local_key"] is False and sv["live"] is False and sv["has_key"] is True
sv = ok(call("admin_save_jev_settings", {"provider": "openrouter"}))["settings"]
assert sv["provider"] == "openrouter" and sv["ready"] is True
ok(call("admin_clear_jev_key"))
assert call("admin_jev_settings")["has_key"] is False

# ---------------------------------------------------------------------------------- Privacy & Terms
if "legal_server" in M:
    as_user(ana)
    st = call("legal_state")
    assert st["signedIn"] and st["accepted_version"] is None
    ok(call("legal_accept", st["version"], "signup"))
    assert ana["legal_source"] == "signup" and call("legal_state")["accepted_version"] == st["version"]

# ---------------------------------------------------------------------------------- every callable is covered by a permission check
# A callable that changes data without require_user / a C.require_* check is a security hole. List the public ones here.
PUBLIC = {"get_me", "submit_feedback", "list_recipes", "get_recipe", "jev_status", "legal_state", "legal_accept"}
for name, (f, need) in sorted(anvil.server.CALLABLES.items()):
    if name in PUBLIC:
        continue
    assert need, "%s is callable by anyone: add require_user=True (or list it in PUBLIC in test_server.py)" % name

print("ALL OK (%d server functions)" % len(anvil.server.CALLABLES))
