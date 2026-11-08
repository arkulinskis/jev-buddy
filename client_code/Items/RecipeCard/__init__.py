from anvil import *
from anvil.js import window

from ._anvil_designer import RecipeCardTemplate
from ... import jb, router, state
from ...Pages.Recipes import like_look, toggle_like


class RecipeCard(RecipeCardTemplate):
    """Recipes: one card (item = a list_recipes row + scope). Opens #recipes/<id> on click or Enter; the heart likes it."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        cat = jb.cats().get(r.get("category")) or jb.cats()["other"]
        self.cat_icon.classes.add("ic-" + cat[1])
        self.cat_label.text = cat[0]
        if r.get("scope") == "mine":
            self.status.text = "Hidden by a moderator" if r.get("hidden") else "Shared" if r.get("is_public") else "Private"
            self.status.role = ["badge"] + (["badge-warn"] if r.get("hidden") else ["badge-good"] if r.get("is_public") else [])
        else:
            self.status.visible = bool(r.get("demo"))
            self.status.text = "Demo"
        self.by.text = "by %s · %s%s" % (r.get("owner") or "", state.ago(r.get("updated") or r.get("created")),
                                        " · fork of " + r["forked_from"] if r.get("forked_from") else "")
        self.summary.text = r.get("summary") or ", ".join(r.get("names") or [])
        for t in r.get("types") or []:
            s = window.document.createElement("span")
            s.className = "jb-type " + str(t)
            s.textContent = t
            self.dom_nodes["types"].appendChild(s)
        self.forks.visible = bool(r.get("forks"))
        self.forks_n.text = str(r.get("forks") or 0)
        self.like_button.visible = bool(r.get("is_public"))
        like_look(self.like_button, r)

    def card_click(self, event):
        if event.target.closest(".anvil-role-rc-like"):
            return
        router.go("recipes", self.item["id"])

    def card_key(self, event):
        if event.key == "Enter" and event.target == event.currentTarget:
            router.go("recipes", self.item["id"])

    @handle("like_button", "click")
    def like_button_click(self, **event_args):
        toggle_like(self.like_button, self.item)
