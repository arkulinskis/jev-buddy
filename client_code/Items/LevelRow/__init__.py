from anvil import *

from ._anvil_designer import LevelRowTemplate
from ... import state


class LevelRow(LevelRowTemplate):
    """Playground: one score level (item = {text, k, levels}); level 0 is the first."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.ix.text = str(self.item["k"])
        state.set_control_attr(self.level_box, "aria-label", "Level %d" % self.item["k"])

    @handle("level_box", "change")
    def level_box_change(self, **event_args):
        self.item["levels"][self.item["k"]] = self.level_box.text or ""
        self.parent.raise_event("x-edit")

    @handle("del_button", "click")
    def del_button_click(self, **event_args):
        self.parent.raise_event("x-del", k=self.item["k"])
