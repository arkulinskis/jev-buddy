from anvil import *

from ._anvil_designer import OsCardTemplate


class OsCard(OsCardTemplate):
    """Open source: one project card (item = an entry of JB.OS.list().opts + dim). Pressing it jumps to its section."""

    def __init__(self, **properties):
        super().__init__(**properties)
        o = self.item
        if o.get("best"):
            self.badge.text, self.badge.role = o["best"], ["badge", "badge-brand"]
        else:
            self.badge.text, self.badge.role = o["status"][0], ["badge", "badge-" + o["status"][1]]
        self.card.classes["dim"] = bool(o.get("dim"))

    def card_click(self, event):
        self.parent.raise_event("x-jump", key=self.item["id"])
