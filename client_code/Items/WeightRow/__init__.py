from anvil import *
import anvil.js

from ._anvil_designer import WeightRowTemplate
from ... import state


class WeightRow(WeightRowTemplate):
    """Tools → Confidence: one option (choice: editable label) or level (score) with its raw weight slider.
    item = {row: [label, weight] (the page's own list), i, kind, p}. Raises x-weights on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        choice = it["kind"] == "choice"
        self.label_box.visible = choice
        self.level.visible = not choice
        self.level.text = "level %d" % it["i"]
        state.set_control_attr(self.label_box, "aria-label", "Option label")
        r = self.dom_nodes["range"]
        r.value = str(it["row"][1])
        r.addEventListener("input", anvil.js.report_exceptions(self._slide))
        self.p.text = "%.2f" % it["p"]

    def _slide(self, event):
        self.item["row"][1] = int(float(self.dom_nodes["range"].value))
        self.parent.raise_event("x-weights")

    @handle("label_box", "change")
    def label_box_change(self, **event_args):
        self.item["row"][0] = (self.label_box.text or "").strip()
        self.parent.raise_event("x-weights")

    def show_p(self, p):
        self.p.text = "%.2f" % p
