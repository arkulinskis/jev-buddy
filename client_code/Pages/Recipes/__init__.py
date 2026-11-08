import anvil.server
from anvil import *
from anvil.js import window

from ._anvil_designer import RecipesTemplate
from ... import jb, router, state


def like_look(button, r):
    """The heart button: count, on/off, disabled on your own recipe."""
    button.text = str(r.get("likes") or 0)
    button.role = ["rc-like", "ic-heart"] + (["on"] if r.get("liked") else [])
    button.enabled = not r.get("mine")
    button.tooltip = "Your own recipe" if r.get("mine") else "Like"
    state.set_control_attr(button, "aria-pressed", "true" if r.get("liked") else "false")
    state.set_control_attr(button, "aria-label", "Like (%s)" % (r.get("likes") or 0))


def toggle_like(button, r):
    """Like / unlike (members only); updates r and the button."""
    if not state.me():
        router.remember_after(window.location.hash)
        router.go("auth")
        state.toast("Sign in to like recipes.")
        return
    res = state.call("toggle_like", r["id"])
    if res:
        r["liked"], r["likes"] = res["liked"], res["likes"]
        like_look(button, r)


class Recipes(RecipesTemplate):
    """#recipes (community, public), #recipes/mine (your own; sign in first) and #recipes/<id> (one recipe: state,
    questions, code in every language, like, fork or edit in the playground, delete). Server: Recipes.py."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        a = args[0] if args else None
        self.list_part.visible = a is None or a == "mine"
        self.detail_part.visible = False
        self.missing.visible = False
        if a and a != "mine":
            self.rid = a
            self._detail()
            return
        self.scope = "mine" if a == "mine" else "community"
        self.sort = "top"
        self._timer = None
        mine = self.scope == "mine"
        self.list_title.text = "My recipes" if mine else "Community recipes"
        state.heading(self.list_title, 1)
        self.list_lead.text = ("Requests you saved from the playground. Share one and it shows up for everyone." if mine else
                               "Ready-made Jev requests shared by developers. Open one in the playground, tweak it, save your own copy.")
        self.tab_community.classes["on"] = not mine
        self.tab_mine.classes["on"] = mine
        self.sort_seg.visible = not mine
        cats = jb.cats()
        self.cat_box.items = [("All categories", "")] + [(cats[c][0], c) for c in jb.cat_keys()]
        state.set_control_attr(self.cat_box, "aria-label", "Category")
        state.set_control_attr(self.search_box, "aria-label", "Search")
        self._show_sort()
        if mine and not state.me():
            self.filters.visible = False
            self.count.visible = False
            self._empty("save", "Save your own recipes", "Create a free account to keep the requests you build in the playground.",
                        "Create an account", "#auth/signup")
            return
        self._load()

    # ---- the list
    def _empty(self, icon, title, text, link_text=None, link=None):
        self.cards.items = []
        self.empty.visible = True
        self.empty_icon.classes.add("ic-" + icon)
        self.empty_title.text, self.empty_text.text = title, text
        self.empty_link.visible = bool(link_text)
        if link_text:
            self.empty_link_label.text = link_text
            state.set_attr(self.empty_link, "href", link)

    def _load(self):
        d = anvil.server.call("list_recipes", self.scope, self.cat_box.selected_value or None,
                              (self.search_box.text or "").strip() or None, self.sort)
        if isinstance(d, dict) and d.get("ok") is False:
            self.count.visible = False
            self._empty("lock", d.get("error") or "Sign in first", "", "Sign in", "#auth")
            return
        self.count.visible = bool(d["items"])
        self.count.text = state.plural(d["total"], "recipe")
        if not d["items"]:
            mine = self.scope == "mine"
            self._empty("save" if mine else "search", "No recipes yet" if mine else "Nothing matches",
                        "Build a request in the playground and press Save." if mine else "Try another search or category.",
                        "Open the playground" if mine else None, "#playground")
            return
        self.empty.visible = False
        self.cards.items = [dict(r, scope=self.scope) for r in d["items"]]

    def _show_sort(self):
        self.sort_top.classes["on"] = self.sort == "top"
        self.sort_new.classes["on"] = self.sort == "new"

    def sort_click(self, event):
        self.sort = event.currentTarget.getAttribute("data-s")
        self._show_sort()
        self._load()

    @handle("cat_box", "change")
    def cat_box_change(self, **event_args):
        self._load()

    @handle("search_box", "change")
    def search_box_change(self, **event_args):
        if self._timer is not None:
            window.clearTimeout(self._timer)
        self._timer = window.setTimeout(self._load, 250)

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self._load()

    def leave(self):
        if getattr(self, "_timer", None) is not None:
            window.clearTimeout(jb.loose(self._timer))

    # ---- one recipe
    def _detail(self):
        res = anvil.server.call("get_recipe", self.rid)
        if not isinstance(res, dict) or res.get("ok") is False:
            self.missing.visible = True
            self.missing_text.text = (res or {}).get("error") or "That recipe wasn't found."
            return
        r = self.r = res["recipe"]
        self.detail_part.visible = True
        router.title(r["title"])
        self.back_label.text = "My recipes" if r.get("mine") else "All recipes"
        state.set_attr(self.back_link, "href", "#recipes/mine" if r.get("mine") else "#recipes")
        cat = jb.cats().get(r.get("category")) or jb.cats()["other"]
        self.cat_icon.classes.add("ic-" + cat[1])
        self.cat_label.text = cat[0]
        self.hidden_badge.visible = bool(r.get("hidden"))
        self.private_badge.visible = not r.get("is_public")
        self.title.text = r["title"]
        state.heading(self.title, 1)
        self.summary.text = r.get("summary") or ""
        self.byline.text = "by %s · updated %s%s" % (r.get("owner") or "", state.short_date(r.get("updated")) + " " + (r.get("updated") or "")[:4],
                                                    " · fork of " + r["forked_from"] if r.get("forked_from") else "")
        self.like_button.visible = bool(r.get("is_public"))
        like_look(self.like_button, r)
        self.try_button.text = "Edit in the playground" if r.get("mine") else "Fork in the playground"
        self.delete_button.visible = bool(r.get("can_delete"))
        self.state_text.text = r["state"]
        qs = r["questions"]
        self.q_count.text = "Questions (%d)" % len(qs)
        self.questions.items = [dict(q, name=n) for n, q in qs.items()]
        req = {"model": jb.MODEL, "state": jb.parse_state(r["state"]), "questions": qs}
        self.code.content = jb.all_code(req)

    @handle("like_button", "click")
    def like_button_click(self, **event_args):
        toggle_like(self.like_button, self.r)

    @handle("try_button", "click")
    def try_button_click(self, **event_args):
        router.go("playground", "recipe", self.rid)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("It disappears for everyone. Forks other people made stay.", title="Delete this recipe?",
                   buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_recipe", self.rid) is not None:
                state.toast("Deleted", "ok")
                router.go("recipes", "mine")
