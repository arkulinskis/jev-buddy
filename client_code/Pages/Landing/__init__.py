from anvil import *

from ._anvil_designer import LandingTemplate
from ... import jb, state

# The app's video on the Addanapp YouTube channel (APP_MAKER/youtube/manifest.json), shown in the Watch section.
YT_VIDEO = "pGgzeKsxuk0"

FRAGILE = ('reply = llm("Classify this ticket. Answer ONLY with JSON like "\n            \'{"team": ..., "urgent": true/false}: \' + ticket)\n'
           'try:\n    data = json.loads(reply)        # sometimes it adds a sentence first\nexcept json.JSONDecodeError:\n'
           '    data = retry_with_stricter_prompt(ticket)\nteam = data.get("team", "unknown")    # "Billing", "billing team", "finance"...')
SOLID = ('answers, _ = ask(ticket, {\n    "team": {"type": "choice", "instructions": "Which team?",\n'
         '             "criteria": {"billing": "...", "tech": "...", "sales": "..."}},\n'
         '    "urgent": {"type": "noul", "instructions": "Is someone blocked right now?",\n'
         '               "criteria": {"true": "...", "false": "..."}},\n})\n'
         'team = answers["team"]["choice"]          # always one of your labels\nif answers["team"]["confidence"] < 0.6:\n    escalate(ticket)')


class Landing(LandingTemplate):
    """#landing (Persuade; also "About" for members): the promise and the animated decision terminal
    (Components/Hero), the Watch section (the YouTube video), the numbers, LLM vs Jev, the three primitives, how it
    works, six use cases, who it's for, the open-source band, FAQ. Static copy lives in the template; the code blocks
    and probability bars come from the engine (jb.py)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        me = state.me()
        self.join_link.visible = not me
        if me:
            self.dom_nodes["band_text"].textContent = "My recipes"
            state.set_attr(self.band_link, "href", "#recipes/mine")
        self.code_llm.content = jb.code({"lang": "python", "label": "fragile.py", "code": FRAGILE})
        self.code_jev.content = jb.code({"lang": "python", "label": "solid.py", "code": SOLID})
        self.prim_probs.content = jb.probs({"billing": 0.91, "tech": 0.06, "sales": 0.03})
        self.uses_panel.items = jb.examples()[:6]
        self.dom_nodes["yt_cover"].addEventListener("click", self._play)

    def _play(self, event):
        """Swap the video's cover for YouTube's player (privacy-enhanced); nothing loads from YouTube before this click."""
        self.dom_nodes["yt_frame"].innerHTML = (
            '<iframe src="https://www.youtube-nocookie.com/embed/' + YT_VIDEO + '?autoplay=1&rel=0&playsinline=1" '
            'title="Jev Buddy video" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen '
            'referrerpolicy="strict-origin-when-cross-origin"></iframe>')
