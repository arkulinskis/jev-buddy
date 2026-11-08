from anvil import *

from ._anvil_designer import SideGroupTemplate


class SideGroup(SideGroupTemplate):
    """The guide's chapter list: one group heading and its links (item = {name, items})."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.links.items = self.item["items"]
