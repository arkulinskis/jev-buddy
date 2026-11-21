from anvil import *
from anvil.js import window

from ._anvil_designer import ShareDraftTemplate
from ... import jb, state

MAX_LINK = 6000  # characters: longer links break in some chat apps, issue trackers and browsers


class ShareDraft(ShareDraftTemplate):
    """Playground -> Share: the link (the request is packed inside it, nothing is stored on the server), Copy, and a
    "Try it in Jev Buddy" README badge (theme/assets/badge.svg) as Markdown or HTML. Links over MAX_LINK characters
    offer "Save as a recipe" instead (closes with "save").
    alert(ShareDraft(link=..., origin=..., problems=0), buttons=[], role="app-dialog")."""

    def __init__(self, link="", origin="", problems=0, **properties):
        super().__init__(**properties)
        self.share_link, self.md_code, self.html_code = link, "", ""
        state.heading(self.heading, 2)
        too_long = len(link) > MAX_LINK
        self.long_part.visible = too_long
        self.link_part.visible = not too_long
        self.intro.text = ("Anyone with the link opens this exact request in the playground, no account needed. "
                           "The request travels inside the link itself, so nothing is stored on our server.")
        if too_long:
            self.long_msg.text = ("This request makes a %s-character link, more than the %s that chat apps and issue "
                                  "trackers handle reliably. Save it as a recipe (free account), tick \"Share it in "
                                  "Community recipes\" and share the recipe's page instead."
                                  % (jb.thousands(len(link)), jb.thousands(MAX_LINK)))
            return
        self.link_box.text = link
        state.set_control_attr(self.link_box, "readonly", "readonly")
        state.set_control_attr(self.link_box, "aria-label", "Share link")
        badge = origin.rstrip("/") + "/_/theme/badge.svg"
        self.md_code = "[![Try it in Jev Buddy](%s)](%s)" % (badge, link)
        self.html_code = '<a href="%s"><img src="%s" alt="Try it in Jev Buddy" height="20"></a>' % (
            link.replace("&", "&amp;").replace('"', "&quot;"), badge)
        self.md_box.text = self.md_code
        state.set_control_attr(self.md_box, "readonly", "readonly")
        state.set_control_attr(self.md_box, "spellcheck", "false")
        self.dom_nodes["badge_link"].setAttribute("href", link)
        if problems:
            self.problems_note.visible = True
            self.problems_note.text = ("Heads up: the request still has %d thing%s to fix, and the link shares it "
                                       "as it is." % (problems, "" if problems == 1 else "s"))

    def _copy(self, text):
        window.JB.copy(text)

    @handle("copy_link", "click")
    def copy_link_click(self, **event_args):
        self._copy(self.share_link)

    @handle("copy_md", "click")
    def copy_md_click(self, **event_args):
        self._copy(self.md_code)

    @handle("copy_html", "click")
    def copy_html_click(self, **event_args):
        self._copy(self.html_code)

    @handle("link_box", "focus")
    def link_box_focus(self, **event_args):
        getattr(state.control(self.link_box), "select")()

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("long_close", "click")
    def long_close_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("long_save", "click")
    def long_save_click(self, **event_args):
        self.raise_event("x-close-alert", value="save")
