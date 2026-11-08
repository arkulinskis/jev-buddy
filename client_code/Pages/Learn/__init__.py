from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import LearnTemplate
from ... import jb, router, state


def read_map():
    """{chapter id: time first read} kept in this browser (store 'read', same key as the JavaScript version)."""
    r = jb.store_get("read", {})
    return r if isinstance(r, dict) else {}


def mark_read(cid):
    r = read_map()
    if cid not in r:
        r[cid] = window.Date.now()
        jb.store_set("read", r)


def groups(chapters, make):
    out = []
    for c in chapters:
        g = [x for x in out if x["name"] == c["group"]]
        if not g:
            out.append({"name": c["group"], "items": []})
            g = [out[-1]]
        g[0]["items"].append(make(c))
    return out


class Learn(LearnTemplate):
    """#learn: the guide's index (16 chapters in 4 groups, read ticks, progress, Continue reading).
    #learn/<chapter>: one chapter: the chapter list with ticks beside it (a picker on phones), the chapter text from
    the engine (JB.chapter in jb-content.js: code tabs remember the reader's language), previous / next.
    A chapter counts as read when its end scrolls into view or after 45 seconds."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.chs = jb.chapters()
        ids = [c["id"] for c in self.chs]
        self.cid = args[0] if args and args[0] in ids else None
        self._timer = None
        self._io = None
        self.index_part.visible = self.cid is None
        self.chapter_part.visible = self.cid is not None
        if self.cid:
            self._chapter()
        else:
            self._index()

    def _progress(self, count_label, box, bar):
        r = read_map()
        n = len([c for c in self.chs if c["id"] in r])
        count_label.text = "%d / %d" % (n, len(self.chs))
        bar.style.width = "%d%%" % int(round(n * 100.0 / len(self.chs)))
        state.set_attr(box, "aria-valuenow", n)
        state.set_attr(box, "aria-valuemin", 0)
        state.set_attr(box, "aria-valuemax", len(self.chs))

    # ---- the index
    def _index(self):
        r = read_map()
        self._progress(self.prog_count, self.prog_bar_box, self.dom_nodes["prog_bar"])
        first = ([c for c in self.chs if c["id"] not in r] or self.chs)[0]
        state.set_attr(self.continue_link, "href", router.href("learn", first["id"]))
        self.continue_label.text = "Continue reading" if r else "Start with chapter 1"
        self.groups.items = groups(self.chs, lambda c: dict(c, read=c["id"] in r))

    # ---- one chapter
    def _chapter(self):
        r = read_map()
        i = [c["id"] for c in self.chs].index(self.cid)
        ch = self.chs[i]
        prev = self.chs[i - 1] if i > 0 else None
        nxt = self.chs[i + 1] if i + 1 < len(self.chs) else None
        router.title(ch["title"])
        self._progress(self.side_count, self.side_bar_box, self.dom_nodes["side_bar"])
        self.side_groups.items = groups(self.chs, lambda c: {"id": c["id"], "title": c["title"], "read": c["id"] in r,
                                                             "on": c["id"] == self.cid})
        self.pick_label.text = "Chapter %d of %d" % (i + 1, len(self.chs))
        self.pick.items = [("%d. %s%s" % (k + 1, c["title"], "  ✓" if c["id"] in r else ""), c["id"]) for k, c in enumerate(self.chs)]
        self.pick.selected_value = self.cid
        state.set_control_attr(self.pick, "aria-label", "Chapter")
        self.group_badge.text = ch["group"]
        self.mins.text = "%d min read" % ch["mins"]
        self.title.text = ch["title"]
        state.heading(self.title, 1)
        self.body.content = str(window.JB.chapter(self.cid))
        self.prev_link.visible = prev is not None
        if prev:
            state.set_attr(self.prev_link, "href", router.href("learn", prev["id"]))
            self.prev_title.text = prev["title"]
        if nxt:
            state.set_attr(self.next_link, "href", router.href("learn", nxt["id"]))
            self.next_title.text = nxt["title"]
        else:
            self.dom_nodes["next_small"].textContent = "You made it →"
            self.next_title.text = "Try it in the playground"

    @handle("pick", "change")
    def pick_change(self, **event_args):
        if self.pick.selected_value and self.pick.selected_value != self.cid:
            router.go("learn", self.pick.selected_value)

    def start(self):
        """After the page is on screen: watch for the chapter's end, and the 45-second fallback."""
        if not self.cid:
            return
        cid = self.cid

        def seen(entries, *rest):
            if entries[0].isIntersecting:
                mark_read(cid)
                self._stop_io()

        if window.get("IntersectionObserver"):
            self._io = anvil.js.new(window.IntersectionObserver, anvil.js.report_exceptions(seen))
            self._io.observe(self.dom_nodes["end"])
        self._timer = window.setTimeout(lambda: mark_read(cid), 45000)

    def _stop_io(self):
        if self._io is not None:
            self._io.disconnect()
            self._io = None

    def leave(self):
        self._stop_io()
        if self._timer is not None:
            window.clearTimeout(self._timer)
            self._timer = None
