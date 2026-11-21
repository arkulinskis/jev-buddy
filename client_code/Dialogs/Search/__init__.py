from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import SearchTemplate
from ... import jb, state


class Search(SearchTemplate):
    """The search palette (Layouts/Shell opens it: header button, More sheet, Ctrl/Cmd+K or "/").
    Searches chapters and their sections, gotchas, error codes, use cases, the Open source page and the tools in the
    browser (jb.search -> JB.search in jb-content.js). Empty box = popular picks; no hits = a Submit feedback link.
    Keyboard: up/down move the highlighted hit, Enter opens it. Closes with the hit's address ("learn/gotchas") or None.
    alert(Search(), buttons=[], role="app-dialog", large=True, dismissible=True)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.hits: list = []
        self.active = 0
        box = state.control(self.q_box)
        for name, value in (("role", "combobox"), ("aria-expanded", "true"), ("aria-controls", "sr-list"),
                            ("aria-autocomplete", "list"), ("aria-label", "Search Jev Buddy"), ("type", "search"),
                            ("autocomplete", "off"), ("spellcheck", "false"), ("enterkeyhint", "go")):
            box.setAttribute(name, value)
        box.addEventListener("keydown", anvil.js.report_exceptions(self._keydown))
        self.results.add_event_handler("x-pick", self._pick)
        state.live(self.hint)
        self._run()

    @handle("", "show")
    def form_show(self, **event_args):
        window.setTimeout(lambda: state.focus(self.q_box), 60)

    @handle("q_box", "change")
    def q_box_change(self, **event_args):
        self._run()

    def _run(self):
        q = (self.q_box.text or "").strip()
        self.hits = jb.search(q, 12)
        self.active = 0
        for i, h in enumerate(self.hits):
            h["i"] = i
        self.results.items = self.hits
        self.empty.visible = bool(q) and not self.hits
        self.empty_text.text = "Nothing found for “%s”." % q[:60] if q else ""
        if not q:
            self.hint.text = "Popular"
        elif self.hits:
            self.hint.text = "%d result%s" % (len(self.hits), "" if len(self.hits) == 1 else "s") if len(self.hits) < 12 else "Top 12 results"
        else:
            self.hint.text = "No results"
        self._mark()

    def _nodes(self):
        return [n for n in getattr(window.Array, "from")(self.dom_nodes["list"].querySelectorAll(".sr-hit"))]

    def _mark(self, scroll=False):
        box = state.control(self.q_box)
        nodes = self._nodes()
        for i, n in enumerate(nodes):
            on = i == self.active
            n.classList.toggle("on", on)
            n.setAttribute("aria-selected", "true" if on else "false")
            if on and scroll:
                n.scrollIntoView(jb.to_js({"block": "nearest"}))
        if nodes and self.active < len(nodes):
            box.setAttribute("aria-activedescendant", str(nodes[self.active].id))
        else:
            box.removeAttribute("aria-activedescendant")

    def _keydown(self, event):
        key = getattr(event, "key", "")
        if key in ("ArrowDown", "ArrowUp") and self.hits:
            event.preventDefault()
            step = 1 if key == "ArrowDown" else -1
            self.active = (self.active + step) % len(self.hits)
            self._mark(scroll=True)
        elif key == "Enter":
            event.preventDefault()
            if self.hits:
                self._pick(self.hits[self.active]["go"])

    def _pick(self, go, **event_args):
        self.raise_event("x-close-alert", value=go)

    @handle("feedback_button", "click")
    def feedback_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
        state.feedback()
