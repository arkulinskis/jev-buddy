import math

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import ToolsTemplate
from ... import jb, router, state

TABS = ["cost", "confidence", "thresholds"]
COST_DEFAULT = {"volume": 100000, "tokens": 250, "questions": 3, "llmIn": 0.10, "llmOut": 0.50, "outPerQ": 40, "overhead": 120, "retry": 3}
THR_DEFAULT = {"auto": 0.8, "floor": 0.5, "errCost": 25, "reviewCost": 1.5}


def r3(x):
    return math.floor(x * 1000 + 0.5) / 1000.0


def r2(x):
    return math.floor(x * 100 + 0.5) / 100.0


def number(box):
    """A TextBox(type=number) value as a float >= 0 (empty or bad = 0)."""
    v = box.text
    try:
        return max(0.0, float(v)) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def norm(rows):
    t = sum(x[1] for x in rows) or 1
    return [x[1] * 1.0 / t for x in rows]


def synthetic():
    """600 decisions: confidence skews high, and correctness rises with confidence (as calibration intends).
    The same seeded generator as the JavaScript version, so the numbers match."""
    seed, data = [7], []  # a list cell: the browser's Python has no nonlocal

    def rnd():
        seed[0] = (seed[0] * 16807) % 2147483647
        return (seed[0] - 1) / 2147483646.0

    for _ in range(600):
        c = min(0.999, rnd() ** 0.45)
        data.append((c, rnd() < 0.3 + 0.69 * c))
    return data


class Tools(ToolsTemplate):
    """#tools/cost[/volume/tokens/questions]: Jev's monthly cost against an LLM returning JSON (store 'cost').
    #tools/confidence: how confidence is computed for choice, score and noul (TypeSafe's formulas, JB.conf*).
    #tools/thresholds: the threshold simulator on 600 synthetic decisions (store 'thr'). All in the browser."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.args = list(args)
        self.tab = args[0] if args and args[0] in TABS else "cost"
        for t, part, link in (("cost", self.cost_part, self.tab_cost), ("confidence", self.conf_part, self.tab_confidence),
                              ("thresholds", self.thr_part, self.tab_thresholds)):
            part.visible = t == self.tab
            link.classes["on"] = t == self.tab
        {"cost": self._cost_setup, "confidence": self._conf_setup, "thresholds": self._thr_setup}[self.tab]()

    # ================================================================ cost
    COST_BOXES = [("volume", "c_volume"), ("tokens", "c_tokens"), ("questions", "c_questions"), ("llmIn", "c_llm_in"),
                  ("llmOut", "c_llm_out"), ("outPerQ", "c_out_per_q"), ("overhead", "c_overhead"), ("retry", "c_retry")]

    def _cost_setup(self):
        v = dict(COST_DEFAULT)
        v.update(jb.store_get("cost", {}) or {})
        a = self.args
        try:
            if len(a) > 1:
                v["volume"] = float(a[1]) or v["volume"]
                v["tokens"] = (float(a[2]) if len(a) > 2 else 0) or v["tokens"]
                v["questions"] = (float(a[3]) if len(a) > 3 else 0) or v["questions"]
        except ValueError:
            pass
        steps = {"volume": 1000, "tokens": 10, "questions": 1, "llmIn": 0.01, "llmOut": 0.01, "outPerQ": 5, "overhead": 10, "retry": 1}
        for key, name in self.COST_BOXES:
            box = getattr(self, name)
            box.text = v[key]
            state.set_control_attr(box, "min", 0)
            state.set_control_attr(box, "step", steps[key])
            box.add_event_handler("change", self._cost_calc)
        self._cost_calc()

    def _cost_calc(self, **event_args):
        v = {key: number(getattr(self, name)) for key, name in self.COST_BOXES}
        jb.store_set("cost", v)
        jev_call = v["tokens"] * jb.PRICE_PER_M / 1e6
        jev_month = jev_call * v["volume"]
        llm_call = ((v["tokens"] + v["overhead"]) * v["llmIn"] + v["questions"] * v["outPerQ"] * v["llmOut"]) / 1e6 * (1 + v["retry"] / 100.0)
        llm_month = llm_call * v["volume"]
        ratio = llm_month / jev_month if jev_month > 0 else 0
        top = max(jev_month, llm_month, 1e-9)
        self.k_jev.text, self.k_llm.text = jb.money(jev_month), jb.money(llm_month)
        self.k_ratio.text = ((str(int(round(ratio))) if ratio >= 10 else "%.1f" % ratio) + "×") if ratio >= 1 else "–"
        self.k_year.text = "cheaper with Jev · %s a year" % jb.money(max(0, llm_month - jev_month) * 12)
        self.dom_nodes["bar_jev"].style.width = "%s%%" % (jev_month / top * 100)
        self.dom_nodes["bar_llm"].style.width = "%s%%" % (llm_month / top * 100)
        self.v_jev.text, self.v_llm.text = jb.money(jev_month), jb.money(llm_month)
        n = jb.n
        self.cost_table.content = jb.table(["Per call", "Jev", "LLM"], [
            ["Input tokens", n(v["tokens"]), n(v["tokens"] + v["overhead"])],
            ["Output tokens", "0", n(v["questions"] * v["outPerQ"])],
            ["Cost", jb.money(jev_call), jb.money(llm_call)],
            ["Median latency", "≈ 0.21 s", "usually 0.5 s or more"],
            ["Parsing and retries", "none", n(v["retry"]) + "% retried"]])
        self.cost_note.text = ("Jev bills only input tokens. Estimates, not quotes: your provider's price page wins. "
                               "1 million decisions with these settings cost %s on Jev." % jb.money(jev_call * 1e6))

    # ================================================================ confidence
    def _conf_setup(self):
        self.s: dict = {"type": "choice", "choice": [["billing", 70], ["tech", 20], ["sales", 10]],
                  "score": [["0", 5], ["1", 90], ["2", 5]], "noul": 0.82}
        r = self.dom_nodes["noul_range"]
        r.value = str(self.s["noul"])
        r.setAttribute("aria-label", "Probability of true")
        r.addEventListener("input", anvil.js.report_exceptions(self._noul_slide))
        self.weights.add_event_handler("x-weights", self._weights_changed)
        self._conf_inputs()
        self._conf_out()

    def type_click(self, event):
        self.s["type"] = event.currentTarget.getAttribute("data-t")
        self._conf_inputs()
        self._conf_out()

    def _conf_inputs(self):
        t = self.s["type"]
        for k, b in (("choice", self.t_choice), ("score", self.t_score), ("noul", self.t_noul)):
            b.classes["on"] = k == t
        self.noul_part.visible = t == "noul"
        self.weights_part.visible = t != "noul"
        self.noul_out.text = "%.2f" % self.s["noul"]
        if t != "noul":
            rows = self.s[t]
            P = norm(rows)
            self.weights.items = [{"row": x, "i": i, "kind": t, "p": P[i]} for i, x in enumerate(rows)]
            self.add_row.text = "Option" if t == "choice" else "Level"
            self.add_row.enabled = len(rows) < 8
            self.del_row.enabled = len(rows) > 2

    def _noul_slide(self, event):
        self.s["noul"] = float(self.dom_nodes["noul_range"].value)
        self.noul_out.text = "%.2f" % self.s["noul"]
        self._conf_out()

    def _weights_changed(self, **event_args):
        P = norm(self.s[self.s["type"]])
        for i, row in enumerate(self.weights.get_components()):
            if i < len(P):
                jb.loose(row).show_p(P[i])
        self._conf_out()

    @handle("add_row", "click")
    def add_row_click(self, **event_args):
        rows = self.s[self.s["type"]]
        rows.append(["option_%d" % (len(rows) + 1) if self.s["type"] == "choice" else str(len(rows)), 20])
        self._conf_inputs()
        self._conf_out()

    @handle("del_row", "click")
    def del_row_click(self, **event_args):
        self.s[self.s["type"]].pop()
        self._conf_inputs()
        self._conf_out()

    def _conf_out(self):
        t = self.s["type"]
        if t == "noul":
            p = self.s["noul"]
            c = abs(2 * p - 1)
            html = (jb.answer_card("your_question", {"type": "noul", "noul": r2(p)})
                    + '<div class="ui-card tl-math"><h3>The maths</h3><div class="tl-formula">confidence = |2p − 1|\n'
                    + "           = |2 × %.2f − 1|\n           = %.2f</div>" % (p, c)
                    + '<p class="muted small tl-flat">' + ("Near 0.5 Jev is unsure: send it to a person or rephrase the question."
                                                           if 0.4 < p < 0.6 else "Far from 0.5: a clear answer.") + "</p></div>")
        elif t == "choice":
            P = norm(self.s["choice"])
            probs = {}
            for i, x in enumerate(self.s["choice"]):
                probs[x[0] or "option_%d" % i] = r3(P[i])
            n = len(P)
            pm = max(P)
            ordered = sorted(P, reverse=True)
            cc = float(window.JB.confChoice(jb.to_js(probs)))
            top = max(probs.values())
            best = [k for k in probs if probs[k] == top][0]
            html = (jb.answer_card("your_question", {"type": "choice", "choice": best, "confidence": r2(cc), "probabilities": probs})
                    + '<div class="ui-card tl-math"><h3>The maths</h3><div class="tl-formula">confidence = (p_max − 1/n) / (1 − 1/n)\n'
                    + "           = (%.2f − 1/%d) / (1 − 1/%d)\n           = %.2f</div>" % (pm, n, n, cc)
                    + jb.table(["Other measures", "Value", "Reads as"], [
                        ["Top probability", "%.2f" % pm, "How likely the pick is"],
                        ["Top ÷ runner-up", ("%.1f×" % (pm / ordered[1])) if len(ordered) > 1 and ordered[1] else "∞",
                         "How clearly it beats second place"]]) + "</div>")
        else:
            Q = norm(self.s["score"])
            pr, lg, sc = {}, {}, 0.0
            for i, p in enumerate(Q):
                pr[str(i)] = r3(p)
                lg[str(i)] = "level %d" % i
                sc += i * p
            cs = float(window.JB.confScore(jb.to_js(Q)))
            m = Q.index(max(Q))
            nn = len(Q)
            spread = sum(p * abs(i - m) for i, p in enumerate(Q))
            mad = sum(abs(i - (nn - 1) / 2.0) / nn for i in range(nn))
            html = (jb.answer_card("your_question", {"type": "score", "score": r2(sc), "confidence": r2(cs), "probabilities": pr, "legend": lg})
                    + '<div class="ui-card tl-math"><h3>The maths</h3><div class="tl-formula">score      = Σ i × p_i = %.2f\n' % sc
                    + "most likely level m = %d\nspread     = Σ p_i × |i − m| = %.3f\n" % (m, spread)
                    + "uniform    = mean |i − (n−1)/2| = %.3f\nconfidence = max(0, 1 − spread / uniform) = %.2f</div></div>" % (mad, cs))
        self.conf_out.content = html

    # ================================================================ thresholds
    def _thr_setup(self):
        self.data = synthetic()
        v = dict(THR_DEFAULT)
        v.update(jb.store_get("thr", {}) or {})
        self.dom_nodes["r_auto"].value = str(v["auto"])
        self.dom_nodes["r_floor"].value = str(v["floor"])
        self.dom_nodes["r_auto"].setAttribute("aria-label", "Act automatically above")
        self.dom_nodes["r_floor"].setAttribute("aria-label", "Ask to confirm above")
        jb.loose(self.t_err).text, jb.loose(self.t_review).text = v["errCost"], v["reviewCost"]
        state.set_control_attr(self.t_err, "min", 0)
        state.set_control_attr(self.t_review, "min", 0)
        state.set_control_attr(self.t_review, "step", 0.1)
        calc = anvil.js.report_exceptions(lambda e: self._thr_calc())
        self.dom_nodes["r_auto"].addEventListener("input", calc)
        self.dom_nodes["r_floor"].addEventListener("input", calc)
        self.t_err.add_event_handler("change", lambda **e: self._thr_calc())
        self.t_review.add_event_handler("change", lambda **e: self._thr_calc())
        self._thr_calc()

    def _thr_calc(self):
        auto_t = float(self.dom_nodes["r_auto"].value)
        v = {"auto": auto_t, "floor": min(float(self.dom_nodes["r_floor"].value), auto_t),
             "errCost": number(self.t_err), "reviewCost": number(self.t_review)}
        jb.store_set("thr", v)
        self.o_auto.text = "%.2f" % v["auto"]
        self.o_floor.text = "%.2f" % v["floor"]
        data, total = self.data, float(len(self.data))
        auto = [d for d in data if d[0] >= v["auto"]]
        conf = [d for d in data if v["floor"] <= d[0] < v["auto"]]
        human = len(data) - len(auto) - len(conf)
        wrong = len([d for d in auto if not d[1]])
        acc = 1 - wrong * 1.0 / len(auto) if auto else 0

        def per10k(n):
            return int(math.floor(n / total * 10000 + 0.5))

        cost_total = (wrong * v["errCost"] + (len(conf) + human) * v["reviewCost"]) / total * 10000
        self.k_auto.text = jb.pct(len(auto) / total)
        self.k_acc.text = "%.1f%%" % (acc * 100) if auto else "–"
        self.k_wrong.text = str(per10k(wrong))
        self.thr_chart.content = self._histogram(v)
        self.thr_table.content = jb.table(["Route", "Share", "Per 10k decisions"], [
            ['<span class="jb-conf hi">Automatic</span>', jb.pct(len(auto) / total), per10k(len(auto))],
            ['<span class="jb-conf mid">Confirm</span>', jb.pct(len(conf) / total), per10k(len(conf))],
            ['<span class="jb-conf lo">Human</span>', jb.pct(human / total), per10k(human)]])
        self.thr_total.text = "Total cost per 10k decisions: " + jb.money(cost_total)
        self.thr_how.text = "(mistakes × $%s + reviews × $%s; Jev itself adds about %s)" % (
            jb.n(v["errCost"]), jb.n(v["reviewCost"]), jb.money(10000 * 250 * jb.PRICE_PER_M / 1e6))

    def _histogram(self, v):
        """The confidence histogram (right / wrong per bin) with the two threshold lines, as SVG."""
        bins, W, H, pad = 20, 600, 190, 24
        bw = (W - pad * 2) / float(bins)
        hist = [[0, 0] for _ in range(bins)]
        for c, ok in self.data:
            hist[min(bins - 1, int(math.floor(c * bins)))][0 if ok else 1] += 1
        mx = max(h[0] + h[1] for h in hist)
        parts = []
        for k, (ok, bad) in enumerate(hist):
            x = pad + k * bw
            h_ok, h_bad, y0 = ok * 1.0 / mx * (H - 40), bad * 1.0 / mx * (H - 40), H - 22
            parts.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="2" fill="var(--c-brand)" opacity=".75"/>' % (x + 2, y0 - h_ok, bw - 4, h_ok))
            parts.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="2" fill="var(--c-bad)" opacity=".85"/>' % (x + 2, y0 - h_ok - h_bad, bw - 4, h_bad))

        def line(t, color, label):
            x = pad + t * (W - pad * 2)
            return ('<line x1="%.2f" x2="%.2f" y1="10" y2="%d" stroke="%s" stroke-width="2" stroke-dasharray="4 3"/>'
                    '<text x="%.2f" y="20" font-size="11" fill="%s" font-family="JetBrains Mono, monospace">%s</text>' % (x, x, H - 22, color, x + 4, color, label))

        axis = "".join('<text x="%.2f" y="%d" font-size="11" text-anchor="middle" fill="var(--c-faint)" font-family="JetBrains Mono, monospace">%s</text>'
                       % (pad + t * (W - pad * 2), H - 6, jb.n(t)) for t in (0, 0.25, 0.5, 0.75, 1))
        return ('<div class="tl-chart"><svg viewBox="0 0 %d %d" role="img" aria-label="Confidence histogram">' % (W, H) + "".join(parts)
                + line(v["floor"], "var(--c-warn)", "confirm") + line(v["auto"], "var(--c-good)", "auto") + axis + "</svg></div>")
