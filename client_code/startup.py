"""The app starts here (anvil.yaml: startup module). One server call to learn who is signed in (Anvil's loading
spinner shows meanwhile), the Privacy & Terms kit, then the page for the address in the browser bar."""
import anvil.server
from anvil.js import window

from . import legal, router, state

LEGAL_THEME = {"accent": "#4f46e5"}  # colours for the Privacy & Terms page (match --c-brand in app.css)

legal.setup(LEGAL_THEME)
window.JB_TOAST = state.toast  # the JavaScript engine (jb.js: "Copied to the clipboard") shows toasts through Python
state.set_me(anvil.server.call("get_me"))
if state.me():
    legal.refresh_soon()
router.start()
