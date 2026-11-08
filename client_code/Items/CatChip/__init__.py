from anvil import *

from ._anvil_designer import CatChipTemplate
from ... import state


class CatChip(CatChipTemplate):
    """A filter chip (Use cases categories, the Open source hardware picker): item = {key, label, icon, on}.
    Clicking raises x-pick on the panel with the key."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.chip.role = ["chip", "ic-" + self.item["icon"]] + (["on"] if self.item.get("on") else [])
        state.set_control_attr(self.chip, "aria-pressed", "true" if self.item.get("on") else "false")
        state.set_control_attr(self.chip, "data-key", self.item["key"])

    @handle("chip", "click")
    def chip_click(self, **event_args):
        self.parent.raise_event("x-pick", key=self.item["key"])
