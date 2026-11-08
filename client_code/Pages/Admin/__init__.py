import anvil.server
from anvil import *

from ._anvil_designer import AdminTemplate
from ... import state

TABS = ["overview", "feedback", "users", "jev", "recipes", "demo"]


class Admin(AdminTemplate):
    """#admin/<tab>: overview numbers, the old feedback inbox, users (admin / active switches), the Jev API settings for
    live playground runs (OpenRouter key and model, or the admin's own open-source server; limits; a test call; usage),
    recipe moderation (hide shared recipes) and the demo data. Each tab is its own address."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tab = args[0] if args and args[0] in TABS else "overview"
        self._filter = "new"
        parts = {"overview": self.overview_part, "feedback": self.feedback_part, "users": self.users_part,
                 "jev": self.jev_part, "recipes": self.recipes_part, "demo": self.demo_part}
        tabs = {"overview": self.tab_overview, "feedback": self.tab_feedback, "users": self.tab_users,
                "jev": self.tab_jev, "recipes": self.tab_recipes, "demo": self.tab_demo}
        for name in TABS:
            parts[name].visible = name == self.tab
            tabs[name].classes["on"] = name == self.tab
        self.feedback_panel.add_event_handler("x-changed", self._feedback_changed)
        self.recipes_panel.add_event_handler("x-changed", lambda **e: self._recipes())
        getattr(self, "_" + self.tab)()

    # ---- overview
    def _overview(self):
        d = state.call("admin_overview")
        self.s_users.text, self.s_admins.text = str(d["users"]), str(d["admins"])
        self.s_admins_label.text = "admin" if d["admins"] == 1 else "admins"
        self.s_feedback.text, self.s_recipes.text = str(d["feedback_new"]), str(d["recipes"])
        self.s_public.text, self.s_runs.text = str(d["public_recipes"]), str(d["runs_today"])
        self.live_line.text = "Live playground runs are %s. %s" % (
            "on" if d["live"] else "off", "" if d["live"] else "Visitors see the simulator. Switch live runs on in the Jev API tab.")
        self.demo_line.text = "Demo data is %s (%d demo people). Manage it in the Demo data tab." % (
            d["demo"]["state"], d["demo"]["counts"].get("users", 0))

    # ---- feedback
    def _feedback(self):
        d = state.call("list_feedback", None)
        items = [i for i in d["items"] if self._filter == "all" or i["status"] == self._filter]
        self.feedback_panel.items = items
        self.no_feedback.visible = not items
        labels = {"new": "New", "read": "Read", "done": "Done", "all": "All"}
        for key, el in (("new", self.f_new), ("read", self.f_read), ("done", self.f_done), ("all", self.f_all)):
            n = len(d["items"]) if key == "all" else d["counts"].get(key, 0)
            el.text = "%s (%d)" % (labels[key], n)
            el.role = ["seg", "on"] if key == self._filter else ["seg"]

    def _set_filter(self, value):
        self._filter = value
        self._feedback()

    @handle("f_new", "click")
    def f_new_click(self, **event_args):
        self._set_filter("new")

    @handle("f_read", "click")
    def f_read_click(self, **event_args):
        self._set_filter("read")

    @handle("f_done", "click")
    def f_done_click(self, **event_args):
        self._set_filter("done")

    @handle("f_all", "click")
    def f_all_click(self, **event_args):
        self._set_filter("all")

    def _feedback_changed(self, **event_args):
        self._feedback()

    # ---- users
    def _users(self, query=None):
        d = state.call("list_users", query or None)
        self.users_panel.items = d["users"]
        self.users_count.text = state.plural(d["total"], "person", "people")

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self._users(self.search_box.text)

    @handle("search_button", "click")
    def search_button_click(self, **event_args):
        self._users(self.search_box.text)

    # ---- Jev API
    def _jev(self, s=None):
        s = s or state.call("admin_jev_settings")
        self.s = s
        own = s["provider"] == "selfhosted"
        self.prov_or.selected = not own
        self.prov_self.selected = own
        self._show_provider()
        self.key_state.text = "(saved, ends %s)" % s["key_hint"] if s["has_key"] else "(not set)"
        self.key_box.text = ""
        self.key_box.placeholder = "Leave empty to keep the saved key" if s["has_key"] else "sk-or-v1-..."
        self.model_box.text = s["model"]
        self.clear_or.visible = bool(s["has_key"])
        self.url_box.text = s["base_url"] or ""
        self.local_key_state.text = "(saved, ends %s)" % s["local_key_hint"] if s["has_local_key"] else "(optional)"
        self.local_key_box.text = ""
        self.local_key_box.placeholder = ("Leave empty to keep the saved key" if s["has_local_key"]
                                          else "The value of LAYA_API_KEY, KEV_API_KEY…")
        self.local_model_box.text = s["local_model"] or ""
        self.clear_self.visible = bool(s["base_url"])
        self.cap_box.text, self.per_box.text = s["daily_cap"], s["per_user_hour"]
        self.enabled_box.checked = bool(s["enabled"])
        self.enabled_hint.visible = not s["ready"]
        self.test_jev.visible = bool(s["ready"])
        self.test_jev.text = "Test the server" if own else "Test the key"
        self.endpoint_line.visible = bool(s["ready"])
        self.endpoint_line.text = "Live runs go to %s%s." % (s["endpoint"], " (model %s)" % s["local_model"] if own and s["local_model"] else "")
        self.jev_result.visible = False
        self.u_live.text = "On" if s["live"] else "Off"
        self.u_today.text, self.u_errors.text = str(s["runs_today"]), str(s["errors_today"])
        self.u_total.text = str(s["runs_total"])
        self.u_cost.text = "$%.5f" % (s.get("cost_total") or 0)
        self.u_ms.text = "%d ms" % s["avg_ms"]
        for box, auto in ((self.key_box, "off"), (self.local_key_box, "off")):
            state.set_control_attr(box, "autocomplete", auto)
        for box in (self.model_box, self.url_box, self.local_model_box):
            state.set_control_attr(box, "spellcheck", "false")

    def _show_provider(self):
        own = self.prov_self.selected
        self.or_fields.visible = not own
        self.self_fields.visible = own
        self.prov_or_box.classes["on"] = not own
        self.prov_self_box.classes["on"] = own

    @handle("prov_or", "clicked")
    def prov_or_clicked(self, **event_args):
        self._show_provider()

    @handle("prov_self", "clicked")
    def prov_self_clicked(self, **event_args):
        self._show_provider()

    @handle("save_jev", "click")
    def save_jev_click(self, **event_args):
        data = {"provider": "selfhosted" if self.prov_self.selected else "openrouter", "key": self.key_box.text or "",
                "model": self.model_box.text or "", "base_url": self.url_box.text or "", "local_key": self.local_key_box.text or "",
                "local_model": self.local_model_box.text or "", "daily_cap": self.cap_box.text, "per_user_hour": self.per_box.text,
                "enabled": bool(self.enabled_box.checked)}
        r = state.call("admin_save_jev_settings", data)
        if r:
            state.toast("Saved", "ok")
            self._jev(r["settings"])

    @handle("test_jev", "click")
    def test_jev_click(self, **event_args):
        self.test_jev.enabled = False
        try:
            r = anvil.server.call("admin_test_jev")
        finally:
            self.test_jev.enabled = True
        self.jev_result.visible = True
        if isinstance(r, dict) and r.get("ok"):
            a = (r["response"].get("answers") or {}).get("is_refund") or {}
            self.jev_result.role = "msg-note"
            self.jev_result.text = "It works: %s answered is_refund = %s in %d ms." % (
                r["response"].get("model") or "your server", a.get("noul"), r["ms"])
        else:
            self.jev_result.role = "msg-error"
            self.jev_result.text = (r or {}).get("error") or "The test didn't work."

    def _clear(self, which):
        own = which == "selfhosted"
        if confirm("The address and the server key are removed. If live runs used it, they switch off." if own else
                   "If live runs used it, they switch off and the playground goes back to the simulator.",
                   title="Forget your server?" if own else "Remove the OpenRouter key?",
                   buttons=[("Cancel", False), ("Forget" if own else "Remove", True)], role="app-dialog"):
            r = state.call("admin_clear_jev_key", which)
            if r:
                state.toast("Server forgotten" if own else "Key removed", "ok")
                self._jev(r["settings"])

    @handle("clear_or", "click")
    def clear_or_click(self, **event_args):
        self._clear("openrouter")

    @handle("clear_self", "click")
    def clear_self_click(self, **event_args):
        self._clear("selfhosted")

    # ---- recipes
    def _recipes(self):
        d = state.call("admin_list_recipes")
        self.recipes_panel.items = d["items"]
        self.no_recipes.visible = not d["items"]

    # ---- demo data
    def _demo(self):
        d = state.call("admin_overview")["demo"]
        counts = ", ".join("%s %s" % (v, k) for k, v in d["counts"].items())
        self.demo_status.text = "Status: %s · %s" % (d["state"], counts)
        self.demo_load_button.text = "Reload demo data" if d["state"] == "loaded" else "Load demo data"

    @handle("demo_load_button", "click")
    def demo_load_button_click(self, **event_args):
        if confirm("Demo people and content are added (any old demo rows are replaced).", title="Load the demo data?",
                   buttons=[("Cancel", False), ("Load", True)], role="app-dialog"):
            if state.call("demo_load"):
                state.toast("Done", "ok")
                self._demo()

    @handle("demo_remove_button", "click")
    def demo_remove_button_click(self, **event_args):
        if confirm("Every demo row is deleted. Real data stays.", title="Remove the demo data?",
                   buttons=[("Cancel", False), ("Remove", True)], role="app-dialog"):
            if state.call("demo_remove"):
                state.toast("Done", "ok")
                self._demo()
