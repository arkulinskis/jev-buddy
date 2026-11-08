from anvil import *

from ._anvil_designer import ChapterGroupTemplate


class ChapterGroup(ChapterGroupTemplate):
    """The guide's index: one group of chapters (item = {name, items})."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.cards.items = self.item["items"]
