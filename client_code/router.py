"""Page addresses: #name/arg1/arg2 -> a page Form (open_form), with sign-in rules.

Links in templates are plain <a href="#learn">; code calls router.go("recipes", id).

    PAGES[name] = (who may open it, browser-tab title)   who: None = anyone, "guest" = signed out only, "user", "admin"
    NAV = the main menu (header for everyone; the phone tab bar shows the first 4, the rest are under More):
          (page, label, icon). Jev Buddy is a public guide, so the menu is the same signed in or out.
New page: add it to PAGES, to _form() and (if it belongs in the menu) to NAV.
Same addresses as the JavaScript version (#learn/<chapter>, #examples/<slug>, #playground/recipe/<id>,
#recipes/mine, #recipes/<id>, #opensource/<section>, #tools/cost/<volume>/<tokens>/<questions>, #admin/<tab>).
"""
import anvil
import anvil.js
from anvil.js import window

from . import state

PAGES = {
    "landing": (None, "The developer guide to Jev"),
    "learn": (None, "Guide"),
    "examples": (None, "Use cases"),
    "playground": (None, "Playground"),
    "recipes": (None, "Recipes"),
    "opensource": (None, "Open-source alternatives to Jev"),
    "tools": (None, "Tools"),
    "auth": ("guest", "Sign in"),
    "profile": ("user", "Your profile"),
    "admin": ("admin", "Admin"),
}
NAV = [("learn", "Guide", "book"), ("examples", "Use cases", "grid"), ("playground", "Playground", "play"),
       ("recipes", "Recipes", "users"), ("opensource", "Open source", "unlock"), ("tools", "Tools", "calc")]
HOME = "learn"          # first page after signing in
APP_NAME = "Jev Buddy"
_r: dict = {"after": "", "listening": False, "page": None}


def _form(name):
    """The page's Form class (imported when first needed, so start-up stays quick)."""
    if name == "landing":
        from .Pages.Landing import Landing
        return Landing
    if name == "learn":
        from .Pages.Learn import Learn
        return Learn
    if name == "examples":
        from .Pages.Examples import Examples
        return Examples
    if name == "playground":
        from .Pages.Playground import Playground
        return Playground
    if name == "recipes":
        from .Pages.Recipes import Recipes
        return Recipes
    if name == "opensource":
        from .Pages.Opensource import Opensource
        return Opensource
    if name == "tools":
        from .Pages.Tools import Tools
        return Tools
    if name == "auth":
        from .Pages.Auth import Auth
        return Auth
    if name == "profile":
        from .Pages.Profile import Profile
        return Profile
    from .Pages.Admin import Admin
    return Admin


def parse(hash_text):
    h = (hash_text or "").lstrip("#").lstrip("!").lstrip("/").split("?")[0]
    parts = [window.decodeURIComponent(p) for p in h.split("/") if p]
    return (parts[0] if parts else ""), parts[1:]


def href(name, *args):
    """'#name/arg1/arg2' with every part URL-encoded (row ids contain brackets and commas)."""
    return "#" + "/".join([name] + [window.encodeURIComponent(str(a)) for a in args if a not in (None, "")])


def home_page():
    return HOME if state.me() else "landing"


def title(text):
    """A page that knows a better browser-tab title (a chapter, a use case) sets it here."""
    window.document.title = text + " · " + APP_NAME


def show():
    """Open the page for the current address."""
    name, args = parse(window.location.hash)
    if name not in PAGES:
        name, args = home_page(), []
    who = PAGES[name][0]
    if who == "guest" and state.me():
        name, args = HOME, []
    elif who in ("user", "admin") and not state.me():
        _r["after"] = window.location.hash
        name, args = "auth", []
    elif who == "admin" and not state.is_admin():
        state.toast("That page is for admins only.", "error")
        name, args = HOME, []
    old = _r["page"]
    if old is not None and hasattr(old, "leave"):
        old.leave()  # stop timers, key listeners and observers of the page being left
    title(PAGES[name][1])
    window.UI_READY = False
    page = _form(name)(args=args)
    _r["page"] = page
    anvil.open_form(page)
    shell = getattr(page, "layout", None)
    if shell is not None and hasattr(shell, "refresh"):
        shell.refresh(name)  # Anvil reuses the layout between pages: tell it who is signed in and which page is open
    window.scrollTo(0, 0)
    if hasattr(page, "start"):
        page.start()  # work that needs the page on screen (scrolling to a section, an animation, observers)
    window.UI_READY = True  # tests and screenshots wait for this


def go(name, *args):
    """Go to a page. Same address again = reload the page."""
    target = href(name, *args)
    if window.location.hash == target:
        show()
    else:
        window.location.hash = target


def replace(name, *args):
    """Change the address without opening anything (a page that switches its own view)."""
    window.history.replaceState(None, "", href(name, *args))


def after_sign_in():
    """Where to go once someone signs in: the page they were heading for, or home."""
    target = _r["after"]
    _r["after"] = ""
    if target and target != window.location.hash:
        window.location.hash = target
    else:
        go(HOME)


def remember_after(target):
    _r["after"] = target


def _on_hash(event):
    show()


def start():
    if not _r["listening"]:
        window.addEventListener("hashchange", anvil.js.report_exceptions(_on_hash))
        _r["listening"] = True
    show()
