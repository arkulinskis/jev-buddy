import anvil.server
from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import PlaygroundTemplate
from ... import jb, router, state

TABS = ["answers", "request", "code"]


class Playground(PlaygroundTemplate):
    """#playground, #playground/recipe/<id>, #playground/s/<code> (a share link): build a Jev request (state + typed questions) and run it.
    Answers come live through the server (run_live: OpenRouter or the admin's own open-source server) when an admin
    switched live runs on and the visitor is signed in; otherwise from the in-browser simulator (JB.simulate), clearly
    labelled. The draft is kept in this browser (store 'pg_draft', the same key as before; examples and recipes hand
    requests over through it). Members save the draft as a recipe (Dialogs/SaveRecipe -> save_recipe).
    Share (anyone, no account): the request packed into the link itself (jb.pack -> #playground/s/<code>, Dialogs/
    ShareDraft, with a README badge). Opening one keeps the visitor's old draft in store 'pg_prev' for "Restore"."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tab, self.last_err = "answers", None
        self.last: dict = {}
        self.meta: dict = {}
        saved = jb.store_get("pg_draft")
        first = jb.examples()[0]
        if saved and saved.get("questions"):
            self.d = jb.from_map(saved.get("state"), saved["questions"])
            self.meta = saved.get("meta") or {}
        else:
            self.d = jb.from_map(first["state"], first["questions"])
            self.meta = {"title": first["title"], "from": "example"}
        self.status: dict = {"live": False, "signed_in": bool(state.me())}
        self.template_box.items = ([("Start from a template…", "")] + [(e["title"], e["slug"]) for e in jb.examples()]
                                   + [("Blank request", "__blank")])
        state.set_control_attr(self.template_box, "aria-label", "Start from a template")
        state.set_control_attr(self.state_box, "aria-label", "State")
        state.set_control_attr(self.state_box, "spellcheck", "false")
        self.questions.add_event_handler("x-edit", self._edited)
        self.questions.add_event_handler("x-redraw", self._redraw)
        self.questions.add_event_handler("x-del-q", self._del_q)
        self._key = anvil.js.report_exceptions(self._keydown)
        self.share_bar.visible = False
        if len(args) >= 2 and args[0] == "s":
            self._open_shared(args[1])
        if len(args) >= 2 and args[0] == "recipe":
            res = anvil.server.call("get_recipe", args[1])
            if isinstance(res, dict) and res.get("ok"):
                r = res["recipe"]
                self._load({"state": r["state"], "questions": r["questions"]},
                           {"title": r["title"], "summary": r.get("summary"), "category": r.get("category"),
                            "is_public": r.get("is_public"), "recipe_id": r["id"], "mine": r.get("mine"), "owner": r.get("owner")},
                           draw=False)
            else:
                state.toast((res or {}).get("error") or "That recipe wasn't found.", "error")
        s = state.call_quiet("jev_status")
        if isinstance(s, dict):
            self.status = s
        self._draw_all()

    # ---- share links
    def _open_shared(self, code):
        """#playground/s/<code>: load the request inside the link (old draft kept for Restore), or say it's broken."""
        router.replace("playground")
        data = jb.unpack(code)
        qs = data.get("q") if isinstance(data, dict) else None
        d = None
        if isinstance(qs, dict) and qs and all(isinstance(q, dict) and q.get("type") in ("choice", "noul", "score")
                                               for q in qs.values()):
            try:
                d = jb.from_map(data.get("s"), qs)
            except Exception:
                d = None
        self.share_bar.visible = True
        if d is None:
            self.share_msg.role = ["msg-error", "pg-shared-msg"]
            self.share_msg.text = ("That share link is broken or cut short, so your own draft is still here. "
                                   "Ask for the link again and copy the whole address.")
            self.restore_button.visible = False
            return
        prev = jb.store_get("pg_draft")
        had_prev = bool(prev and prev.get("questions"))
        if had_prev:
            jb.store_set("pg_prev", prev)
        self.d = d
        self.meta = {"title": str(data.get("t") or "Shared request")[:80], "from": "share"}
        self._persist()
        n = len(jb.problems(d))
        self.share_msg.role = ["msg-note", "pg-shared-msg"]
        self.share_msg.text = ("You opened a shared request. Press Run to try it, or change it: it's your copy now."
                               + (" It has %d thing%s to fix first (listed on the right)." % (n, "" if n == 1 else "s") if n else ""))
        self.restore_button.visible = had_prev

    @handle("restore_button", "click")
    def restore_button_click(self, **event_args):
        prev = jb.store_get("pg_prev")
        if not (prev and prev.get("questions")):
            state.toast("Your previous draft isn't in this browser any more.", "error")
            return
        jb.store_set("pg_prev", None)
        self._load({"state": prev.get("state"), "questions": prev["questions"]}, prev.get("meta") or {})
        self.share_bar.visible = False
        state.toast("Your previous draft is back.", "ok")

    @handle("share_close", "click")
    def share_close_click(self, **event_args):
        self.share_bar.visible = False

    @handle("share_button", "click")
    def share_button_click(self, **event_args):
        req = jb.to_req(self.d)
        if not req["questions"]:
            state.toast("Add a question first: there's nothing to share yet.", "error")
            return
        m = jb.loose(self.meta) or {}
        code = jb.pack({"v": 1, "t": str(m.get("title") or "Shared request")[:80], "s": req["state"], "q": req["questions"]})
        if not code:
            state.toast("This browser couldn't make a link. Try Save instead.", "error")
            return
        from ...Dialogs.ShareDraft import ShareDraft
        base = str(window.location.href).split("#")[0]
        res = alert(ShareDraft(link=base + "#playground/s/" + code, origin=str(window.location.origin),
                               problems=len(jb.problems(self.d))),
                    buttons=[], role="app-dialog", dismissible=True)
        if res == "save":
            self.save_button_click()

    # ---- the draft
    def _persist(self):
        req = jb.to_req(self.d)
        req["meta"] = self.meta
        jb.store_set("pg_draft", req)

    def _load(self, req, meta, draw=True):
        self.d = jb.from_map(req["state"], req["questions"])
        self.meta = meta or {}
        self.last, self.last_err = {}, None
        self._persist()
        if draw:
            self._draw_all()

    def _draw_all(self):
        m = jb.loose(self.meta) or {}
        self.title.text = str(m.get("title") or "Untitled request")
        self.title_badge.visible = bool(m.get("recipe_id"))
        if m.get("recipe_id"):
            self.title_badge.text = "your recipe" if m.get("mine") else "from " + str(m.get("owner") or "the community")
            self.title_badge.role = ["badge", "badge-brand"] if m.get("mine") else ["badge"]
        state.heading(self.title, 1)
        self.state_box.text = self.d["state"]
        self.state_kind.text = jb.state_kind(self.d["state"])
        self._draw_questions()
        self._draw_mode()
        self._draw_out()

    def _draw_questions(self):
        self.q_count.text = "Questions (%d)" % len(self.d["qs"])
        self.questions.items = [{"q": q, "i": i} for i, q in enumerate(self.d["qs"])]

    def _draw_mode(self):
        s, me = jb.loose(self.status), state.me()
        own = s.get("provider") == "selfhosted"
        live = bool(s.get("live"))
        self.mode_live.visible = live and bool(me)
        self.mode_signin.visible = live and not me
        self.mode_sim.visible = not live
        self.live_self.visible = own
        self.live_or.visible = not own
        self.self_model.text = self.or_model.text = s.get("model") or ""
        self.left.text = ", %d shared runs left today" % s["daily_left"] if s.get("daily_left") is not None else ""
        self.signin_target.text = "our open-source model server" if own else "real Jev"

    def _draw_out(self):
        req, probs = jb.to_req(self.d), jb.problems(self.d)
        for t, b in zip(TABS, [self.tab_answers, self.tab_request, self.tab_code]):
            b.role = ["pg-tab", "ic-" + {"answers": "sparkle", "request": "code", "code": "copy"}[t]] + (["on"] if self.tab == t else [])
            state.set_control_attr(b, "aria-pressed", "true" if self.tab == t else "false")
        lines = probs[:4] + (["…and %d more" % (len(probs) - 4)] if len(probs) > 4 else [])
        self.errors.visible = bool(probs)
        self.errors.text = "\n".join(lines)
        self.note.visible = False
        self.empty.visible = False
        self.code_hint.visible = self.tab == "code"
        if self.tab == "request":
            self.out.content = jb.code({"lang": "json", "label": "POST " + jb.ENDPOINT.replace("https://", ""), "code": jb.req_json(req)})
            return
        if self.tab == "code":
            self.out.content = jb.code(jb.gen_blocks(req))
            return
        if self.last_err:
            self.out.content = ""
            self.note.visible = False
            self.errors.visible = True
            self.errors.text = "\n".join(lines + [self.last_err])
            return
        if not self.last:
            self.out.content = ""
            self.empty.visible = True
            return
        r = jb.loose(self.last)["resp"]
        u = r.get("usage") or {}
        if self.last.get("note"):
            self.note.visible = True
            self.note.text = self.last["note"]
        flag = '<span class="jb-live-flag">Live</span>' if self.last.get("live") else '<span class="jb-sim-flag">Simulated · not Jev</span>'
        banner = ('<div class="pg-banner">' + flag + "<span>" + jb.esc(r.get("model") or "") + "</span>"
                  + ("<span>%d ms</span>" % self.last["ms"] if self.last.get("ms") is not None else "")
                  + "<span>%d input tokens</span><span>%s</span></div>" % (u.get("input_tokens") or 0, jb.money(u.get("cost") or 0)))
        cards = "".join(jb.answer_card(k, a) for k, a in (r.get("answers") or {}).items())
        raw = jb.code({"lang": "json", "label": "response.json", "code": jb.pretty(r)})
        self.out.content = (banner + '<div class="jb-ans">' + cards + '</div><details class="jb-raw"><summary>Raw response</summary>'
                         + raw + "</details>")

    # ---- editing
    @handle("state_box", "change")
    def state_box_change(self, **event_args):
        self.d["state"] = self.state_box.text or ""
        self.state_kind.text = jb.state_kind(self.d["state"])
        self._edited()

    def _edited(self, **event_args):
        self._persist()
        if self.tab != "answers":
            self._draw_out()
        elif bool(jb.problems(self.d)) != self.errors.visible:
            self._draw_out()

    def _redraw(self, **event_args):
        self._persist()
        self._draw_out()

    def _add(self, kind):
        if len(self.d["qs"]) >= 12:
            state.toast("Up to 12 questions per request here.", "error")
            return
        self.d["qs"].append(jb.blank(kind, self.d))
        self._persist()
        self._draw_questions()
        self._draw_out()

    @handle("add_choice", "click")
    def add_choice_click(self, **event_args):
        self._add("choice")

    @handle("add_noul", "click")
    def add_noul_click(self, **event_args):
        self._add("noul")

    @handle("add_score", "click")
    def add_score_click(self, **event_args):
        self._add("score")

    def _del_q(self, i, **event_args):
        self.d["qs"].pop(i)
        self._persist()
        self._draw_questions()
        self._draw_out()

    @handle("template_box", "change")
    def template_box_change(self, **event_args):
        v = self.template_box.selected_value
        self.template_box.selected_value = ""
        if v == "__blank":
            self._load({"state": "", "questions": {"is_true": {"type": "noul", "instructions": "", "criteria": {"true": "", "false": ""}}}},
                       {"title": "Untitled request"})
            return
        ex = jb.example(v) if v else None
        if ex:
            self._load({"state": ex["state"], "questions": ex["questions"]}, {"title": ex["title"], "from": "example"})

    # ---- output tabs
    def _set_tab(self, t):
        self.tab = t
        self._draw_out()

    @handle("tab_answers", "click")
    def tab_answers_click(self, **event_args):
        self._set_tab("answers")

    @handle("tab_request", "click")
    def tab_request_click(self, **event_args):
        self._set_tab("request")

    @handle("tab_code", "click")
    def tab_code_click(self, **event_args):
        self._set_tab("code")

    # ---- run
    @handle("run_button", "click")
    def run_button_click(self, **event_args):
        probs = jb.problems(self.d)
        self.tab, self.last_err = "answers", None
        if probs:
            self._draw_out()
            state.toast(probs[0], "error")
            return
        req = jb.to_req(self.d)
        if self.status.get("live") and state.me():
            t0 = window.Date.now()
            self.run_button.enabled = False
            try:
                res = anvil.server.call("run_live", req["state"], req["questions"])
            except Exception as e:
                res = {"ok": False, "error": str(e) or "The live run didn't work."}
            finally:
                self.run_button.enabled = True
            if isinstance(res, dict) and res.get("ok"):
                self.last = {"resp": res["response"], "live": True, "ms": res.get("ms") or int(window.Date.now() - t0)}
                if self.status.get("daily_left") is not None:
                    self.status["daily_left"] = max(0, self.status["daily_left"] - 1)
                    self._draw_mode()
            else:
                self.last = {"resp": jb.simulate(req["state"], req["questions"]), "live": False,
                             "note": str(jb.loose(res or {}).get("error") or "") + " Showing the simulator instead."}
            self._draw_out()
            return
        t1 = window.performance.now()
        resp = jb.simulate(req["state"], req["questions"])
        self.last = {"resp": resp, "live": False, "ms": max(1, int(round(window.performance.now() - t1)))}
        self._draw_out()

    def _keydown(self, event):
        if (getattr(event, "ctrlKey", False) or getattr(event, "metaKey", False)) and getattr(event, "key", None) == "Enter":
            event.preventDefault()
            self.run_button_click()

    def start(self):
        window.document.addEventListener("keydown", self._key)

    def leave(self):
        window.document.removeEventListener("keydown", self._key)

    def signin_click(self, event):
        router.remember_after("#playground")

    # ---- save
    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        if not state.me():
            router.remember_after("#playground")
            router.go("auth", "signup")
            state.toast("Create a free account to save recipes.")
            return
        probs = jb.problems(self.d)
        if probs:
            state.toast(probs[0], "error")
            return
        from ...Dialogs.SaveRecipe import SaveRecipe
        req = jb.to_req(self.d)
        data_state = req["state"] if isinstance(req["state"], str) else jb.state_text(req["state"])
        rcp = alert(SaveRecipe(meta=self.meta or {}, state_text=data_state, questions=req["questions"]),
                    buttons=[], role="app-dialog", dismissible=True)
        if rcp:
            self.meta = {"title": rcp["title"], "summary": rcp.get("summary"), "category": rcp.get("category"),
                         "is_public": rcp.get("is_public"), "recipe_id": rcp["id"], "mine": True}
            self._persist()
            self._draw_all()
