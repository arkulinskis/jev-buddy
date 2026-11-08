from anvil import *
from anvil.js import window

from ._anvil_designer import ExamplesTemplate
from ... import jb, router, state


class Examples(ExamplesTemplate):
    """#examples: the twelve business use cases with category chips (the choice is remembered, store 'ex_cat').
    #examples/<slug>: one use case: problem, steps, the state, the request in every language, illustrative answers,
    the routing code, tips, its monthly cost and "Open in the playground". Data: JB.EXAMPLES (jb.js)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.ex = jb.example(args[0]) if args else None
        self.list_part.visible = self.ex is None
        self.detail_part.visible = self.ex is not None
        if self.ex:
            self._detail(self.ex)
        else:
            self.cat = state.store_get("ex_cat", "all")
            self.chips.add_event_handler("x-pick", self._pick)
            self._list()

    # ---- the list
    def _list(self):
        cats = jb.cats()
        used = [c for c in jb.cat_keys() if any(e["cat"] == c for e in jb.examples())]
        self.chips.items = [{"key": c, "label": "All" if c == "all" else cats[c][0], "icon": "grid" if c == "all" else cats[c][1],
                             "on": c == self.cat} for c in ["all"] + used]
        self.cards.items = [e for e in jb.examples() if self.cat == "all" or e["cat"] == self.cat]

    def _pick(self, key, **event_args):
        self.cat = key
        state.store_set("ex_cat", key)
        self._list()
        state.refocus(self.chips, key)

    # ---- one use case
    def _detail(self, ex):
        router.title(ex["title"])
        req = {"model": jb.MODEL, "state": ex["state"], "questions": ex["questions"]}
        self.req = req
        exs = jb.examples()
        nxt = exs[(exs.index(ex) + 1) % len(exs)]
        cat = jb.cats()[ex["cat"]]
        self.cat_icon.classes.add("ic-" + cat[1])
        self.cat_label.text = cat[0]
        self.title.text = ex["title"]
        state.heading(self.title, 1)
        self.tagline.text = ex["tagline"]
        self.who.text = ex["who"]
        m, qn = jb.monthly(ex), len(ex["questions"])
        self.calls.text = "At %s calls a month" % jb.thousands(ex["volume"])
        self.month.text = jb.money(m)
        self.per_call.text = "%d questions per call · about %d input tokens · %s each" % (
            qn, ex["tokens"], jb.money(ex["tokens"] * jb.PRICE_PER_M / 1e6))
        state.set_attr(self.compare_link, "href", router.href("tools", "cost", ex["volume"], ex["tokens"], qn))
        self.problem.text = ex["problem"]
        self.before.text = ex["before"]
        self.steps.items = ex["steps"]
        state.set_attr(self.steps, "role", "list")
        self.state_text.text = jb.state_text(ex["state"])
        self.request_code.content = jb.all_code(req)
        self.answers.content = '<div class="ex-ans">' + "".join(jb.answer_card(k, a) for k, a in ex["answers"].items()) + "</div>"
        cost = float("%.2g" % (ex["tokens"] * jb.PRICE_PER_M / 1e6))
        resp = {"id": "gen-dec-…", "model": "typesafe/jev-1.13-20260917", "provider": "TypeSafe", "answers": ex["answers"],
                "usage": {"input_tokens": ex["tokens"], "output_tokens": 0, "cost": cost}}
        self.raw.content = jb.code({"lang": "json", "label": "response.json", "code": jb.pretty(resp)})
        self.logic.content = jb.code({"lang": "python", "label": ex["slug"].replace("-", "_") + ".py", "code": ex["logic"]})
        self.tips.items = ex["tips"]
        self.next_label.text = "Next: " + nxt["title"]
        state.set_attr(self.next_link, "href", router.href("examples", nxt["slug"]))

    @handle("try_button", "click")
    def try_button_click(self, **event_args):
        ex = jb.loose(self.ex)
        window.JB.toPlayground(jb.to_js(self.req), jb.to_js({"title": ex["title"], "from": "example"}))
