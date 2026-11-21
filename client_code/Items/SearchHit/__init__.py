from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import SearchHitTemplate

KIND_CLASS = {"Chapter": "ch", "Use case": "uc", "Open source": "os", "Gotcha": "gt", "Error fix": "er", "Tool": "tl", "Page": "pg"}


class SearchHit(SearchHitTemplate):
    """Dialogs/Search: one hit (item = {kind, title, snippet (HTML from JB.search, matches in <mark>), go, icon, i}).
    A real link (#go), so Ctrl/middle-click opens a new tab; a plain click raises x-pick so the dialog closes first."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        a = self.dom_nodes["link"]
        a.setAttribute("href", "#" + it["go"])
        a.id = "sr-hit-%d" % it.get("i", 0)
        a.classList.add("k-" + KIND_CLASS.get(it["kind"], "ch"))
        self.dom_nodes["icon"].innerHTML = str(window.UI.icon(it.get("icon") or "book"))
        self.dom_nodes["kind"].textContent = it["kind"]
        self.dom_nodes["title"].textContent = it["title"]
        self.dom_nodes["snip"].innerHTML = it.get("snippet") or ""  # escaped by JB.search; only <mark> is markup
        a.addEventListener("click", anvil.js.report_exceptions(self._click))

    def _click(self, event):
        if getattr(event, "ctrlKey", False) or getattr(event, "metaKey", False) or getattr(event, "shiftKey", False) or getattr(event, "button", 0):
            return
        event.preventDefault()
        if self.parent is not None:
            self.parent.raise_event("x-pick", go=self.item["go"])
