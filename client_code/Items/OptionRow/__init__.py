from anvil import *

from ._anvil_designer import OptionRowTemplate
from ... import state


class OptionRow(OptionRowTemplate):
    """Playground: one choice option (item = {label, desc, k}). Typing edits the draft in place; x-edit / x-del tell the page."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.ix.text = str(self.item["k"] + 1)
        state.set_control_attr(self.label_box, "aria-label", "Option label")
        state.set_control_attr(self.desc_box, "aria-label", "Option description")
        state.set_control_attr(self.label_box, "spellcheck", "false")

    @handle("label_box", "change")
    def label_box_change(self, **event_args):
        self.item["opt"]["label"] = self.label_box.text or ""
        self.parent.raise_event("x-edit")

    @handle("desc_box", "change")
    def desc_box_change(self, **event_args):
        self.item["opt"]["desc"] = self.desc_box.text or ""
        self.parent.raise_event("x-edit")

    @handle("del_button", "click")
    def del_button_click(self, **event_args):
        self.parent.raise_event("x-del", k=self.item["k"])
