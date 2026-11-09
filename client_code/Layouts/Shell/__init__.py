import datetime

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import ShellTemplate
from ... import auth, router, state

THEMES = ["auto", "light", "dark"]


class Shell(ShellTemplate):
    """The frame around every page: header (the six-page menu for everyone; Sign in / Join free or the account button),
    the account menu, the footer and the phone tab bar (Guide, Use cases, Playground, Recipes + a More sheet).
    Pages use it with <anvil-form layout="Jev_Buddy.Layouts.Shell">.

    Anvil keeps ONE Shell while pages come and go (open_form only swaps the "content" slot when the layout matches),
    so everything that depends on who is signed in or which page is open is drawn in refresh(), which router.show()
    calls after every page change. Never only in __init__."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.copyright_label.text = ("© %d Jev Buddy · An independent guide, not affiliated with TypeSafe or OpenRouter. "
                                     "Jev is TypeSafe's model; prices, limits and APIs can change, so check the official docs "
                                     "before you ship." % datetime.date.today().year)
        self._outside = anvil.js.report_exceptions(self._close_outside)
        self._keys = anvil.js.report_exceptions(self._key)
        self.refresh("")

    def refresh(self, page):
        me = state.me()
        node = anvil.js.get_dom_node(self)  # a layout's DOM node IS its template root (.ui-shell)
        root = node if node.classList.contains("ui-shell") else node.querySelector(".ui-shell")
        if root:
            for c in [str(x) for x in root.className.split(" ")]:
                if c.startswith("page-"):
                    root.classList.remove(c)
            root.classList.add("page-" + (page or "none"))
            root.classList.toggle("signed-in", bool(me))
            root.classList.toggle("signed-out", not me)
        self.member_actions.visible = bool(me)
        self.guest_actions.visible = not me and page != "auth"
        self.menu.visible = False
        self.sheet.visible = False
        state.set_attr(self.more_link, "aria-expanded", "false")
        links = [{"page": p, "label": label, "icon": icon, "on": p == page} for p, label, icon in router.NAV]
        self.nav_panel.items = links
        self.tab_panel.items = links[:4]
        self.more_link.classes["on"] = page not in [p for p, _, _ in router.NAV[:4]] and page != "landing"
        self.sheet_member.visible = bool(me)
        self.sheet_guest.visible = not me
        self.sheet_admin.visible = bool(me and me.get("is_admin"))
        if me:
            self.avatar_button.text = state.initials(me.get("name"))
            self.menu_name.text = me.get("name") or ""
            self.menu_email.text = me.get("email") or ""
            self.admin_link.visible = bool(me.get("is_admin"))
        self._show_theme()

    # ---- account menu and the phone's More sheet
    @handle("avatar_button", "click")
    def avatar_button_click(self, **event_args):
        self.menu.visible = not self.menu.visible

    def more_click(self, event):
        event.preventDefault()
        self.sheet.visible = not self.sheet.visible
        state.set_attr(self.more_link, "aria-expanded", "true" if self.sheet.visible else "false")

    def _close_outside(self, event):
        t = event.target
        if self.menu.visible and not t.closest(".anvil-role-avatar, .ui-menu .ui-seg"):
            self.menu.visible = False
        if self.sheet.visible and not t.closest(".ui-tabbar .more, .jb-sheet .ui-seg"):
            self.sheet.visible = False
            state.set_attr(self.more_link, "aria-expanded", "false")

    def _key(self, event):
        if getattr(event, "key", None) == "Escape":
            self.menu.visible = False
            self.sheet.visible = False

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("click", self._outside, True)
        window.document.addEventListener("keydown", self._keys)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("click", self._outside, True)
        window.document.removeEventListener("keydown", self._keys)

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-set"))
        self._show_theme()

    def _show_theme(self):
        t = state.theme()
        for name, a, b in zip(THEMES, [self.theme_auto, self.theme_light, self.theme_dark],
                              [self.sheet_auto, self.sheet_light, self.sheet_dark]):
            a.classes["on"] = name == t
            b.classes["on"] = name == t

    def feedback_click(self, event):
        self.menu.visible = False
        self.sheet.visible = False
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        state.toast("Signed out. See you soon!")
        router.go("landing")
