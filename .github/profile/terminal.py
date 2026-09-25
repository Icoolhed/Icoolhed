"""Terminal panel: a looping shell session on a rack-mounted monitor.

The commands and their output come from profile.json (terminal.session);
an output of "@board" expands into a kubectl-style table of the projects.

Every glyph sits on a fixed character grid. Each run of text is pinned to
its grid width with textLength, so table columns, the typing cursor and the
coloured prompt line up in whatever monospace font the viewer has.

The animation is one shared loop: type, run, next command, hold, `clear`.
An animation-delay only applies to the first iteration, so every element
that appears at its own moment gets its own @keyframes, with percentages
taken from the loop length. Without animation (reduced motion, static
renderers) the SVG shows the finished session.

The loop is finite: an <img> SVG with any running animation is repainted every
frame, so the session plays twice and then rests. The second pass ends partway
through its hold, where every loop animation already equals the finished
screen; the cursor keeps blinking a little longer, then stays lit. No
animation fills forwards: once they end, the plain (static) SVG shows.
"""

from __future__ import annotations

import math
import re
from datetime import date

from theme import (AMBER, CYAN, DIM, EDGE, GREEN, MAGENTA, PURPLE, RED,
                   TEXT, esc, fmt, label, led, panel_gradient, rng,
                   scanlines_pattern, screw, svg_doc)

W = 900
FS = 20                  # terminal font size; big enough to survive a phone-width README
ADV = FS * 0.6           # character grid pitch
LH = 29                  # line pitch
BLOCK_GAP = 11           # extra air above each new prompt
OUT = "#9CAECB"          # command output, a step below TEXT

# geometry: rack ears either side, a bezel, then the glass
EAR = 40
BEZ_X, BEZ_Y, BEZ_PAD = EAR + 10, 44, 7
GLASS_X = BEZ_X + BEZ_PAD
GLASS_Y = BEZ_Y + BEZ_PAD
GLASS_W = W - 2 * GLASS_X
TITLE_H = 30             # title bar across the top of the glass
PAD_X = 22               # text inset from the glass edge
X0 = GLASS_X + PAD_X     # column 0
COLS = int((GLASS_W - 2 * PAD_X) / ADV)
FIRST_BASE = GLASS_Y + TITLE_H + 34
PAD_BOTTOM = 16          # glass below the last baseline's descenders

# Status colours match the project module cards, so a project reads the same
# everywhere on the page. Anything unrecognised is amber: worth a look, not an alarm.
STATUS_COLORS = {"running": GREEN, "public": CYAN, "stable": PURPLE}
FAILED = {"stopped", "failed", "error", "crashloopbackoff"}

# timing, seconds. Every visitor starts watching at 0, so the session gets to
# the point quickly and the finished screen owns most of the loop.
T_FIRST_WAIT = 0.5       # the first prompt idles, cursor lit, before typing
T_WAIT = 0.6             # idle before each later command
T_KEY = (0.035, 0.045)   # per keystroke: base + random spread
T_SPACE = (0.03, 0.05)   # extra around a space, where a typist hesitates
T_ENTER = 0.25           # last keystroke to first output line
T_LINE = 0.08            # between plain output lines
T_ROW = 0.045            # between table rows
T_NEXT = 0.12            # last output line to the next prompt
T_HOLD = 9.0             # the finished screen stays up this long
T_TAIL = 0.25            # blank screen after `clear`, before the loop restarts
BLINK = 1.06             # cursor blink period
PLAYS = 2                # the session is typed this many times, then rests
SETTLE = 45.0            # the cursor blinks until about here (s after load), then stays lit
# Keystrokes closer than this share one TX flash. Each flash-off is a repaint of
# the whole bloomed screen, so a typed word keeps the LED lit instead.
FLASH_MERGE = 0.15

READY_RE = re.compile(r"\d+/\d+|-")    # what kubectl can print under READY


# --- text on the grid ---------------------------------------------------------------
def _runs(line: str) -> list[tuple[int, str]]:
    """Split a line into (column, text) runs at gaps of two or more spaces.

    Wide gaps become column offsets instead of whitespace, so nothing depends
    on how a renderer treats repeated spaces.
    """
    return [(m.start(), m.group()) for m in re.finditer(r"\S+(?: \S+)*", line)]


def _text(col: float, y: float, s: str, color: str, *, bold: bool = False) -> str:
    """Text starting at grid column `col`, stretched or squeezed to exactly len(s) cells."""
    fit = f" textLength='{fmt(len(s) * ADV)}' lengthAdjust='spacing'" if len(s) > 1 else ""
    weight = " font-weight='700'" if bold else ""
    return (f"<text x='{fmt(X0 + col * ADV)}' y='{fmt(y)}' fill='{color}'{fit}{weight}>"
            f"{esc(s)}</text>")


def _wrap(line: str, width: int) -> list[str]:
    """Wrap on spaces, keeping inner spacing (it carries column alignment).

    A `key   value` line carries on under its value column, not under the key.
    """
    m = re.match(r"\S+ {3,}", line)
    indent = m.end() if m and m.end() < width // 2 else 0
    out, lead = [], 0
    while len(line) > width:
        cut = line.rfind(" ", lead + 1, width + 1)
        cut = cut if cut > lead else width
        out.append(line[:cut].rstrip())
        line = " " * indent + line[cut:].lstrip()
        lead = indent
    return out + [line.rstrip()] if line.strip() else out


def _output_line(y: float, line: str) -> str:
    """Plain output: '//' separators in purple, a leading `key   value` key in magenta."""
    runs = _runs(line)
    keyed = len(runs) > 1 and "//" not in line and re.match(r"\S+ {3,}", line)
    parts = []
    for i, (col, s) in enumerate(runs):
        color = PURPLE if s == "//" else MAGENTA if (keyed and i == 0) else OUT
        parts.append(_text(col, y, s, color))
    return "".join(parts)


def _row(name: str, status: str | None, ready: str | None, age: str | None) -> tuple:
    """One board row, told straight: every cell is the project's own value.

    READY defaults to 1/1 only for something that is actually running, and a
    READY that kubectl could never print (a placeholder like 'N/N') falls back
    to that default. An AGE that merely repeats the status would say the same
    thing twice, so it shows '-'.
    """
    status = str(status or "unknown")
    if not (ready and READY_RE.fullmatch(str(ready))):
        ready = "1/1" if status.lower() == "running" else "-"
    age = str(age) if age and str(age).lower() != status.lower() else "-"
    return (str(name), str(ready), status[:1].upper() + status[1:], age)


def _board(content: dict) -> tuple[tuple, list[tuple], list[int]]:
    """kubectl-style listing: header, rows, and the start column of each column."""
    rows = [_row(p["slug"], p.get("status"), p.get("ready"), p.get("age"))
            for p in content.get("projects", [])]
    rows += [_row(x["name"], x.get("status"), x.get("ready"), x.get("age"))
             for x in content.get("board_extra", [])]
    header = ("NAME", "READY", "STATUS", "AGE")
    cols, c = [], 0
    for i in range(4):
        cols.append(c)
        c += max(len(r[i]) for r in rows + [header]) + 3   # kubectl pads with 3 spaces
    return header, rows, cols


def _kube_age(since: str, today: str) -> str:
    """Days between two ISO dates, printed the way kubectl prints AGE (12d, 1y40d).

    A date that doesn't parse shows '-' rather than failing the daily render.
    """
    try:
        days = (date.fromisoformat(str(today)) - date.fromisoformat(str(since))).days
    except ValueError:
        return "-"
    if days < 0:
        return "-"
    return f"{days // 365}y{days % 365}d" if days >= 365 else f"{days}d"


def _with_ages(content: dict, today: str | None) -> dict:
    """Copy of content where every item with a `since` date gets a real AGE.

    `today` is the last day of the fetched GitHub data, so the age advances with
    each daily render and the output stays deterministic for a given input.
    """
    if not today:
        return content
    out = dict(content)
    for key in ("projects", "board_extra"):
        out[key] = [dict(x, age=_kube_age(x["since"], today)) if x.get("since") else x
                    for x in content.get(key, [])]
    return out


def _status_color(status: str) -> str:
    s = status.lower()
    return STATUS_COLORS.get(s, RED if s in FAILED else AMBER)


def _cursor() -> str:
    """Block cursor with a soft halo, drawn at the origin of the baseline."""
    top, h = -FS * 0.8, FS * 1.08
    return (f"<rect x='-2' y='{fmt(top - 2)}' width='{fmt(ADV + 4)}' height='{fmt(h + 4)}' "
            f"rx='2' fill='{CYAN}' opacity='0.18'/>"
            f"<rect y='{fmt(top)}' width='{fmt(ADV)}' height='{fmt(h)}' fill='{CYAN}'/>")


# --- the shared loop -------------------------------------------------------------------
class Loop:
    """Elements that switch on (and maybe off) at moments within one shared loop."""

    def __init__(self) -> None:
        self.buckets: dict[tuple, list[str]] = {}
        self.css: list[str] = []
        self.total = 0.0
        self._n = 0

    def at(self, t_on: float, frag: str, *, transient: bool = False) -> None:
        """Show `frag` from t_on. Transient parts are not in the finished screen."""
        self.buckets.setdefault((round(t_on, 3), transient), []).append(frag)

    def name(self) -> str:
        self._n += 1
        return f"k{self._n}"

    def pct(self, t: float) -> str:
        return f"{fmt(100 * t / self.total, 3)}%"

    def keyframes(self, frames: str) -> str:
        """Register @keyframes; returns the attributes that play them on the loop."""
        n = self.name()
        self.css.append(f"@keyframes {n}{{{frames}}}")
        return f" class='k' style='animation-name:{n}'"

    def emit(self) -> str:
        out = []
        for (t_on, transient), frags in sorted(self.buckets.items()):
            if t_on == 0 and not transient:
                out.extend(frags)
                continue
            attrs = self.keyframes(f"0%{{opacity:0}}{self.pct(t_on)}{{opacity:1}}")
            if transient:
                attrs += " opacity='0'"
            if len(frags) == 1 and frags[0].count("<") == 2:
                # a lone <text>: animate it directly instead of wrapping it in a <g>
                cut = frags[0].index(" ")
                out.append(frags[0][:cut] + attrs + frags[0][cut:])
            else:
                out.append(f"<g{attrs}>{''.join(frags)}</g>")
        return "".join(out)


# --- the session ------------------------------------------------------------------------
class Session:
    """Lays the session out line by line while keeping the clock."""

    def __init__(self, user: str, host: str) -> None:
        self.user, self.host = user, host
        self.loop = Loop()
        self.y = FIRST_BASE
        self.t = 0.0
        self.tx: list[float] = []          # keystrokes, for the TX LED
        self.rx: list[float] = []          # output lines, for the RX LED
        self.cursors: list[tuple] = []     # (t_off, [(t, col, y, visible)]) per typed line

    def prompt(self) -> int:
        """Draw `user@host:~$ ` on the current line now; returns its width in columns."""
        who = f"{self.user}@{self.host}"
        self.loop.at(self.t, _text(0, self.y, who, CYAN, bold=True)
                     + _text(len(who), self.y, ":~", PURPLE, bold=True)
                     + _text(len(who) + 2, self.y, "$", MAGENTA, bold=True))
        return len(who) + 4

    def type(self, cmd: str, start_col: int, wait: float, *, transient: bool = False) -> None:
        """Idle for `wait` with a blinking cursor, type `cmd`, press enter."""
        frames = [(self.t, start_col, self.y, True)]
        k = BLINK / 2
        while k < wait - 0.05:
            frames.append((self.t + k, start_col, self.y, int(k / (BLINK / 2)) % 2 == 0))
            k += BLINK / 2
        t, col, y = self.t + wait, start_col, self.y
        r = rng(f"{self.host}:{cmd}")
        for i, ch in enumerate(cmd):
            # uneven like a person, longer around spaces; identical every render
            t += T_KEY[0] + r.random() * T_KEY[1]
            if ch == " " or (i and cmd[i - 1] == " "):
                t += T_SPACE[0] + r.random() * T_SPACE[1]
            if col >= COLS:
                col, y = 0, y + LH
            if ch != " ":
                self.loop.at(t, _text(col, y, ch, TEXT), transient=transient)
            self.tx.append(t)
            col += 1
            frames.append((t, col, y, True))
        self.t = t + T_ENTER
        self.cursors.append((self.t, frames))
        self.y = y + LH

    def lines(self, out: list[str]) -> None:
        for i, part in enumerate(p for line in out for p in _wrap(line, COLS)):
            if i:
                self.t += T_LINE
            self.loop.at(self.t, _output_line(self.y, part))
            self.rx.append(self.t)
            self.y += LH

    def board(self, header: tuple, rows: list[tuple], cols: list[int]) -> None:
        self.loop.at(self.t, "".join(_text(c, self.y, h, DIM) for c, h in zip(cols, header)))
        self.rx.append(self.t)
        for name, ready, status, age in rows:
            self.y += LH
            self.t += T_ROW
            color = _status_color(status)
            # the status LED sits in the gutter, so STATUS text stays on its column
            dot = led(X0 + (cols[2] - 1.4) * ADV, self.y - FS * 0.32, color, r=FS * 0.14)
            self.loop.at(self.t, _text(cols[0], self.y, name, TEXT)
                         + _text(cols[1], self.y, ready, OUT)
                         + dot + _text(cols[2], self.y, status, color)
                         + _text(cols[3], self.y, age, OUT))
            self.rx.append(self.t)
        self.y += LH


def _play(content: dict) -> tuple[Session, dict]:
    """Run the whole session: every command, the idle hold, and the closing `clear`."""
    term = content.get("terminal", {})
    s = Session(term.get("user", "user"), term.get("host", "localhost"))
    for step in term.get("session", []):
        s.type(step.get("cmd", ""), s.prompt(), T_FIRST_WAIT if s.t == 0 else T_WAIT)
        out = step.get("out", [])
        if out == "@board":
            s.board(*_board(content))
        else:
            s.lines([out] if isinstance(out, str) else out)
        s.t += T_NEXT
        s.y += BLOCK_GAP
    t_final, y_final = s.t, s.y
    cols = s.prompt()
    s.t += T_HOLD
    t_hold_end = s.t
    s.type("clear", cols, 0.0, transient=True)
    s.loop.total = s.t + T_TAIL
    return s, dict(t_final=t_final, t_hold_end=t_hold_end, t_clear=s.t,
                   cursor=(X0 + cols * ADV, y_final), bottom=y_final)


# --- keyframes for cursors and LEDs ---------------------------------------------------------
def _typing_cursor(loop: Loop, t_off: float, frames: list[tuple]) -> str:
    """A cursor that jumps along with each keystroke and vanishes on enter."""
    t0, col0, y0, _ = frames[0]
    # hidden until its prompt appears; a cursor that starts the loop needs no lead-in
    ks = [f"0%{{opacity:0;transform:translate({fmt(X0 + col0 * ADV)}px,{fmt(y0)}px)}}"] if t0 > 0 else []
    for t, col, y, visible in frames:
        ks.append(f"{loop.pct(t)}{{opacity:{int(visible)};"
                  f"transform:translate({fmt(X0 + col * ADV)}px,{fmt(y)}px)}}")
    ks.append(f"{loop.pct(t_off)},100%{{opacity:0}}")
    return f"<g{loop.keyframes(''.join(ks))} opacity='0'>{_cursor()}</g>"


def _flashes(loop: Loop, name: str, moments: list[float], on: float) -> str:
    """LED activity keyframes: a short flash per moment, merged where they touch."""
    spans: list[list[float]] = []
    for m in sorted(moments):
        if spans and m <= spans[-1][1] + FLASH_MERGE:
            spans[-1][1] = m + on
        else:
            spans.append([m, m + on])
    if not spans:
        return f"@keyframes {name}{{0%{{opacity:0}}}}"
    ons = ",".join(loop.pct(a) for a, _ in spans)
    offs = ",".join(loop.pct(b) for _, b in spans)
    return f"@keyframes {name}{{0%,{offs},100%{{opacity:0}}{ons}{{opacity:1}}}}"


# --- hardware -----------------------------------------------------------------------------------
def _label_w(text: str, size: float, spacing: float) -> float:
    """Worst-case width of a silkscreen label, letter-spacing included."""
    return len(text) * (size * 0.62 + spacing)


def _chassis(h: float, gh: float, model: str) -> str:
    """Rack panel face, ears and screws, header silkscreen and activity LEDs."""
    parts = [
        f"<rect x='4' y='4' width='{W - 8}' height='{fmt(h - 8)}' rx='12' fill='url(#face)'/>",
        f"<rect x='4.5' y='4.5' width='{W - 9}' height='{fmt(h - 9)}' rx='11.5' stroke='{EDGE}'/>",
        f"<path d='M16 5.5H{W - 16}' stroke='#fff' stroke-opacity='0.07'/>",
    ]
    for ex in (EAR, W - EAR):        # the seam between rack ear and faceplate
        parts.append(f"<path d='M{ex} 12V{fmt(h - 12)}' stroke='#000' stroke-opacity='0.55'/>"
                     f"<path d='M{ex + 1} 12V{fmt(h - 12)}' stroke='#fff' stroke-opacity='0.04'/>")
    for sx, sy, a in ((22, 26, 20), (22, h - 26, 110), (W - 22, 26, 70), (W - 22, h - 26, 150)):
        parts.append(screw(sx, sy, r=5.2, angle=a))

    # header: bold model code and a dim product name, as on the hero unit;
    # LEDs on the right, an engraved groove between
    name = "session monitor"
    x = BEZ_X + 4
    parts.append(label(x, 29, model, size=11, color=TEXT, weight=700, spacing=2))
    x += _label_w(model, 11, 2) + 8
    parts.append(label(x, 29, name, size=8.5, color=DIM, spacing=1.8))
    groove_from = x + _label_w(name, 8.5, 1.8) + 14

    lx = W - BEZ_X - 4
    for cls, name, color in (("rx", "RX", CYAN), ("tx", "TX", MAGENTA), ("", "LINK", GREEN)):
        parts.append(label(lx, 29, name, size=9, color=DIM, anchor="end", spacing=1.6))
        cx = lx - _label_w(name, 9, 1.6) - 10
        parts.append(f"<circle cx='{fmt(cx)}' cy='25.5' r='3.6' fill='#120A1E' stroke='{EDGE}'/>")
        lit = led(cx, 25.5, color, r=2.6)
        parts.append(f"<g class='{cls}' opacity='0'>{lit}</g>" if cls else lit)
        lx = cx - 20
    groove_to = lx + 4
    if groove_to - groove_from > 40:
        parts.append(f"<path d='M{fmt(groove_from)} 25H{fmt(groove_to)}' stroke='#000' stroke-opacity='0.6'/>"
                     f"<path d='M{fmt(groove_from)} 26H{fmt(groove_to)}' stroke='#fff' stroke-opacity='0.05'/>")

    # bezel: a dark lip lit from below, so the glass reads as recessed
    bw, bh = W - 2 * BEZ_X, gh + 2 * BEZ_PAD
    parts += [
        f"<rect x='{BEZ_X}' y='{BEZ_Y}' width='{bw}' height='{fmt(bh)}' rx='13' fill='#07040D'/>",
        f"<rect x='{BEZ_X + 0.5}' y='{BEZ_Y + 0.5}' width='{bw - 1}' height='{fmt(bh - 1)}' "
        f"rx='12.5' stroke='url(#lip)'/>",
    ]
    return "".join(parts)


def _glass(gh: float, user: str, host: str) -> tuple[str, str]:
    """The screen: (under the text, over the text)."""
    gx, gy, gw = GLASS_X, GLASS_Y, GLASS_W
    ty = gy + TITLE_H / 2
    under = [
        f"<rect x='{gx}' y='{gy}' width='{gw}' height='{fmt(gh)}' rx='8' fill='url(#glass)'/>",
        f"<path d='M{gx + 8} {gy}H{gx + gw - 8}a8 8 0 0 1 8 8V{gy + TITLE_H}H{gx}V{gy + 8}"
        f"a8 8 0 0 1 8 -8Z' fill='#110A1F' fill-opacity='0.85'/>",
        f"<path d='M{gx} {gy + TITLE_H - 0.5}H{gx + gw}' stroke='{EDGE}'/>",
    ]
    # the monitor's on-screen input tag, balancing the shell name on the right
    under.append(label(gx + 16, ty + 3.5, "ch a", size=9, color=DIM, spacing=1.6))
    under.append(f"<text x='{W / 2}' y='{fmt(ty + 4)}' font-size='12' fill='{DIM}' "
                 f"text-anchor='middle' letter-spacing='0.5'>{esc(f'{user}@{host}: ~')}</text>")
    under.append(f"<text x='{gx + gw - 16}' y='{fmt(ty + 4)}' font-size='11' fill='#5E4F85' "
                 f"text-anchor='end' letter-spacing='1'>bash</text>")
    body_y, body_h = gy + TITLE_H, gh - TITLE_H
    over = (
        f"<g clip-path='url(#glassclip)'>"
        f"<rect x='{gx}' y='{body_y}' width='{gw}' height='{fmt(body_h)}' fill='url(#scan)'/>"
        f"<rect x='{gx}' y='{gy}' width='{gw}' height='{fmt(gh)}' fill='url(#vig)'/>"
        f"<rect x='{gx}' y='{gy}' width='{gw}' height='{fmt(gh * 0.45)}' fill='url(#sheen)'/>"
        f"</g>"
        f"<rect x='{gx + 0.5}' y='{gy + 0.5}' width='{gw - 1}' height='{fmt(gh - 1)}' rx='7.5' "
        f"stroke='#000' stroke-opacity='0.8'/>"
    )
    return "".join(under), over


def _defs(gh: float) -> str:
    gx, gy, gw = GLASS_X, GLASS_Y, GLASS_W
    return (
        panel_gradient("face")
        + "<linearGradient id='lip' x1='0' y1='0' x2='0' y2='1'>"
          "<stop offset='0' stop-color='#000'/><stop offset='1' stop-color='#3A2860'/></linearGradient>"
        + "<radialGradient id='glass' cx='0.5' cy='0.42' r='0.75'>"
          "<stop offset='0' stop-color='#140B26'/><stop offset='0.6' stop-color='#0A0614'/>"
          "<stop offset='1' stop-color='#05020A'/></radialGradient>"
        + "<radialGradient id='vig' cx='0.5' cy='0.5' r='0.72'>"
          "<stop offset='0.62' stop-color='#000' stop-opacity='0'/>"
          "<stop offset='1' stop-color='#000' stop-opacity='0.55'/></radialGradient>"
        + "<linearGradient id='sheen' x1='0' y1='0' x2='0' y2='1'>"
          "<stop offset='0' stop-color='#fff' stop-opacity='0.035'/>"
          "<stop offset='1' stop-color='#fff' stop-opacity='0'/></linearGradient>"
        + scanlines_pattern("scan", gap=3, opacity=0.22)
        + f"<clipPath id='glassclip'><rect x='{gx}' y='{gy}' width='{gw}' height='{fmt(gh)}' rx='8'/></clipPath>"
        # text bloom, filtered once for the whole screen and clipped to the glass
        # below the title bar: the smaller the region, the cheaper each repaint
        + f"<filter id='bloom' filterUnits='userSpaceOnUse' x='{gx}' y='{gy + TITLE_H}' width='{gw}' "
          f"height='{fmt(gh - TITLE_H)}' color-interpolation-filters='sRGB'>"
          "<feGaussianBlur stdDeviation='2.2' result='b'/>"
          "<feComponentTransfer in='b' result='b2'><feFuncA type='linear' slope='0.6'/></feComponentTransfer>"
          "<feMerge><feMergeNode in='b2'/><feMergeNode in='SourceGraphic'/></feMerge></filter>"
    )


def _spoken_list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _describe(content: dict, user: str, host: str) -> tuple[str, str]:
    said = []
    for step in content.get("terminal", {}).get("session", []):
        cmd, out = step.get("cmd", ""), step.get("out", [])
        if out == "@board":
            _, rows, _ = _board(content)
            by_status: dict[str, list[str]] = {}
            for r in rows:
                by_status.setdefault(r[2], []).append(r[0])
            said.append(f"Running {cmd} lists each project with its status: " + "; ".join(
                f"{_spoken_list(names)} {st.lower()}" for st, names in by_status.items()))
        else:
            lines = [out] if isinstance(out, str) else out
            # read the '//' separators as commas rather than "slash slash"
            said.append(f"Running {cmd} prints: " + "; ".join(
                " ".join(re.sub(r"\s+//\s+", ", ", l).split()) for l in lines))
    desc = (f"A terminal on a rack-mounted monitor, logged in as {user}@{host}, types "
            f"commands and shows their output. " + "".join(f"{s}. " for s in said)).strip()
    return f"Terminal session: {user}@{host}", desc


def render(ctx: dict) -> dict[str, str]:
    content = _with_ages(ctx["content"], (ctx.get("data") or {}).get("fetched_at"))
    s, marks = _play(content)
    loop = s.loop
    gh = marks["bottom"] + FS * 0.3 + PAD_BOTTOM - GLASS_Y
    h = round(GLASS_Y + gh + BEZ_PAD + 16)

    text = loop.emit()
    cursors = [_typing_cursor(loop, t_off, frames) for t_off, frames in s.cursors]
    # the finished screen's cursor: shown from the last prompt until `clear` starts
    fx, fy = marks["cursor"]
    window = loop.keyframes(f"0%{{opacity:0}}{loop.pct(marks['t_final'])}{{opacity:1}}"
                            f"{loop.pct(marks['t_hold_end'])},100%{{opacity:0}}")
    cursors.append(f"<g{window}><g class='blink' transform='translate({fmt(fx)} {fmt(fy)})'>"
                   f"{_cursor()}</g></g>")

    total = fmt(loop.total, 3)
    # Where the last pass stops: halfway through its hold, when the final prompt
    # is up, the LEDs are dark and `clear` is still seconds away. A fractional
    # iteration count ends there, and without fill-mode the elements fall back
    # to their static values, which are that same finished screen.
    t_stop = (PLAYS - 1) * loop.total + marks["t_final"] + T_HOLD / 2
    runs = fmt(t_stop / loop.total, 4)
    # whole blink periods, so the last one ends lit; never before the loop stops
    blinks = math.ceil(max(SETTLE, t_stop) / BLINK)
    css = (
        # ligatures would merge two cells into one glyph and nudge the grid
        "text{font-variant-ligatures:none}"
        f".k{{animation-duration:{total}s;animation-timing-function:steps(1,end);"
        f"animation-iteration-count:{runs}}}"
        f".scr{{animation:scr {total}s steps(1,end) {runs}}}"
        f"@keyframes scr{{0%{{opacity:1}}{loop.pct(marks['t_clear'])},100%{{opacity:0}}}}"
        f".blink{{animation:blink {BLINK}s steps(1,end) {blinks}}}"
        "@keyframes blink{0%{opacity:1}50%{opacity:0}}"
        f".tx{{animation:tx {total}s steps(1,end) {runs}}}"
        f".rx{{animation:rx {total}s steps(1,end) {runs}}}"
        + _flashes(loop, "tx", s.tx, 0.045)
        + _flashes(loop, "rx", s.rx, 0.07)
        + "".join(loop.css)
    )

    under, over = _glass(gh, s.user, s.host)
    body = (
        _chassis(h, gh, str(content.get("terminal", {}).get("model", "TTY-02")))
        + under
        + f"<g class='scr' font-size='{FS}'>"
        + f"<g filter='url(#bloom)'>{text}</g>"
        + "".join(cursors)
        + "</g>"
        + over
    )
    title, desc = _describe(content, s.user, s.host)
    svg = svg_doc(W, h, body, title=title, desc=desc, css=css, defs=_defs(gh))
    return {"terminal.svg": svg}
