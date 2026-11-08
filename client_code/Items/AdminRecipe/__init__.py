from anvil import *

from ._anvil_designer import AdminRecipeTemplate
from ... import router, state


class AdminRecipe(AdminRecipeTemplate):
    """Admin → Recipes: one shared recipe with Hide / Show again (raises x-changed so the list reloads)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        state.set_attr(self.link, "href", router.href("recipes", r["id"]))
        self.demo_badge.visible = bool(r.get("demo"))
        self.hidden_badge.visible = bool(r.get("hidden"))
        self.meta.text = "%s · %s · %d likes · %s" % (r.get("owner") or "", state.short_date(r.get("created")), r.get("likes") or 0,
                                                   r.get("summary") or "")
        self.hide_button.text = "Show again" if r.get("hidden") else "Hide"
        self.hide_button.role = ["btn", "btn-sm"] + ([] if r.get("hidden") else ["btn-danger"])

    @handle("hide_button", "click")
    def hide_button_click(self, **event_args):
        if state.call("admin_set_recipe_hidden", self.item["id"], not self.item.get("hidden")) is not None:
            state.toast("Saved", "ok")
            self.parent.raise_event("x-changed")
