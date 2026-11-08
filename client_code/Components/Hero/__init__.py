from anvil import *
from anvil.js import window

from ._anvil_designer import HeroTemplate


class Hero(HeroTemplate):
    """The landing hero: an HTML/CSS terminal that cycles through three example states (illustrative answers).
    The animation is the JavaScript engine's (JB.hero); this component starts it on show and stops it on hide."""

    def __init__(self, **properties):
        self._stop = None
        super().__init__(**properties)

    @handle("", "show")
    def form_show(self, **event_args):
        if self._stop is None:
            self._stop = window.JB.hero(self.dom_nodes["mount"])

    @handle("", "hide")
    def form_hide(self, **event_args):
        if self._stop is not None:
            self._stop()
            self._stop = None
