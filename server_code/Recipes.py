"""Recipes: saved Jev requests (state + questions). Anyone can browse the public ones; members save their own
(from the playground), share them, like and fork other people's. Admins can hide a public recipe."""
import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import DemoData, Jev

CATEGORIES = ("support", "sales", "safety", "agents", "finance", "ops", "content", "other")
MAX_PER_USER = 200


def _visible(r, me):
    if r is None:
        return False
    if me is not None and (r["owner"] == me or C.is_admin(me)):
        return True
    return bool(r["is_public"]) and not r["hidden"]


def _liked(r, me):
    return me is not None and app_tables.recipe_likes.get(user=me, recipe=r) is not None


def _recipe(r, me, full=False):
    qs = r["questions"] or {}
    d = {"id": r.get_id(), "title": r["title"], "summary": r["summary"] or "", "category": r["category"] or "other",
         "owner": C.name_of(r["owner"]), "mine": me is not None and r["owner"] == me, "is_public": bool(r["is_public"]),
         "hidden": bool(r["hidden"]), "likes": int(r["likes"] or 0), "forks": int(r["forks"] or 0),
         "created": C.iso(r["created"]), "updated": C.iso(r["updated"]), "demo": bool(r["is_demo"]),
         "types": [q.get("type") for q in qs.values()], "names": list(qs.keys()),
         "forked_from": r["forked_from"]["title"] if r["forked_from"] is not None else None}
    if full:
        d.update(state=r["state"] or "", questions=qs, liked=_liked(r, me),
                 can_delete=me is not None and (r["owner"] == me or C.is_admin(me)))
    return d


@anvil.server.callable
def list_recipes(scope="community", category=None, query=None, sort="top"):
    DemoData.ensure_loaded()
    me = C.me()
    if scope == "mine":
        if me is None:
            return C.fail("Sign in to see your recipes.")
        rows = list(app_tables.recipes.search(tables.order_by("updated", ascending=False), owner=me))
    else:
        rows = [r for r in app_tables.recipes.search(tables.order_by("created", ascending=False), is_public=True) if not r["hidden"]]
    if category in CATEGORIES:
        rows = [r for r in rows if r["category"] == category]
    q = C.text(query, 80).lower()
    if q:
        rows = [r for r in rows if q in (r["title"] or "").lower() or q in (r["summary"] or "").lower()
                or any(q in n for n in (r["questions"] or {}).keys())]
    if sort == "top" and scope != "mine":
        rows.sort(key=lambda r: (-(r["likes"] or 0), -(r["forks"] or 0)))
    liked = set()
    if me is not None:
        liked = {l["recipe"].get_id() for l in app_tables.recipe_likes.search(user=me) if l["recipe"] is not None}
    items = []
    for r in rows[:120]:
        d = _recipe(r, me)
        d["liked"] = d["id"] in liked
        items.append(d)
    return {"items": items, "total": len(rows), "categories": list(CATEGORIES)}


@anvil.server.callable
def get_recipe(recipe_id):
    me = C.me()
    r = C.row_by_id(app_tables.recipes, recipe_id)
    if not _visible(r, me):
        return C.fail("That recipe doesn't exist or isn't shared.")
    return C.ok(recipe=_recipe(r, me, full=True))


@anvil.server.callable(require_user=True)
def save_recipe(data, recipe_id=None, forked_from=None):
    me = C.require_user()
    if not isinstance(data, dict):
        return C.fail("Nothing to save.")
    title = C.text(data.get("title"), 80)
    if len(title) < 3:
        return C.fail("Give the recipe a title (at least 3 characters).")
    category = data.get("category") if data.get("category") in CATEGORIES else "other"
    state, questions, err = Jev.validate(data.get("state"), data.get("questions"))
    if err:
        return C.fail(err)
    if not isinstance(state, str):
        import json
        state = json.dumps(state, indent=2)
    fields: dict = dict(title=title, summary=C.text(data.get("summary"), 240), category=category, state=state,
                  questions=questions, is_public=bool(data.get("is_public")), updated=C.now())
    if recipe_id:
        r = C.row_by_id(app_tables.recipes, recipe_id)
        if r is None:
            return C.fail("That recipe no longer exists.")
        if r["owner"] != me:
            return C.fail("You can only edit your own recipes. Save a copy instead.")
        r.update(**fields)
        return C.ok(recipe=_recipe(r, me, full=True))
    if C.rate_limited("save_recipe", 40, 3600):
        return C.fail("That's a lot of recipes in one hour. Take a break and try again later.")
    if len(app_tables.recipes.search(owner=me)) >= MAX_PER_USER:
        return C.fail("You have %d recipes, the most we keep per person. Delete some first." % MAX_PER_USER)
    parent = C.row_by_id(app_tables.recipes, forked_from) if forked_from else None
    if parent is not None and not _visible(parent, me):
        parent = None
    r = app_tables.recipes.add_row(owner=me, created=C.now(), likes=0, forks=0, hidden=False, is_demo=False,
                                   forked_from=parent, **fields)
    if parent is not None and parent["owner"] != me:
        parent["forks"] = (parent["forks"] or 0) + 1
    return C.ok(recipe=_recipe(r, me, full=True))


@anvil.server.callable(require_user=True)
def delete_recipe(recipe_id):
    me = C.require_user()
    r = C.row_by_id(app_tables.recipes, recipe_id)
    if r is None:
        return C.ok()
    if r["owner"] != me and not C.is_admin(me):
        return C.fail("You can only delete your own recipes.")
    for l in app_tables.recipe_likes.search(recipe=r):
        l.delete()
    for child in app_tables.recipes.search(forked_from=r):
        child["forked_from"] = None
    r.delete()
    return C.ok()


@anvil.server.callable(require_user=True)
def toggle_like(recipe_id):
    me = C.require_user()
    r = C.row_by_id(app_tables.recipes, recipe_id)
    if not _visible(r, me) or not r["is_public"]:
        return C.fail("That recipe isn't shared.")
    if r["owner"] == me:
        return C.fail("That's your own recipe: it's already loved.")
    like = app_tables.recipe_likes.get(user=me, recipe=r)
    if like is None:
        app_tables.recipe_likes.add_row(user=me, recipe=r, created=C.now(), is_demo=False)
        r["likes"] = (r["likes"] or 0) + 1
    else:
        like.delete()
        r["likes"] = max(0, (r["likes"] or 0) - 1)
    return C.ok(liked=like is None, likes=int(r["likes"]))


# ------------------------------------------------------------------------------------------- admin
@anvil.server.callable(require_user=True)
def admin_list_recipes():
    """Shared recipes (public or hidden by an admin). Private ones stay private, even from admins."""
    me = C.require_admin()
    rows = app_tables.recipes.search(tables.order_by("created", ascending=False), is_public=True)
    return {"items": [_recipe(r, me) for r in rows[:300]]}


@anvil.server.callable(require_user=True)
def admin_set_recipe_hidden(recipe_id, flag):
    me = C.require_admin()
    r = C.row_by_id(app_tables.recipes, recipe_id)
    if r is None:
        return C.fail("That recipe no longer exists.")
    r["hidden"] = bool(flag)
    return C.ok(recipe=_recipe(r, me))
