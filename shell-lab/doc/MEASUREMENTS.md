# Prototypes: replacing ble.sh

Measured 2026-09-26 on WSL, bash 5.2.21, in `~/code/argos`, with the PATH already
clear of Windows directories. Same method on every row: real pty, wait for the
prompt, median of several passes, the line typed character by character.

| Option | ms/keystroke | Highlighting |
|---|---|---|
| ble.sh 0.4.0-devel4, current config | 27.7 | yes |
| custom editor + tree-sitter | 0.6, 0.16 warm | yes, real grammar |
| custom editor + bash tokenizer | 0.8 to 1.8 | yes, approximate |
| plain readline + the 11 macros | 0.33 | no |

Breaking ble.sh down: of its ~22-28 ms, about 14.5 is the line editor machinery and
about 8 the highlighting. The expensive part is the editor, not the colouring.

## What ble.sh was actually being asked for

- 83 `ble-bind`, of which **11 worked**. The other 72 are dead: 67 call
  `~/.config/subset/subset.py`, which does not exist, and 5 call missing binaries
  (`amixer` twice, `spt`, `neovim`, `gitui`).
- 63 `ble-face`: the highlighting theme. They collapse into about 10 real
  categories; the rest are ble.sh internals (menus, regions, vbell).
- 6 `bleopt`, three of which DISABLE ble.sh features (autocomplete, history
  completion, ambiguous completion).

## tree-sitter: published and official

`tree-sitter-bash` **0.25.1**, released 2 December 2025, MIT, in the tree-sitter
organisation's own repository: `github.com/tree-sitter/tree-sitter-bash`. Authors
Max Brunsfeld and Amaan Qureshi. It is in all three registries at the same version:

| Registry | Package |
|---|---|
| PyPI | `tree-sitter-bash` |
| npm | `tree-sitter-bash`, 251 projects depend on it |
| crates.io | `tree-sitter-bash`, 13.19 million downloads |

The one installed here is the latest. ABI 15, 280 node kinds, 19 fields, 7571 parser
states. The wheel ships the compiled `.so`, so no compiler is needed. And it ships
`queries/highlights.scm`: **its own published highlighting rules**, which is what
this highlighter uses instead of a hand-rolled node map.

### Why NOT nvim-treesitter's query

nvim ships a 261-line one, far richer than the grammar's 43, and it is already on
disk at `~/.local/share/nvim/lazy/nvim-treesitter/queries/bash/highlights.scm`.
It loads fine with the Python binding, 49 patterns and 30 captures, **but it gives
wrong results**: it uses 3 `#lua-match?` predicates, which are nvim's own and the
Python binding does not evaluate. Its guarded patterns then fire unconditionally,
and `echo` ends up captured as `@function.call`, `@function.builtin` AND `@number`
at once, so it is painted as a number. Verified.

The grammar's own query only uses `#match?`, which the binding does evaluate:
checked with `git log --format=x -v normal`, where it flags only `--format=x` and
`-v` and leaves `log` and `normal` alone.

So the base is the official query plus `highlights-extra.scm`, a 15-line extension
of my own for what it misses: `;` and `;;`, brackets, the operators
`|| = += =~ == != &> <& >& >| << <<<`, `test_operator`, `number` and `regex`.
Total: 17 patterns, 12 captures.

### The rule is still: do not fork

| Invocation route | Cost per keystroke |
|---|---|
| `fork` plus `exec` of any binary | 917 us |
| starting an empty python | 16 000 us |
| round trip through a persistent coprocess with `cat` | 69 us |
| **round trip with this highlighter, warm** | **158 us** |

Inside the coprocess, the actual work:

| Stage | Time |
|---|---|
| tree-sitter parse | 10.9 us |
| query plus painting, 45-character line | 44.5 us |
| query plus painting, 432-character line | 313 us |
| incremental reparse passing the previous tree | 1.1 us |

So of the 158 us, 69 is the pipe and 45 the work; the rest is Python. A Rust binary
using the `tree-sitter` and `tree-sitter-bash` crates would sit near 69 us and start
in a couple of ms. Incremental reparsing is not worth it: the pipe dominates, not the
parse.

**Startup:** 47 ms to `READY`. Launched in the background when the shell opens, the
prompt appears instantly. The first few keystrokes are a little slower while the
`which` cache fills.

### Where it wins and the bash tokenizer loses

With `tricky-cases.txt`, the bash one gets wrong:

- `echo "escaped \" inside" and outside` — it treats the escaped quote as a closer
  and mispaints the rest of the line. tree-sitter gets it right.
- `for f in *.sh; do nosuch-cmd "$f"; done` — it does not see that a new command
  starts after `do`, so it does not flag the unknown one in red. That is the single
  most useful signal in the whole thing.
- It paints `if`, `then`, `fi`, `for` and `do` as commands, not keywords.
- It splits `&&` into two `&` and `<<` into two `<`.
- It leaves `$((2 + 3 * 4))` uncoloured except the dollar.

Verified in a pty with the final version: keywords, brackets, delimiters, unknown
command in red, arithmetic numbers, escaped quote handled, the line runs, zero errors.

**What tree-sitter does not solve:** green or red on whether the command **exists**
is semantic, not syntactic. That is `shutil.which` with a cache inside the
coprocess. tree-sitter only says where the command name is.

## Files

- `editor.sh` — the read loop, single copy. Colouring is **pluggable**: it calls
  `__ed_colorize_into`, which leaves the result in `$__COLORED`. It also exposes
  `__ed_key_hook`, so whoever integrates it can handle their own keys.
  Keys: insert, delete, arrows, Home/End, Del, C-a C-e C-b C-f C-k C-u C-w C-y C-l
  C-p C-n, Esc-b Esc-f Esc-d, C-left/right, TAB and C-d. Plus `__ed_seed_history`,
  which seeds the up arrow from bash's real history, and `__ed_syntax_status`, the
  pluggable "is this finished?" check behind multiline continuation.
- `editor-treesitter.sh` — a 40-line layer over `editor.sh` that swaps the
  colouriser for the coprocess. **The recommended version.**
- `tokenizer.sh` — the default colouriser, plain bash, no dependencies.
- `ts_highlighter.py` — the tree-sitter coprocess. Takes `--info` to show where it
  loads the rules from.
- `highlights-extra.scm` — the 15-line extension over the official query.
- `venv/` — environment with `tree_sitter` 0.26.0 and `tree_sitter_bash`. 19 MB.
  Rebuild with:
  `python3 -m venv venv && venv/bin/pip install tree_sitter tree_sitter_bash`
- `macros-readline.sh` — the 11 live macros translated to `bind -x`. Tested against
  ble.sh: same behaviour, same `(auto)➜` notice. The lab has a richer version.
- `tricky-cases.txt` — the bash cases to compare highlighters against.
- `LSP.md` — is a language server worth it in a prompt? Measurements say mostly no.
- `PRIOR-ART.md` — is a terminal IDE new? No. Who has already built it.
- `NVIM-INLINE.md` — editor mode as an inline nvim. Probed and it works: 1.51 ms per
  keystroke with your real config, and it brings its own highlighting.
- `nvim_ui_probe.py` — the msgpack-rpc UI client behind that probe.
- `lsp_client.py`, `bench_lsp.py` — the harness that produced LSP.md's numbers.

## Trying it without installing anything

    bash --rcfile <(printf '%s\n' \
      'export TS_PY=$HOME/doc/shell-editor-poc/venv/bin/python' \
      'export TS_HL=$HOME/doc/shell-editor-poc/ts_highlighter.py' \
      'source $HOME/doc/shell-editor-poc/editor-treesitter.sh') -i -c __repl

Leave with C-d. In practice you want `~/shell-lab/lab` and then `hl`, which is this
same editor integrated with the prompt, the metadata, the marks and the history.

## Multiline continuation: the two-stage gate

The editor now waits for an unfinished command the way bash does, printing `>` and
reading on. The neat part is where the answer comes from: **the coprocess is already
parsing on every keystroke and used to throw that away.**

`ts_highlighter.py` answers a status query, a line prefixed with the `0x01` byte,
with `ok`, `inc` or `err`. Safe as a sentinel because the editor never lets a control
byte into the line, and newlines travel escaped so the protocol stays line-based.

But tree-sitter alone is not enough, and the measurement says why:

| Line | has_error | missing node | error at end | verdict |
|---|---|---|---|---|
| `for i in 1 2; do` | yes | `done` | no | incomplete |
| `echo hola \|` | yes | `word` | no | incomplete |
| `echo 'unclosed` | yes | none | **yes** | incomplete |
| `echo )` | yes | none | **yes** | **invalid** |
| `\| echo` | yes | none | no | invalid |
| `echo hola` | no | none | no | complete |

The last two rows of the same signature are the problem: `echo 'unclosed` and
`echo )` are indistinguishable to the grammar. Looping on `has_error` alone would
trap you forever on an invalid line.

So `inc` means "possibly incomplete" and the caller settles it with `bash -n`, which
is the authority on what bash will run:

- empty output → complete
- `unexpected end of file`, `unexpected EOF while looking for matching` or
  `delimited by end-of-file` → incomplete
- anything else → invalid, so it is run and bash prints its own error

| Stage | Cost | When |
|---|---|---|
| coprocess status query | 62 us | once per Enter |
| `bash -n` tiebreak | 1405 us | only when the parse is suspicious |

Sixty-two microseconds per Enter in the common case, because the work was already
being done. Without the coprocess `editor.sh` falls back to `bash -n` alone, which
works too and costs about 4 ms per Enter.

Verified in a real terminal: `for i in 1 2 3; do` waits, so does the second line,
`done` runs it and prints n=1 n=2 n=3. An unclosed quote waits and then runs. A
trailing pipe waits. `echo )` is **not** trapped, bash complains. C-c abandons an
unfinished continuation.

**Known limitation:** during continuation only the current line is coloured, not the
accumulated text, so a bare `done` on its own line shows as an unknown command. The
fix is colouring the whole and displaying the tail, which is fiddlier than it is worth
right now.

## The wall: why ble.sh is 1 MB

Keeping readline and capturing keys with `bind -x` **does not work**: readline
repaints after every handler and erases what you drew. Verified. That is why these
editors drop readline, and why everything readline gave has to be rebuilt by hand:

- history file integration and C-r search; the hstr binding stops working, being a
  readline macro. (The editor's up arrow is now seeded from the real history, and the
  lab adds its own C-r picker.)
- real completion, beyond the toy `compgen -f` it carries
- bracketed paste
- kill ring, word movement, transpose
- job control nuances, because here it is `eval` rather than letting bash read

## Three editor bugs that surfaced from using it

1. **The default branch inserted control characters literally.** C-w, C-g and
   friends were not in the `case`, fell to the end and went into the buffer as raw
   control bytes. It was not that they "did nothing": they dirtied the line. Any
   unhandled `[[:cntrl:]]` is now ignored.
2. **There were two copies of `__read_line`**, one in `editor.sh` and one in
   `editor-treesitter.sh`, so every bug in the loop had to be fixed twice. Hence the
   pluggable colouriser.
3. **Reading a fixed number of bytes after ESC does not work.** `\e[D` is 2 bytes,
   `\e[3~` is 3 and `\e[1;5D` is 5: reading a fixed 2 left the rest in the stream and
   it ended up inserted as text. It now reads to the final byte. And the wait after
   ESC is 0.4 s, not 0.06: a person pressing Esc then f does not make it in 60 ms.
   readline uses 0.5 s for the same reason.

Also, an empty subscript on an associative array is an ERROR in bash, not "absent":
the key hook received Enter as an empty string and printed `bad array subscript`.

## Four traps I fell into measuring this

1. `local line=$1 out= n=${#line}` **does not work**. Bash expands every argument of
   `local` before assigning them, so `n` read the outer scope's `line` and came out
   0. The colouring did nothing and I was benchmarking a no-op, which gave a false
   0.46 ms. It takes two statements.
2. `$(type -t "$w")` is a command substitution, i.e. a fork per keystroke.
   `type -t "$w" >/dev/null` gives the same yes/no without forking.
3. `for line in sys.stdin` in Python uses a read-ahead buffer that adds about a
   millisecond per round trip in interactive use. `sys.stdin.readline()` does not.
4. Methodological: the test shells inherited the parent's dirty PATH, which inflated
   the figure from 0.75 ms to 10 ms. PATH has to be set explicitly in the test
   environment.

A command table precomputed with `compgen -c` at startup costs 70 ms and 2179
entries, but with a clean PATH it is unnecessary: `type -P` per keystroke is already
free.
