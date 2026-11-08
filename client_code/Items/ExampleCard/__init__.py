from anvil import *
from anvil.js import window

from ._anvil_designer import ExampleCardTemplate
from ... import jb, router, state


class ExampleCard(ExampleCardTemplate):
    """Use cases: one card (item = an entry of JB.EXAMPLES): category, who, tagline, question types, monthly cost."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        state.set_attr(self.link, "href", router.href("examples", e["slug"]))
        self.icon.classes.add("ic-" + e["icon"])
        self.cat.text = jb.cats()[e["cat"]][0]
        self.cost.text = "≈ %s/mo" % jb.money(jb.monthly(e))
        box = self.dom_nodes["types"]
        for q in e["questions"].values():
            s = window.document.createElement("span")
            s.className = "jb-type " + q["type"]
            s.textContent = q["type"]
            box.appendChild(s)
