from anvil import *

from ._anvil_designer import UseCardTemplate
from ... import router, state


class UseCard(UseCardTemplate):
    """Landing: one business use case (item = an entry of JB.EXAMPLES) linking to #examples/<slug>."""

    def __init__(self, **properties):
        super().__init__(**properties)
        state.set_attr(self.link, "href", router.href("examples", self.item["slug"]))
        self.icon.classes.add("ic-" + self.item["icon"])
