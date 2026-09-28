# shell-lab

A sandbox for living without ble.sh and wiring in your own tools. It touches
nothing in your config: you go in, try it, leave, and everything is as it was.

## Using it

    lab

One word, and you land straight in the editor with highlighting on. The `lab` alias
lives in `~/.config/bash/.bash_lab.sh`, which your `.bashrc` loads on its own through
the `for f in ~/.config/bash/.bash_*` loop, so nothing in `.bashrc` was edited for it.

    lab-plain                start in readline instead of the editor
    lab -c 'command'         run one command inside and leave
    LAB_TIMING=0 lab         switch one piece off

Inside: `C-d` drops from the editor to readline without closing the shell, `C-g e`
brings it back, and `exit` returns you to your normal shell, ble.sh and all.

`lab -c` never enters the editor: it has one command to run and leave. The check is
that `$-` carries a `c` in that case.

What you see on entry:

    shell-lab  no ble.sh  |  on: macros timing marks history search meta
              C-g e toggles the editor   C-r augmented history   exit back to your shell
    ── editor on. C-d leaves. no hstr and no TAB subcommands in here.
    [3:53:18pm]:~/code/argos (feat/bounded-workspace-syncback)
    (editor)➜

## How it is wired

`lab` starts `bash --rcfile lab.bash`. `lab.bash` exports `SHELL_LAB=1`, loads
**your real `.bashrc`** and then stacks the pieces in `parts/` in order.

Loading your real `.bashrc` is deliberate: the lab always inherits your PATH, your
aliases, your functions and your prompt, and only changes what it means to change.
Edit your config tomorrow and the lab follows with no work.

Your `~/dotfiles/.bashrc` has **two added lines**, one guard on the ble.sh load and
one on `ble-attach`:

    [ -z "${SHELL_LAB:-}" ] && source .../ble.sh ...
    [ -z "${SHELL_LAB:-}" ] && [[ ${BLE_VERSION-} ]] && ble-attach

Without the variable everything behaves as always. Verified: without it
`BLE_VERSION` reads `0.4.0-devel4`, with it, empty.

## The pieces

| File | What it does | Switch off with |
|---|---|---|
| `05-keys.bash` | Key dispatcher for the `hl` editor. Other pieces register keys in `__LAB_KEYS`, so adding one is a line and they never fight. | - |
| `10-macros.bash` | The macros that actually worked: the **9 git ones on C-g** plus htop on C-x h. Defined **once** in a table and served to both front ends, readline and the `hl` editor. Of the 83 declared only 11 were alive; the other 72 called `subset.py`, which does not exist, or missing binaries. The `C-e x` one was dropped to keep `end-of-line`. | `LAB_MACROS=0` |
| `20-timing.bash` | How long the last command took, with `$EPOCHREALTIME` and no forks. | `LAB_TIMING=0` |
| `30-osc133.bash` | Terminal integration marks: per-command blocks, coloured by success. | `LAB_OSC133=0` |
| `40-history.bash` | Your own history with metadata, one `printf >>`. | `LAB_HISTORY=0` |
| `45-histsearch.bash` | **Augmented history search on C-r**, both front ends. See below. | `LAB_HISTSEARCH=0` |
| `50-prompt.bash` | Composes the metadata line with your `__setprompt`, without replacing it. | `LAB_META=0` |
| `91-nvline.bash` | **Editor mode backed by a real nvim**, inline on one row. `nv` starts it, `C-g v` toggles it. nvim's modal editing, your keymaps, your colourscheme. 1.51 ms per keystroke with your full config. **You start in insert mode** and type straight away, like any prompt; `Esc` gives you normal mode. The prompt carries a three-column mode badge: `I` green, `N` blue, `V` magenta, `R` red. **In normal mode your `C-g` git macros work**, and whatever you had half-typed comes back afterwards. | `LAB_NVLINE=0` |
| `90-highlight.bash` | The custom editor with tree-sitter, started automatically unless `LAB_AUTO_EDITOR=0`., integrated with the rest: inside it you keep your prompt, the metadata line, the marks and the history. **Start it with `hl`**, leave with C-d. Always available, no variables. | not needed |

## What it costs

| Piece | Cost |
|---|---|
| `history 1`, the only process, once per command run | 430 us |
| reading the timer | 12 us |
| writing the history record | 16 us |
| **for comparison: what ble.sh cost, per keystroke** | **27 700 us** |

## Keys: what changes against ble.sh

`C-e` is still **end of line**, verified. The `C-e x` macro was removed for exactly
that: hanging anything off `C-e` turns it into a prefix and steals a key people use.
To leave, `exit` or C-d.

`C-x h` (htop) stays, because `C-x` is already a native readline prefix
(`C-x C-e`, `C-x C-v`...), so hanging something there takes nothing away.

`C-g` **is still a prefix**, since that is where your 9 git macros live. That
displaces `abort`, which moves to `C-x C-g` and `Esc C-g`. To clear the line, `C-u`.

Everything else is unchanged, verified in a real terminal: `C-r` (see below) and TAB
completing paths (`/etc/pass` gives `passwd`), subcommands (`git chec` gives
`checkout`), commands (`ech` gives `echo`) and variables (`$HOM` gives `$HOME`).

## One prompt, with vim behind Esc

This is the shape it settled into. There are no modes to switch between:

    ➜  git commit -m hola          you type: highlighting, macros, C-r, multiline
    Esc
    (nvim)➜  N  git commit -m hola  vim's normal mode, your buffer, your cursor
    dw, yiw, ciw, p, 3x, whatever
    Enter                           runs it, and the next prompt is the fast one again

`Esc` hands the line to a real nvim in normal mode, carrying the buffer and the cursor.
From there `i` and friends type in nvim, and Enter runs the line either way. Switch it
off with `LAB_ESC_TO_NVIM=0`, and `nv` or `C-g v` still start you inside nvim if you
want that.

Worth knowing, and it surprised me first: pressing `Esc` leaves the cursor **on** the
last character, not after it, exactly as vim does when you leave insert mode. So a `dw`
there deletes from that letter. My first test asserted otherwise and was wrong.

The `(editor)` marker on the normal prompt is left over from when there were two modes.
Now that there is one, `LAB_EDITOR_TAG=` gives you a clean prompt and you only see a
marker when you are actually in nvim.

## The augmented history: C-r

`C-r` no longer searches text over `~/.bash_history`. It queries your database and
shows, **per command**:

- the exit status of the **last** run
- how many times you launched it and how many failed
- the mean duration
- how long ago the last one was

And as you move through the list, the preview lists that exact command's latest
runs, each with its status, its duration and **the directory you ran it in**.

A real example from the tests: `git log --oneline -n3` showed up with status 128,
and the preview explained why: it had been launched from `/tmp`, which is not a
repo. That information existed nowhere before.

    C-r      the whole history
    Esc r    only commands from this directory

Unlike hstr it **does not run on its own**: it leaves the command on the line for
you to review. This displaces hstr's shortcut, which was on C-r; hstr is still one
word away by typing `hstr`, and its `C-x k` is untouched. `LAB_HISTSEARCH=0` if you
prefer hstr.

It uses fzf, which you already had at `/usr/bin/fzf`, and falls back to a numbered
list if it were missing. It goes full screen on purpose: with a fixed height fzf
draws inline and fights the `hl` editor, which is repainting right there.

More views from the command line:

    histdb runs <command>    the latest runs of THAT exact command
    histdb pick [--here]     the same picker, standalone
    histdb top               most used, with failures and duration
    histdb fails / slow / here / find / stats / last

## The highlighting: why a custom editor is needed

tree-sitter works fine, it returns the coloured line in 158 us. **The problem was
never tree-sitter: there is nowhere to paint.** readline owns the drawing of the
line you type and exposes no hook to colour it; it repaints from its own buffer,
without colour. So to see colours you must take over the redraw, and that means
replacing readline.

That is what `hl` does, and it is available always with no variable. Loading its
code costs 0 ms and starting its coprocess 42 ms, paid the first time you type it.
Verified inside the editor: unknown command in red, valid in green, strings,
operators and pipes coloured, and on top of that you keep your real prompt with
time, path and branch, the metadata line, the four OSC marks and the history record.

**`C-g e` toggles the editor**, both ways. It fits the existing chord family so it
steals no new key. `C-d` still leaves too.

**You can always tell which mode you are in.** The prompt carries an `(editor)`
marker while `hl` is on, in the same cyan as the `(auto)` the macros print, and the
continuation prompt shows `(editor)>`. Without it the prompt was identical inside and
outside and there was no way to know. Override it with `LAB_EDITOR_TAG`.

**Your macros DO work inside**, readline bindings though they are: they live in a
table and the editor serves them through its key hook. If you had something
half-typed when you fire one, it comes back at the next prompt.

The editing keys work too: C-w, C-y, C-a, C-e, C-b, C-f, C-k, C-u, C-l, C-p, C-n,
Esc-b, Esc-f, Esc-d, C-left, C-right, Home, End and Del. Plus C-r, which opens the
same augmented picker.

**The up arrow now sees your real history.** The editor used to start with an empty
history and only remembered what you typed in that `hl` session, which was the most
annoying gap against ble.sh. It is now seeded with the last 500 entries of bash's
history on entry; verified, 500 of your 3938.

Leave with C-d and you are back in readline.

**Multiline works.** `for i in 1 2 3; do` waits with a `>` and runs when you close it
with `done`, same for unclosed quotes and trailing pipes. The answer comes from the
parse the coprocess is already doing, 62 us per Enter, with `bash -n` as the
tiebreaker in the rare suspicious case. `echo )` is not trapped: bash complains.
Details in the prototype's README.

**The price, while the editor is active:** C-r search via hstr goes away, and so does
bash's programmable completion (TAB becomes a toy `compgen -f`) and bracketed paste.
That is readline, and it is not there.

### What it took to integrate

The prototype's `__repl` is its own read loop, so it **does not go through `PS0` or
`PROMPT_COMMAND`**. As-is, inside the editor the metadata line and the marks were
lost, the duration was recorded wrong (11 seconds for a `sleep 0.35`, because the
timer never started) and it drew a fake prompt. `__lab_repl` calls the hooks by hand
and gets your real prompt out of `${PS1@P}`, splitting the upper lines (printed
once) from the last one (redrawn on every keystroke).

Three traps on the way. `coproc` **always** prints a job notice like `[1] 2481373`
in an interactive shell, and nothing suppresses it: verified in a real pty with
`set +m` before, `set -m` after, `disown` and every combination. That stray line was
the first thing you saw after typing `hl`, and it read like an error. The transport is
now a process substitution plus a fifo opened `<>`, so the open never blocks waiting
for a writer and nothing is announced. Then: leave the OSC sequences inside the prompt being redrawn
and the terminal receives **ten "user input starts here" marks per command**; they
have to come out of the prompt and be emitted by hand, once. And the loop has to
start the highlighter coprocess, which the original `__repl` did on its first line:
without it nothing gets coloured, and the greens that look like they work are your
prompt arrow, which uses the same 118.

## Still missing

**Inline ghost text**, the kind that says "last time this took 48 s and exited 1".
That is why the metadata line goes **above** the prompt: printed before, readline
does not fight it. Inline does need the custom editor, so it would fit there.

One gap left in `hl`: **TAB with subcommands**. Multiline is done, see the
prototype's README for how.

The editor prototype, with all its measurements, lives in `~/doc/shell-editor-poc`.
That directory is the measured reference; the integration with the lab lives here,
in `parts/90-highlight.bash`, to keep it clean.

## Four things I found building this

**`PS0` is no good for timing.** The obvious form is
`PS0='${t:=$EPOCHREALTIME}'`, but it **prints the timestamp on screen**. Also tried
wrapped in `\[ \]`, which in `PS1` means "non-printing": in `PS0` it makes no
difference, out it goes. So the timer lives in a `DEBUG` trap, which prints nothing.
`PS0` is used only for the OSC 133 `C` mark, where printing is the point.

**`PS0` does not understand `\[ \]` either.** This first reused the helper that
wraps the OSC sequence for `PS1`. Bash turned those `\[ \]` into the control bytes
`0x01` and `0x02` and spat them out **literally**, right in front of whatever each
command printed. Invisible on screen, but it pollutes any captured output. It showed
up when dumping the raw pty stream.

**A readline handler that runs a command leaves the timer armed.** A `bind -x`
handler like the C-g macros, or the C-r picker, fires the `DEBUG` trap and arms the
timer, but it never goes through the prompt cycle, so nothing disarms it. The next
real command then inherited every second you spent reading that output. It surfaced as
an `8m38s` on a command that failed instantly, and reproduces as a `true` reporting
11.38 s. Any handler that runs something now calls `__lab_timer_reset` when it
finishes, and the prompt cycle clears the start mark too.

**The `DEBUG` trap also fires for `PROMPT_COMMAND`**, even when you press Enter on
an empty line and nothing runs. Verified by dumping `$BASH_COMMAND` on every fire:
an empty Enter gives two fires, both carrying the name of the `PROMPT_COMMAND`
function; a real command shows up between them. Without filtering that, the history
filled with phantom entries carrying invented durations.

Tried `$HISTCMD` first, which looked like the ideal signal since it only advances on
new commands, but it **does not work**: it does not advance inside the editor's own
read loop, so all records but the first were lost there. The right signal is a
variable set by both paths, the filtered `DEBUG` trap and the custom loop by hand.

**The session's first prompt was lying.** `history 1` there returns the last line of
the history file, i.e. the last command of the *previous* session. A phantom `exit`
got recorded with an invented duration. That prompt is now skipped.

## The history and querying it

The shell only does a `printf >>` into `var/history.tsv`. Tab-separated fields: unix
time, exit status, duration in microseconds, directory, session and command. In the
command only backslash, tab and newline are escaped, with two parameter
substitutions and no processes.

`bin/histdb` imports those records into SQLite when you ask and then queries. It
uses only python3's standard library, because there is no sqlite3 CLI on this
machine but the module is there. The import is incremental: it stores the file
offset and only reads what is new.

The schema is in `bin/histdb` and it is yours: to add fields, add them to the
shell's `printf` and to the `INSERT`.

## Turning the marks on in Windows Terminal

The OSC 133 marks are already being emitted. For the terminal to use them, in its
`settings.json`:

    "autoMarkPrompts": true,
    "showMarksOnScrollbar": true

And a `scrollToMark` action to jump between commands. Inside tmux the sequences are
wrapped so they pass through; your `tmux.conf` already has `allow-passthrough on`,
which is what is needed.

## The test harness

    test/run              every check, in a real pty
    test/run regression   just one file

It lives in the repo and not in `/tmp` because `/tmp` is wiped when WSL boots, and this
harness is the only thing that catches the regressions. Every bug documented above was
either found or confirmed by one of these files:

| File | What it pins down |
|---|---|
| `regression.py` | the 16 core checks, both modes |
| `multiline.py` | continuation, and that `echo )` is not trapped |
| `timer.py` | that a macro does not inflate the next command's duration |
| `autostart.py` | `lab`, `lab-plain` and `lab -c` behaving differently |
| `nested-editor.py` | that typing `hl` inside does not nest |
| `nvim-mode.py` | nvim mode starting, colouring, running and leaving |
| `nvim-modal.py` | that `ciw`, `dw`, `3x`, `I`/`A` and `yiw`/`p` really work |
| `nvim-keys.py` | backspace, Delete, arrows, Home/End, C-Left, and a literal `<` |
| `nvim-lines.py` | that `o` does not silently drop the first line |
| `nvim-modetag.py` | the mode badge following i / Esc / v / R |
| `nvim-chords.py` | `C-g s` and `C-g h` in normal mode, and the pending line returning |
| `nvim-chord-timing.py` | the chord firing at 50 ms and at a 2 second hesitation |
| `unified-esc.py` | Esc handing the line to vim and coming back |
| `mode-switch.py` | `C-g v` and `C-g e` switching modes both ways |

A warning from experience: several of these tests gave **false failures** before they
gave true ones. Readline repaints with backspaces, so the echo line is not the output
line; an f-string swallows `\x1b` into a literal backslash; `git status` needs a git
repo; and after the editor started auto-starting, every test that typed `hl` was
suddenly testing the wrong thing. When a check fails, suspect the check first.

## Promoting or undoing

**Promote:** when a piece convinces you, copy the file into `~/.config/bash/` with a
`.bash_*` name and your `.bashrc` will load it on its own, since it already has the
`for f in ~/.config/bash/.bash_*` loop.

**Undo entirely:** remove the two `SHELL_LAB` guards from `.bashrc` and delete this
directory. A copy of the original files from before any of this is in
`~/dotfiles-backup-20260926-110610`.
