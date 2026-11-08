from anvil import *
import anvil.server

from ._anvil_designer import SaveRecipeTemplate
from ... import jb, state


class SaveRecipe(SaveRecipeTemplate):
    """Playground → Save: title, summary, category, share in Community recipes. Saves your own recipe in place, or a new
    recipe (a fork when it came from someone else's). Closes with the saved recipe (or None when cancelled).
    alert(SaveRecipe(meta=..., state_text=..., questions=...), buttons=[], role="app-dialog")."""

    def __init__(self, meta=None, state_text="", questions=None, **properties):
        super().__init__(**properties)
        self.meta = meta or {}
        self.state_text, self.qs = state_text, questions or {}
        self.mine = bool(self.meta.get("recipe_id") and self.meta.get("mine"))
        self.heading.text = "Save your recipe" if self.mine else "Save as a recipe"
        state.heading(self.heading, 2)
        self.intro.text = ("A recipe is this state and these questions, saved to your account."
                           + (" This saves your own copy (a fork)." if self.meta.get("recipe_id") and not self.mine else ""))
        self.title_box.text = self.meta.get("title") or ""
        self.summary_box.text = self.meta.get("summary") or ""
        cats = jb.cats()
        self.cat_box.items = [(cats[c][0], c) for c in jb.cat_keys()]
        self.cat_box.selected_value = self.meta.get("category") or "support"
        self.public_box.checked = bool(self.meta.get("is_public"))
        self.copy_button.visible = self.mine
        self.save_button.text = "Save changes" if self.mine else "Save recipe"
        state.set_control_attr(self.title_box, "maxlength", 80)
        state.set_control_attr(self.summary_box, "maxlength", 240)

    def _save(self, as_new):
        data = {"title": (self.title_box.text or "").strip(), "summary": (self.summary_box.text or "").strip(),
                "category": self.cat_box.selected_value, "is_public": bool(self.public_box.checked),
                "state": self.state_text, "questions": self.qs}
        rid = self.meta.get("recipe_id") if self.mine and not as_new else None
        fork = self.meta.get("recipe_id") if self.meta.get("recipe_id") and (not self.mine or as_new) else None
        res = anvil.server.call("save_recipe", data, rid, fork)
        if not isinstance(res, dict) or not res.get("ok"):
            self.message.visible = True
            self.message.text = (res or {}).get("error") or "That didn't save."
            return
        state.toast("Recipe saved" if rid else "Saved to My recipes", "ok")
        self.raise_event("x-close-alert", value=res["recipe"])

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        self._save(False)

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        self._save(True)

    @handle("title_box", "pressed_enter")
    def title_box_pressed_enter(self, **event_args):
        self._save(False)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
