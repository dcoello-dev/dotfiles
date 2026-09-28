#!/usr/bin/env python3
"""nvline: the command line edited by a real nvim, rendered inline on one row.

Draws on /dev/tty, writes the finished command to stdout, like fzf does. So the bash
side is two lines:

    line=$(nvline --prompt "$prompt") && eval "$line"

How it works: nvim --embed turns stdin/stdout into a msgpack-rpc channel, we call
nvim_ui_attach and become its UI. nvim sends grid updates and we paint them into one
terminal row, offset past the prompt. Keys go straight to nvim_input, so the modal
editing, the keymaps and the highlighting are nvim's own, not ours.

Exit codes:  0 run the line   1 cancelled (C-c)   2 end of input (C-d on empty)
             4 a C-g chord fired (see --chords)
             3 the user asked for the other editor (C-g e)
"""
import argparse, os, re, select, signal, struct, subprocess, sys, termios, time, tty, fcntl
import msgpack

ESC = "\033"

# NVLINE_DEBUG=/path logs what goes in and what comes back. Only way to see the key
# translation and the notifications when the thing is driven from a pty.
DEBUG = open(os.environ["NVLINE_DEBUG"], "a") if os.environ.get("NVLINE_DEBUG") else None


def tty_size(fd):
    try:
        rows, cols = struct.unpack("hh", fcntl.ioctl(fd, termios.TIOCGWINSZ, "____"))
        return rows or 24, cols or 80
    except Exception:
        return 24, 80


def visible_width(s):
    """Columns the string occupies once escape sequences are removed."""
    return len(re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b.", "", s))


class Nvim:
    def __init__(self, argv):
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        self.unpacker = msgpack.Unpacker(raw=False)
        self.msgid = 0
        self.pending = {}
        self.notifications = []

    def fileno(self):
        return self.p.stdout.fileno()

    def _send(self, obj):
        self.p.stdin.write(msgpack.packb(obj))
        self.p.stdin.flush()

    def notify(self, method, *params):
        self._send([2, method, list(params)])

    def pump(self):
        """Read whatever nvim has to say, queueing notifications.

        They go on a queue rather than being returned, because `call` pumps too while
        it waits for its reply. Returning them from pump lost every notification that
        arrived during a call, which is most of them: all the hl_attr_define events
        land during the setup calls, so the colour table came out empty and every cell
        rendered as a plain reset. That was the whole "it works but has no colour".
        """
        data = self.p.stdout.read1(1 << 16)
        if not data:
            raise EOFError
        self.unpacker.feed(data)
        for msg in self.unpacker:
            if msg[0] == 1:
                self.pending[msg[1]] = (msg[2], msg[3])
            elif msg[0] == 2:
                self.notifications.append((msg[1], msg[2]))

    def drain(self):
        """Take everything queued so far."""
        out, self.notifications = self.notifications, []
        return out

    def call(self, method, *params, timeout=10):
        self.msgid += 1
        mid = self.msgid
        self._send([0, mid, method, list(params)])
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            if mid in self.pending:
                err, res = self.pending.pop(mid)
                if err:
                    raise RuntimeError(f"{method}: {err}")
                return res
            r, _, _ = select.select([self.fileno()], [], [], 0.05)
            if r:
                self.pump()
        raise TimeoutError(method)


# --- the mode indicator ------------------------------------------------------
# nvim tells us the mode through `mode_change`, with clean names: normal, insert,
# visual, replace, operator, cmdline_normal... Three columns wide and always the same
# width, so the grid does not have to be resized when the mode changes.
MODES = {
    "normal":          ("N", 25),    # blue
    "insert":          ("I", 34),    # green
    "visual":          ("V", 170),   # magenta
    "visual_block":    ("B", 170),
    "visual_line":     ("L", 170),
    "select":          ("S", 170),
    "replace":         ("R", 160),   # red
    "operator":        ("O", 172),   # orange
    "cmdline_normal":  ("C", 37),    # cyan
    "cmdline_insert":  ("C", 37),
    "terminal":        ("T", 240),
}
MODE_WIDTH = 3


def mode_tag(name):
    letter, colour = MODES.get(name, ("?", 240))
    return f"{ESC}[48;5;{colour}m{ESC}[38;5;232m {letter} {ESC}[0m"


class Grid:
    """The single row nvim draws into, plus the cursor and the highlight table."""

    def __init__(self, width):
        self.width = width
        self.cells = [" "] * width
        self.hl = [0] * width
        self.attrs = {}
        self.cursor = 0
        self.mode = "insert"
        self.dirty = True

    def resize(self, width):
        self.width = width
        self.cells = [" "] * width
        self.hl = [0] * width
        self.dirty = True

    def handle(self, batch):
        for event in batch:
            kind, *args = event
            if kind == "grid_line":
                for a in args:
                    _grid, row, col_start, cells = a[0], a[1], a[2], a[3]
                    if row != 0:
                        continue
                    col = col_start
                    cur_hl = 0
                    for cell in cells:
                        text = cell[0]
                        if len(cell) > 1:
                            cur_hl = cell[1]
                        repeat = cell[2] if len(cell) > 2 else 1
                        for _ in range(repeat):
                            if 0 <= col < self.width:
                                self.cells[col] = text
                                self.hl[col] = cur_hl
                            col += 1
                    self.dirty = True
            elif kind == "grid_cursor_goto":
                for a in args:
                    if a[0] == 1 and a[1] == 0:
                        self.cursor = a[2]
                        self.dirty = True
            elif kind == "grid_clear":
                self.cells = [" "] * self.width
                self.hl = [0] * self.width
                self.dirty = True
            elif kind == "mode_change":
                for a in args:
                    if self.mode != a[0]:
                        self.mode = a[0]
                        self.dirty = True
            elif kind == "hl_attr_define":
                for a in args:
                    self.attrs[a[0]] = a[1]

    def sgr(self, hl_id):
        a = self.attrs.get(hl_id) or {}
        if not a:
            return ESC + "[0m"
        parts = ["0"]
        fg, bg = a.get("foreground"), a.get("background")
        if a.get("reverse"):
            fg, bg = bg, fg
        if fg is not None:
            parts += ["38", "2", str((fg >> 16) & 255), str((fg >> 8) & 255), str(fg & 255)]
        if bg is not None:
            parts += ["48", "2", str((bg >> 16) & 255), str((bg >> 8) & 255), str(bg & 255)]
        if a.get("bold"):      parts.append("1")
        if a.get("italic"):    parts.append("3")
        if a.get("underline"): parts.append("4")
        return ESC + "[" + ";".join(parts) + "m"

    def render(self, prompt, show_mode=True):
        """The whole row as bytes, ready to write to the tty."""
        tag = mode_tag(self.mode) if show_mode else ""
        out = ["\r", ESC + "[K", prompt, tag]
        last = None
        text = "".join(self.cells).rstrip()
        for i, ch in enumerate(text):
            h = self.hl[i]
            if h != last:
                out.append(self.sgr(h))
                last = h
            out.append(ch)
        out.append(ESC + "[0m")
        # park the cursor where nvim says it is
        target = visible_width(prompt) + (MODE_WIDTH if show_mode else 0) + self.cursor
        out.append("\r")
        if target:
            out.append(ESC + f"[{target}C")
        return "".join(out).encode("utf8", "replace")



# --- terminal bytes -> nvim key notation -------------------------------------
#
# `nvim_input` does NOT take raw terminal bytes. Control bytes below 0x20 happen to
# work, which is what made this look fine at first, but the rest does not:
#
#   0x7f      Backspace       was INSERTED as a literal 0x7f, so you could not delete
#   \e[3~     Delete          became Esc then `[3` then `~`, which in normal mode
#                             toggles case: `hola` turned into `holA`
#   \e[A..D   arrows          same story, they moved nothing
#   <         a typed <       starts key notation, so it has to go as <lt>
#
# So everything special needs translating. Anything left over at the end of a read is
# kept for the next one, because a sequence can be split across reads.

CSI_KEYS = {
    "A": "<Up>", "B": "<Down>", "C": "<Right>", "D": "<Left>",
    "H": "<Home>", "F": "<End>",
    "1~": "<Home>", "2~": "<Insert>", "3~": "<Del>", "4~": "<End>",
    "5~": "<PageUp>", "6~": "<PageDown>",
    "1;5A": "<C-Up>", "1;5B": "<C-Down>", "1;5C": "<C-Right>", "1;5D": "<C-Left>",
    "1;3A": "<M-Up>", "1;3B": "<M-Down>", "1;3C": "<M-Right>", "1;3D": "<M-Left>",
    "1;2C": "<S-Right>", "1;2D": "<S-Left>",
    "Z": "<S-Tab>",
}
SS3_KEYS = {"A": "<Up>", "B": "<Down>", "C": "<Right>", "D": "<Left>",
            "H": "<Home>", "F": "<End>", "P": "<F1>", "Q": "<F2>", "R": "<F3>", "S": "<F4>"}


class KeyDecoder:
    """Turns what the tty gives us into what nvim_input expects."""

    def __init__(self):
        self.pending = b""

    def feed(self, data):
        """Returns the nvim notation for whatever is complete. Keeps the rest."""
        buf = self.pending + data
        self.pending = b""
        out = []
        i = 0
        while i < len(buf):
            b = buf[i]
            if b == 0x1b:                                   # ESC: sequence or plain Esc
                rest = buf[i + 1:]
                if not rest:
                    self.pending = buf[i:]                  # wait, might be a sequence
                    break
                if rest[0:1] == b"[":
                    m = re.match(rb"\[([0-9;]*)([A-Za-z~])", rest)
                    if not m:
                        if len(rest) < 8:
                            self.pending = buf[i:]
                            break
                        i += 1
                        out.append("<Esc>")
                        continue
                    key = (m.group(1) + m.group(2)).decode()
                    out.append(CSI_KEYS.get(key, CSI_KEYS.get(m.group(2).decode(), "")))
                    i += 1 + m.end()
                    continue
                if rest[0:1] == b"O":
                    if len(rest) < 2:
                        self.pending = buf[i:]
                        break
                    out.append(SS3_KEYS.get(rest[1:2].decode(), ""))
                    i += 3
                    continue
                out.append("<Esc>")                         # Esc then a normal key
                i += 1
                continue
            if b == 0x7f:
                out.append("<BS>")
                i += 1
                continue
            if b == 0x00:
                out.append("<Nul>")
                i += 1
                continue
            if b < 0x20:                                    # other control bytes pass
                out.append(chr(b))
                i += 1
                continue
            # printable, possibly multibyte utf8
            j = i + 1
            while j < len(buf) and 0x80 <= buf[j] < 0xc0:
                j += 1
            chunk = buf[i:j].decode("utf8", "replace")
            out.append("<lt>" if chunk == "<" else chunk)
            i = j
        return "".join(out)

    def flush(self):
        """A lone Esc that never became a sequence."""
        if self.pending:
            self.pending = b""
            return "<Esc>"
        return ""


SETUP = [
    # Strip every gutter: without this your config's number column shows up inside the
    # grid as "  1   " and eats the first columns of the line.
    "set nonumber norelativenumber signcolumn=no foldcolumn=0",
    "set laststatus=0 noruler noshowmode noshowcmd nocursorline nowrap",
    "set filetype=bash",
    "set noswapfile nobackup noundofile shortmess+=F",
    # One line only: Enter means "run this", not "insert a newline". The channel id is
    # 1 for an --embed client, so rpcnotify(1, ...) comes back to us.
    'inoremap <expr> <CR> rpcnotify(1, "submit") ? "" : ""',
    'nnoremap <expr> <CR> rpcnotify(1, "submit") ? "" : ""',
    'inoremap <expr> <C-c> rpcnotify(1, "cancel") ? "" : ""',
    'nnoremap <expr> <C-c> rpcnotify(1, "cancel") ? "" : ""',
    # Hand back to whoever launched us, so a mode switch works from in here too.
    # Exit code 3 means "the user asked for the other editor".
    'inoremap <expr> <C-g>e rpcnotify(1, "switch") ? "" : ""',
    'nnoremap <expr> <C-g>e rpcnotify(1, "switch") ? "" : ""',
]


def run(prompt, initial, cols, show_mode=True, chords="", start_normal=False,
        cursor=None):
    tty_fd = os.open("/dev/tty", os.O_RDWR)
    saved = termios.tcgetattr(tty_fd)
    width = max(20, cols - visible_width(prompt) - (MODE_WIDTH if show_mode else 0))
    nv = Nvim(["nvim", "--embed", "-i", "NONE"])
    grid = Grid(width)
    # Start the badge on the mode we are actually about to be in, or it flashes `I`
    # for one frame before nvim's first mode_change lands.
    grid.mode = "normal" if start_normal else "insert"
    keys = KeyDecoder()
    # Start at 2 (end of input), not 1 (cancelled): if the loop ends for a reason we
    # did not handle, "the input ended" is the honest answer. Starting at 1 made a
    # missing handler look like the user had pressed C-c, which is how the `cancel`
    # and `switch` branches went missing from the loop without any test failing.
    status, line, chord = 2, "", ""
    chord_pending = False
    chord_deadline = 0.0
    try:
        tty.setraw(tty_fd)
        nv.call("nvim_ui_attach", width, 1, {
            "ext_linegrid": True, "ext_cmdline": True, "ext_messages": True,
            "ext_popupmenu": True, "ext_tabline": True, "rgb": True,
        })
        for cmd in SETUP:
            nv.call("nvim_command", cmd)
        # NOTE: the C-g chords are NOT nvim mappings. They were, and it was flaky in a
        # way that would have been maddening: your `timeoutlen` is 300 ms, so pressing
        # C-g and then the letter fast enough worked, and hesitating meant C-g fired
        # alone (invisible, since messages are externalised) and the letter went on to
        # do whatever it does in normal mode, `s` substituting a character for example.
        #
        # So nvline resolves the chord itself. It knows the mode from `mode_change`,
        # so in normal mode it swallows C-g, waits for the next key as long as it
        # likes, and reports the pair. Deterministic, and no mapping involved.
        if initial:
            # All the lines, matching what submit returns: a pending buffer restored
            # after a chord can perfectly well be multiline.
            lines = initial.split("\n")
            nv.call("nvim_buf_set_lines", 0, 0, -1, True, lines)
            if cursor is None:
                nv.call("nvim_win_set_cursor", 0, [len(lines), len(lines[-1])])
            else:
                # byte offset into the whole text -> line and column
                row, rest = 1, cursor
                for ln in lines:
                    if rest <= len(ln):
                        break
                    rest -= len(ln) + 1
                    row += 1
                row = min(row, len(lines))
                nv.call("nvim_win_set_cursor", 0,
                        [row, max(0, min(rest, len(lines[row - 1])))])
        if start_normal:
            # Handed over from the other editor with Esc: you are already in normal
            # mode, which is the whole point of pressing Esc.
            pass
        else:
            nv.notify("nvim_input", "A" if initial else "i")

        while True:
            if grid.dirty:
                os.write(tty_fd, grid.render(prompt, show_mode))
                grid.dirty = False
            r, _, _ = select.select([tty_fd, nv.fileno()], [], [], 0.25)
            if chord_pending and time.time() > chord_deadline:
                chord_pending = False       # C-g with nothing after it: forget it
                if DEBUG:
                    DEBUG.write(f"chord expired at {time.time():.2f}\n"); DEBUG.flush()
            if not r:
                seq = keys.flush()          # a lone Esc, nothing followed it
                if seq:
                    if DEBUG:
                        DEBUG.write(f"flush -> {seq!r}\n"); DEBUG.flush()
                    nv.notify("nvim_input", seq)
            if tty_fd in r:
                data = os.read(tty_fd, 1024)
                if not data:
                    status = 2
                    break
                # C-d on an empty line means end of input, the way a shell expects.
                if data == b"\x04":
                    cur = nv.call("nvim_get_current_line")
                    if not cur.strip():
                        status = 2
                        break
                # --- chord resolution, ours, before anything reaches nvim -------
                #
                # Careful with the mode: when you type fast, Esc and C-g and the letter
                # all arrive in ONE read, and at that moment `grid.mode` still says
                # insert, because nvim has not processed the Esc yet. Checking the mode
                # first made the chord work only when you hesitated, which is exactly
                # backwards.
                #
                # So: send whatever comes before the C-g, then ask nvim for the mode.
                # That call is synchronous, so its reply means nvim has caught up, and
                # the answer is the mode that actually applies to the C-g.
                if chord_pending:
                    chord_pending = False
                    if DEBUG:
                        DEBUG.write(f"chord resolving with {data[:1]!r}\n"); DEBUG.flush()
                    letter = data[:1].decode("utf8", "replace")
                    data = data[1:]
                    if letter in chords:
                        line = "\n".join(nv.call("nvim_buf_get_lines", 0, 0, -1, True))
                        status, chord = 4, letter
                        raise StopIteration
                    if not data:
                        continue                      # unknown letter, swallowed
                if chords and b"\x07" in data:
                    head, _, tail = data.partition(b"\x07")
                    if head:
                        seq = keys.feed(head)
                        if seq:
                            nv.notify("nvim_input", seq)
                    # And flush anything the decoder is still holding. A lone Esc sits
                    # in its pending buffer waiting to see if it is a sequence, so
                    # without this nvim had not seen the Esc yet and answered "insert",
                    # which is why fast typing fell through to nvim's own C-g.
                    seq = keys.flush()
                    if seq:
                        nv.notify("nvim_input", seq)
                    if nv.call("nvim_get_mode").get("mode", "").startswith("n"):
                        if tail:
                            letter = tail[:1].decode("utf8", "replace")
                            if letter in chords:
                                line = "\n".join(
                                    nv.call("nvim_buf_get_lines", 0, 0, -1, True))
                                status, chord = 4, letter
                                raise StopIteration
                            data = tail[1:]           # unknown letter, drop the pair
                        else:
                            chord_pending = True
                            chord_deadline = time.time() + 3.0
                            if DEBUG:
                                DEBUG.write(f"chord armed until {chord_deadline:.2f}\n")
                                DEBUG.flush()
                            continue
                    else:
                        data = b"\x07" + tail         # not normal mode: C-g is nvim's
                    if not data:
                        continue
                seq = keys.feed(data)
                if seq:
                    if DEBUG:
                        DEBUG.write(f"in  {data!r} -> {seq!r}\n"); DEBUG.flush()
                    nv.notify("nvim_input", seq)
            if nv.fileno() in r:
                nv.pump()
            # Always drain, not just after a read: events queue up while an RPC call
            # is waiting for its reply too.
            for name, batch in nv.drain():
                if DEBUG and name != "redraw":
                    DEBUG.write(f"note {name} {batch!r}\n"); DEBUG.flush()
                if name == "redraw":
                    grid.handle(batch)
                elif name == "submit":
                    # Every line, not just the cursor's. `o`, `O` and a multiline
                    # paste all make a second line, and taking only the current one
                    # dropped the rest silently: `echo uno`, Esc, `o`, `echo dos`
                    # returned just `echo dos`. bash evals a multiline string fine.
                    line = "\n".join(nv.call("nvim_buf_get_lines", 0, 0, -1, True))
                    status = 0
                    raise StopIteration
                elif name == "cancel":
                    status = 1
                    raise StopIteration
                elif name == "switch":
                    status = 3
                    raise StopIteration
                elif name == "chord":
                    # The letter, plus whatever was half-typed so it can come back.
                    chord = batch[0] if batch else ""   # noqa: the outer name
                    line = "\n".join(nv.call("nvim_buf_get_lines", 0, 0, -1, True))
                    status = 4
                    raise StopIteration
                elif name == "cancel":
                    status = 1
                    raise StopIteration
    except (StopIteration, EOFError):
        pass
    except KeyboardInterrupt:
        status = 1
    finally:
        termios.tcsetattr(tty_fd, termios.TCSADRAIN, saved)
        os.write(tty_fd, b"\r" + (ESC + "[K").encode())
        try:
            nv.notify("nvim_command", "qa!")
        except Exception:
            pass
        os.close(tty_fd)
    return status, line, chord


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--prompt", default="$ ")
    ap.add_argument("--initial", default="")
    ap.add_argument("--cols", type=int, default=0)
    ap.add_argument("--no-mode", action="store_true",
                    help="do not draw the N/I/V mode indicator")
    ap.add_argument("--start-normal", action="store_true",
                    help="do not enter insert mode; you were handed over with Esc")
    ap.add_argument("--cursor", type=int, default=None,
                    help="byte offset in --initial to put the cursor at")
    ap.add_argument("--chords", default="",
                    help="letters to bind as <C-g>LETTER in normal mode; firing one "
                         "exits with code 4, printing the letter then the pending line")
    a = ap.parse_args()
    cols = a.cols or tty_size(os.open("/dev/tty", os.O_RDWR)) [1]
    status, line, chord = run(a.prompt, a.initial, cols,
                              show_mode=not a.no_mode, chords=a.chords,
                              start_normal=a.start_normal, cursor=a.cursor)
    if status == 0:
        sys.stdout.write(line + "\n")
    elif status == 4:
        # first line the chord letter, the rest whatever was half-typed
        sys.stdout.write(chord + "\n" + line + "\n")
    sys.exit(status)


if __name__ == "__main__":
    main()
