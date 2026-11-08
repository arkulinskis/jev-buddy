from anvil import *

from ._anvil_designer import StepTemplate


class Step(StepTemplate):
    """One numbered step of a use case's "With Jev" list (item = the text; the number is CSS)."""

    def __init__(self, **properties):
        super().__init__(**properties)
