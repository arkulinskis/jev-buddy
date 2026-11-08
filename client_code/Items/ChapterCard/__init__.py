from anvil import *

from ._anvil_designer import ChapterCardTemplate
from ... import router, state


class ChapterCard(ChapterCardTemplate):
    """The guide's index: one chapter card (item = {id, icon, title, blurb, mins, read})."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        state.set_attr(self.link, "href", router.href("learn", c["id"]))
        self.icon.classes.add("ic-" + c["icon"])
        self.read_badge.visible = bool(c.get("read"))
        self.mins.visible = not c.get("read")
        self.mins.text = "%d min" % c["mins"]
