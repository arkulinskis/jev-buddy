from anvil import *

from ._anvil_designer import TipTemplate


class Tip(TipTemplate):
    """A "tip from the field" on a use case (item = the text)."""

    def __init__(self, **properties):
        super().__init__(**properties)
