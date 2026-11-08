from anvil import *

from ._anvil_designer import SideLinkTemplate
from ... import router, state


class SideLink(SideLinkTemplate):
    """The guide's chapter list beside a chapter (item = {id, title, read, on})."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        state.set_attr(self.link, "href", router.href("learn", c["id"]))
        self.link.classes["on"] = bool(c.get("on"))
        if c.get("on"):
            state.set_attr(self.link, "aria-current", "page")
        self.tick.classes["done"] = bool(c.get("read"))
        self.tick_icon.visible = bool(c.get("read"))
