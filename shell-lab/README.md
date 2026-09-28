# shell-lab

A bash prompt that shows you what you are doing. One prompt, with vim's normal mode
behind `Esc`.

    ➜  git commit -m hola          you type: highlighting, macros, history, multiline
    Esc
    (nvim)➜  N  git commit -m hola  a real nvim in normal mode, your buffer, your cursor
    dw · yiw · ciw · 3x · p
    Enter                           runs it, and the next prompt is the fast one again

Nothing to switch, nothing to remember. It replaced ble.sh here, and measures 0.16 ms
per keystroke against ble.sh's 27.7, with startup down from 397 ms to 50.

## What you get

- **Highlighting** from tree-sitter's real bash grammar, with the command name green
  when it exists and red when it does not.
- **How long the last command took, and its exit status**, on a line above the prompt
  and only when there is something to say.
- **Your own history with metadata**: exit status, duration, directory, session. `C-r`
  searches it and shows, per command, the status of its last run, how many times you
  launched it, how many failed and the mean duration, with a preview of its last runs
  and where you ran them.
- **Terminal block marks** (OSC 133), so the terminal can colour each command by
  success and let you jump between them.
- **vim behind `Esc`**, backed by a real nvim with your config, your keymaps and your
  colourscheme.
- Your ble.sh macros, on `C-g`, working in both the fast editor and nvim's normal mode.

## Installing

Nothing here is deployed on top of your config. It is a folder you point at.

**1. The folder.** Symlink or copy it where you keep it:

    ln -s ~/dotfiles/shell-lab ~/shell-lab

**2. Two guards in `.bashrc`.** So the lab can start without ble.sh while your normal
shell keeps it. Wrap the two lines that load and attach it:

    [ -z "${SHELL_LAB:-}" ] && source "$HOME/.local/share/blesh/ble.sh" --rcfile ...
    [ -z "${SHELL_LAB:-}" ] && [[ ${BLE_VERSION-} ]] && ble-attach

Without the variable your shell behaves exactly as before. That is the only change the
lab needs outside its own folder. If you do not use ble.sh, skip this.

**3. A one-word way in.** Optional. In `~/.config/bash/.bash_lab.sh`, which the loop in
`.bashrc` picks up on its own:

    alias lab='$HOME/shell-lab/lab'
    alias lab-plain='LAB_AUTO_EDITOR=0 $HOME/shell-lab/lab'

**4. The Python environment**, for the tree-sitter highlighter and the nvim editor.
Deliberately not committed: it is 21 MB of third-party packages against 296 KB of code.

    cd ~/shell-lab/editor
    python3 -m venv venv
    venv/bin/pip install tree_sitter tree_sitter_bash msgpack

Then `lab`, or `~/shell-lab/lab`.

## What it needs

| | |
|---|---|
| bash 5 | `$EPOCHREALTIME` for the timer, associative arrays |
| python3 | the highlighter coprocess and the history queries, standard library only |
| nvim 0.11+ | for the `Esc` editor. Without it, `Esc` does nothing and the rest works |
| fzf | for the `C-r` picker. Without it, a numbered list |
| git | for the `C-g` macros |

Every piece checks for what it needs and stands down rather than breaking. Missing nvim
costs you the `Esc` mode and nothing else.

## Keys

    Esc          vim's normal mode, with the line you were writing
    C-r          the augmented history
    Esc r        the same, only this directory
    C-g s        git status, and the rest of your macros on C-g
    C-w C-y      delete and paste a word, plus C-a C-e C-k C-u C-l C-p C-n
    Esc-b Esc-f  by word, and C-left / C-right
    C-d          drop to plain readline without closing the shell
    C-g e        back up to the editor
    exit         back to your normal shell

## The pieces

Each file in `parts/` is one concern and each one can be switched off, which is how you
bisect a problem.

| File | What it does | Off with |
|---|---|---|
| `05-keys.bash` | key dispatcher for the editor, with a registry so pieces do not fight | - |
| `10-macros.bash` | your macros, defined once and served to readline and to the editor | `LAB_MACROS=0` |
| `20-timing.bash` | how long the last command took, without forking | `LAB_TIMING=0` |
| `30-osc133.bash` | the terminal block marks | `LAB_OSC133=0` |
| `40-history.bash` | the history record, one `printf` append | `LAB_HISTORY=0` |
| `45-histsearch.bash` | the `C-r` picker | `LAB_HISTSEARCH=0` |
| `50-prompt.bash` | composes the metadata line with your own prompt | `LAB_META=0` |
| `90-highlight.bash` | the fast editor with tree-sitter | - |
| `91-nvline.bash` | the nvim-backed editor | `LAB_NVLINE=0` |
| `92-unified.bash` | `Esc` handing the line to vim | `LAB_ESC_TO_NVIM=0` |

`editor/` holds the two line editors and the highlighter. `bin/histdb` queries the
history. `LAB_EDITOR_TAG=` gives you a prompt with no mode marker.

## What it costs

| | |
|---|---|
| A keystroke in the fast editor | 0.16 ms |
| A keystroke in nvim, with a full config | 1.51 ms |
| A keystroke in ble.sh, for comparison | 27.70 ms |
| Starting the lab | 50 ms |
| Recording a command in the history | 430 µs |
| Implementation | 2300 lines |

## The tests

    test/run              all of it, through a real pty
    test/run regression   one file

Fourteen files, and they are the reason this works. Every bug written up in `doc/` was
either found or confirmed by one of them.

A warning worth passing on: several of these gave **false failures** before they gave
true ones. readline repaints with backspaces, so the echoed line is not the output line.
An f-string swallows `\x1b` into a literal backslash. `git status` needs a git repo. And
when the editor started auto-starting, every test that typed `hl` was suddenly testing
something else. When a check fails, suspect the check first.

## Where the detail is

- `doc/LAB.md` — how each piece works, and the four traps met building them.
- `doc/MEASUREMENTS.md` — the numbers, and why the expensive part of ble.sh is the line
  editor rather than the colouring.
- `doc/NVIM-INLINE.md` — nvim as a line editor: the mechanism, what it cost, and the
  three bugs that only showed up from using it.
- `doc/LSP.md` — is a language server worth it in a prompt? Measurements say mostly no,
  and the one piece that is.
- `doc/PRIOR-ART.md` — is a terminal IDE new? No. What already exists, and the three
  gaps that seem to remain.
