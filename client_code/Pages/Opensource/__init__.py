from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import OpensourceTemplate
from ... import jb, state


class Opensource(OpensourceTemplate):
    """#opensource, #opensource/<section>: open-source alternatives to Jev that run on your own machine (Laya, Ollaya,
    Kev, jevos, d1-omni-600M, SemIf, Von). The head, the reasons, the jump bar, the hardware picker and the project cards
    are this Form; the long sections (the one-line switch, the comparison table, install/run/call steps per project,
    build your own, putting a server online, testing, Jev Buddy's own use, sources) are the engine's text
    (JB.OS in jb-content.js), unchanged. #opensource/<section> scrolls to #os-<section>."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.section = args[0] if args else None
        self.hw = "all"
        self.data = jb.os_data()
        self.switch_part.content = str(window.JB.OS.switchHtml())
        self.rest_part.content = str(window.JB.OS.restHtml())
        self.chips.add_event_handler("x-pick", self._pick)
        self.cards.add_event_handler("x-jump", self._card_jump)
        self.dom_nodes["jump_nav"].addEventListener("click", anvil.js.report_exceptions(self._nav_click))
        self._draw()

    def _draw(self):
        self.chips.items = [{"key": k, "label": label, "icon": icon, "on": k == self.hw} for k, label, icon in self.data["hw"]]
        self.tip.content = '<p class="os-tip">' + self.data["tips"][self.hw] + "</p>"
        self.cards.items = [dict(o, dim=self.hw != "all" and self.hw not in o["hw"]) for o in self.data["opts"]]

    def _pick(self, key, **event_args):
        self.hw = key
        self._draw()
        state.refocus(self.chips, key)

    def _jump(self, key, smooth=True):
        el = window.document.getElementById("os-" + key)
        if el:
            el.scrollIntoView(jb.to_js({"behavior": "smooth" if smooth else "auto", "block": "start"}))

    def _card_jump(self, key, **event_args):
        self._jump(key)

    def _nav_click(self, event):
        b = event.target.closest("[data-jump]")
        if b:
            self._jump(b.getAttribute("data-jump"))

    def start(self):
        if self.section:
            key = self.section
            window.setTimeout(lambda: self._jump(key, False), 30)
