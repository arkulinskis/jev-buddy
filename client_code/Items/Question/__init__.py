from anvil import *

from ._anvil_designer import QuestionTemplate
from ... import state


class Question(QuestionTemplate):
    """Playground: one question of the draft (item = {q, i}; q is the draft's own dict, edited in place).
    Type switch, name, instructions, then options (choice), true/false (noul) or levels (score).
    Raises on the questions panel: x-edit (text changed), x-redraw (structure changed), x-del-q."""

    def __init__(self, **properties):
        super().__init__(**properties)
        state.set_control_attr(self.name_box, "aria-label", "Question name")
        state.set_control_attr(self.name_box, "spellcheck", "false")
        state.set_control_attr(self.instr_box, "aria-label", "Instructions")
        state.set_control_attr(self.t_box, "aria-label", "What a yes looks like")
        state.set_control_attr(self.f_box, "aria-label", "What a no looks like")
        self.options.add_event_handler("x-edit", self._edited)
        self.options.add_event_handler("x-del", self._del_opt)
        self.levels.add_event_handler("x-edit", self._edited)
        self.levels.add_event_handler("x-del", self._del_lvl)
        self._draw()

    def _draw(self):
        q = self.item["q"]
        for t, b in (("choice", self.t_choice), ("noul", self.t_noul), ("score", self.t_score)):
            b.classes["on"] = q["type"] == t
        self.choice_part.visible = q["type"] == "choice"
        self.noul_part.visible = q["type"] == "noul"
        self.score_part.visible = q["type"] == "score"
        if q["type"] == "choice":
            self.options.items = [{"opt": o, "label": o["label"], "desc": o["desc"], "k": k} for k, o in enumerate(q["options"])]
            self.opt_count.text = "%d options" % len(q["options"])
        if q["type"] == "score":
            self.levels.items = [{"text": l, "k": k, "levels": q["levels"]} for k, l in enumerate(q["levels"])]
            self.add_lvl.enabled = len(q["levels"]) < 10
            self.lvl_range.text = "score runs 0 to %d" % max(1, len(q["levels"]) - 1)

    def _edited(self, **event_args):
        self.parent.raise_event("x-edit")

    def _changed(self):
        self._draw()
        self.parent.raise_event("x-redraw")

    def type_click(self, event):
        self.item["q"]["type"] = event.currentTarget.getAttribute("data-type")
        self._changed()

    @handle("name_box", "change")
    def name_box_change(self, **event_args):
        self.item["q"]["name"] = self.name_box.text or ""
        self._edited()

    @handle("instr_box", "change")
    def instr_box_change(self, **event_args):
        self.item["q"]["instructions"] = self.instr_box.text or ""
        self._edited()

    @handle("t_box", "change")
    def t_box_change(self, **event_args):
        self.item["q"]["t"] = self.t_box.text or ""
        self._edited()

    @handle("f_box", "change")
    def f_box_change(self, **event_args):
        self.item["q"]["f"] = self.f_box.text or ""
        self._edited()

    @handle("add_opt", "click")
    def add_opt_click(self, **event_args):
        opts = self.item["q"]["options"]
        if len(opts) < 30:
            opts.append({"label": "option_" + chr(97 + len(opts)), "desc": ""})
        self._changed()

    def _del_opt(self, k, **event_args):
        self.item["q"]["options"].pop(k)
        self._changed()

    @handle("add_lvl", "click")
    def add_lvl_click(self, **event_args):
        lv = self.item["q"]["levels"]
        if len(lv) < 10:
            lv.append("Level %d" % len(lv))
        self._changed()

    def _del_lvl(self, k, **event_args):
        self.item["q"]["levels"].pop(k)
        self._changed()

    @handle("del_button", "click")
    def del_button_click(self, **event_args):
        self.parent.raise_event("x-del-q", i=self.item["i"])
