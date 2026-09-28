#!/usr/bin/env python3
"""Bash highlighter running as a persistent coprocess, using tree-sitter.

Protocol: one line in on stdin -> one coloured line out on stdout.
Started once per shell; from then on each keystroke is a pipe round trip, no forks.
A fork per keystroke would cost 917 us; this costs 158 us warm, of which 69 us is
the pipe and 45 us the actual work.

The highlighting rules are NOT invented here, they are loaded from a published
query: tree-sitter-bash's own queries/highlights.scm, plus highlights-extra.scm
next to this file.

Deliberately NOT nvim-treesitter's query, even though it is richer (261 lines and
already on disk): it uses #lua-match? predicates that the Python binding does not
evaluate, so its guarded patterns fire unconditionally and `echo` ends up captured
as @function.call, @function.builtin AND @number at once, painted as a number.
The grammar's own query only uses #match?, which the binding does evaluate: checked
with `git log --format=x -v normal`, where it flags only `--format=x` and `-v` and
leaves `log` and `normal` alone.

The green/red on whether a command EXISTS is semantic, not syntactic: that is
shutil.which with a cache. tree-sitter only says where the command name is.
"""
import sys, shutil, pathlib
from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_bash

LANG = Language(tree_sitter_bash.language())
parser = Parser(LANG)


def load_query():
    official = pathlib.Path(tree_sitter_bash.__file__).parent / "queries" / "highlights.scm"
    extra = pathlib.Path(__file__).parent / "highlights-extra.scm"
    src = official.read_text()
    sources = [str(official)]
    if extra.is_file():
        try:
            Query(LANG, src + "\n" + extra.read_text())
            src += "\n" + extra.read_text()
            sources.append(str(extra))
        except Exception as e:
            print(f"warning: extension ignored ({e})", file=sys.stderr)
    return Query(LANG, src), sources


QUERY, QSOURCES = load_query()

# Palette keyed by capture prefix: resolved from most specific to most generic, so
# @keyword.repeat falls back to keyword when it has no entry of its own.
PALETTE = {
    "function":            b"\033[38;5;118m",
    "keyword":             b"\033[38;5;4m",
    "string":              b"\033[38;5;70m",
    "string.regexp":       b"\033[38;5;198m",
    "variable":            b"\033[38;5;208m",
    "variable.builtin":    b"\033[38;5;208;1m",
    "operator":            b"\033[38;5;37m",
    "punctuation":         b"\033[38;5;66m",
    "punctuation.special": b"\033[38;5;37m",
    "number":              b"\033[38;5;64m",
    "boolean":             b"\033[38;5;64m",
    "constant":            b"\033[38;5;37m",
    "comment":             b"\033[38;5;242m",
    "character.special":   b"\033[38;5;201m",
    "embedded":            b"\033[38;5;208m",
    "property":            b"\033[38;5;208m",
    "label":               b"\033[38;5;92m",
}


def colour_of(capture: str):
    parts = capture.split(".")
    while parts:
        c = PALETTE.get(".".join(parts))
        if c:
            return c
        parts.pop()
    return None


BAD  = b"\033[38;5;197m"             # command that does not exist
ERRC = b"\033[48;5;203m\033[38;5;231m"
OFF  = b"\033[0m"

BUILTINS = {
    "cd", "echo", "printf", "export", "local", "read", "source", ".", "eval",
    "set", "unset", "shift", "test", "[", "true", "false", "exit", "return",
    "declare", "typeset", "alias", "unalias", "type", "command", "builtin",
    "trap", "wait", "jobs", "fg", "bg", "kill", "let", "pwd", "pushd", "popd",
    "history", "bind", "compgen", "complete", "shopt", "hash", "times", "ulimit",
    "mapfile", "readarray", "getopts", "caller", "enable", "logout", "suspend",
    "umask", "time",
}
_cache = {}


def exists(name: str) -> bool:
    if name not in _cache:
        _cache[name] = name in BUILTINS or bool(shutil.which(name))
    return _cache[name]


# captures that mark a command name, for the semantic green/red
COMMAND_CAPS = {"function", "function.call", "function.builtin"}


def paint(src: bytes) -> bytes:
    if not src:
        return src
    tree = parser.parse(src)
    n = len(src)
    cat = [None] * n

    items = []
    for name, nodes in QueryCursor(QUERY).captures(tree.root_node).items():
        for node in nodes:
            items.append((node.end_byte - node.start_byte,
                          node.start_byte, node.end_byte, name))
    # outermost first: shorter spans overwrite longer ones
    for _l, a, b, name in sorted(items, key=lambda x: -x[0]):
        if name in COMMAND_CAPS:
            word = src[a:b].decode("utf8", "replace").split("/")[-1]
            name = name if exists(word) else "__bad"
        for i in range(a, min(b, n)):
            cat[i] = name

    if tree.root_node.has_error:
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type == "ERROR" or node.is_missing:
                for i in range(node.start_byte, min(node.end_byte, n)):
                    cat[i] = "__err"
                continue
            stack.extend(c for c in node.children if c.has_error or c.is_missing)

    out, i = [], 0
    while i < n:
        c = cat[i]
        j = i
        while j < n and cat[j] == c:
            j += 1
        chunk = src[i:j]
        if c is None:        out.append(chunk)
        elif c == "__bad":   out.append(BAD + chunk + OFF)
        elif c == "__err":   out.append(ERRC + chunk + OFF)
        else:
            col = colour_of(c)
            out.append(col + chunk + OFF if col else chunk)
        i = j
    return b"".join(out)



def syntax_status(src: bytes) -> bytes:
    """ok / inc / err, from the parse we are doing anyway.

    This is the whole point: the coprocess already parses on every keystroke and
    used to throw this away. Telling "still typing" from "broken" costs nothing here.

    tree-sitter alone cannot fully separate the two: `echo 'unclosed` (incomplete)
    and `echo )` (invalid) give the SAME signature, an error reaching the end of
    input with no missing node. So `inc` means "possibly incomplete" and the caller
    settles it with `bash -n`, which is authoritative and only gets asked in that
    rare case.
    """
    tree = parser.parse(src)
    root = tree.root_node
    if not root.has_error:
        return b"ok"
    n = len(src)
    stack = [root]
    while stack:
        node = stack.pop()
        if node.is_missing:
            return b"inc"                      # something expected is absent
        if node.type == "ERROR" and node.end_byte >= n:
            return b"inc"                      # the error runs to the end of input
        stack.extend(node.children)
    return b"err"                              # broken in the middle


def unescape_query(raw: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(raw):
        if raw[i:i+1] == b"\\" and i + 1 < len(raw):
            c = raw[i+1:i+2]
            out += {b"n": b"\n", b"\\": b"\\"}.get(c, b"\\" + c)
            i += 2
        else:
            out += raw[i:i+1]; i += 1
    return bytes(out)


def main():
    if "--info" in sys.argv:
        for f in QSOURCES:
            print(f"query: {f}")
        print(f"patterns: {QUERY.pattern_count}  captures: {QUERY.capture_count}")
        return
    # Binary I/O, and readline() rather than iterating sys.stdin: the iterator uses
    # a read-ahead buffer that adds about a millisecond per round trip in
    # interactive pipe use.
    inp, out = sys.stdin.buffer, sys.stdout.buffer
    out.write(b"READY\n"); out.flush()
    while True:
        raw = inp.readline()
        if not raw:
            break
        src = raw.rstrip(b"\n")
        # A leading 0x01 makes it a status query rather than a colour request. Safe
        # as a sentinel because the editor never lets a control byte into the line.
        # Newlines inside come escaped as \n, so the protocol stays line-based.
        if src[:1] == b"\x01":
            try:
                out.write(syntax_status(unescape_query(src[1:])) + b"\n")
            except Exception:
                out.write(b"ok\n")
            out.flush()
            continue
        try:
            out.write(paint(src) + b"\n")
        except Exception:
            out.write(src + b"\n")
        out.flush()


if __name__ == "__main__":
    main()
