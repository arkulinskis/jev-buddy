from anvil import *
from anvil.js import window

from ._anvil_designer import RecipeQuestionTemplate


class RecipeQuestion(RecipeQuestionTemplate):
    """A recipe's question (item = {name, type, instructions, criteria}) with its options, true/false or levels."""

    def __init__(self, **properties):
        super().__init__(**properties)
        q = self.item
        self.type_tag.classes.add(q["type"])
        self.type_label.text = q["type"]
        c = q.get("criteria")
        if q["type"] == "noul":
            rows = [("true", (c or {}).get("true")), ("false", (c or {}).get("false"))] if c else []
        elif q["type"] == "choice":
            rows = [(k, v) for k, v in (c or {}).items()]
        else:
            rows = [(str(i), v) for i, v in enumerate(c or [])]
        ul = self.dom_nodes["crit"]
        for k, v in rows:
            li = window.document.createElement("li")
            b = window.document.createElement("b")
            b.textContent = k
            li.appendChild(b)
            if v:
                li.appendChild(window.document.createTextNode(" " + str(v)))
            ul.appendChild(li)
        ul.style.display = "block" if rows else "none"
