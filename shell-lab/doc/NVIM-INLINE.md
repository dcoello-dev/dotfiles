# Editor mode as an inline nvim. Built and working, 2026-09-26

**`nvline.py` is a working line editor.** In the lab: `nv` starts it, `C-g v` toggles
it, `C-d` on an empty line leaves. Real nvim modal editing at the bash prompt, with
your own colourscheme.

Verified against actual command output, not just the painted line: `ciw` changes a
word, `I` and `A`, `dw`, counts like `3x`, and `yiw` plus `p`. A one-line `for` loop
runs. Six distinct colours from your theme on a single line.

The idea: make the line editor an actual nvim, rendered into one row of the terminal
rather than taking over the screen. Modal editing, your own keymaps, your own
highlighting and colourscheme, all at the prompt.

## The mechanism

nvim 0.11.3 supports `--embed`, which turns stdin/stdout into a msgpack-rpc channel.
You then call `nvim_ui_attach` and become nvim's UI: it sends you grid updates
(`grid_line`, `grid_cursor_goto`, `hl_attr_define`) and you draw them wherever you
like. That is how GUI clients work. Attaching a grid of **80 columns by 1 row**, with
`ext_cmdline` and `ext_messages` to push the command line and messages out of the
grid, leaves that single row holding nothing but the buffer.

Verified with `nvim_ui_attach 80 1`: typing through `nvim_input` produced 29 redraw
events and the row reconstructed exactly as
`git commit -m 'hola' && echo $HOME`.

## The numbers

| Setup | Startup | ms/keystroke |
|---|---|---|
| nvim `-u NONE` plus `syntax=sh` | 26 ms | **0.31** |
| **nvim with your real config** | 25 ms | **1.51** (max 3.85) |
| for reference: custom editor plus tree-sitter coprocess | 42 ms | 0.16 |
| for reference: plain readline, no highlighting | - | 0.33 |
| for reference: ble.sh | 397 ms | 27.70 |

Latency measured as the time from writing the key to the first redraw event landing,
which is what a person would perceive. Even with your full config loaded it is 18
times faster than ble.sh.

## The highlighting comes along

This was the part worth checking, and it works. `hl_attr_define` delivers real
attributes and the cells carry the ids:

- with `-u NONE` plus `syntax=sh`: 58 attribute definitions, and the cells split into
  distinct ids over `'hola'`, `-m` and `echo`/`grep` (the last bold).
- with your real config: ids in the 144-189 range carrying your colourscheme,
  foreground and background, e.g. `{'foreground': 15129460, 'background': 3027516}`
  over `'hola'`.

The attributes are RGB integers plus flags like `bold`, so converting them to ANSI for
the terminal is direct.

So nvim would replace **both** the custom editor and the tree-sitter coprocess: it
brings its own parser, its own queries and your own theme.

## How it is built

`nvline.py` draws on `/dev/tty` and prints the finished command on stdout, the way fzf
does, so the bash side is a command substitution and nothing more.

1. Grid row painted into the terminal, RGB attributes turned into ANSI truecolor.
2. Raw keystrokes go straight to `nvim_input`, so modal editing, keymaps and text
   objects are nvim's own. No key handling of ours at all.
3. `<CR>` is mapped to `rpcnotify(1, "submit")`, and the channel id of an `--embed`
   client is 1, so it reaches us. Then `nvim_get_current_line`.
4. The cursor follows `grid_cursor_goto`.
5. The prompt is drawn by us and the grid is `cols - prompt_width` wide, so nvim never
   knows the prompt exists.
6. Gutters stripped with
   `set nonumber norelativenumber signcolumn=no foldcolumn=0 laststatus=0 noruler`.
   Without it your line-number column shows up inside the grid as `  1   `.

### It starts in insert mode, on purpose

You land in insert mode and type immediately, like any shell prompt. `Esc` gets you
normal mode for editing, `i`/`a`/`I`/`A` go back. That is the only sensible default
here: a prompt where you had to press `i` first would be wrong.

### It really is your nvim

Verified, not assumed: `$MYVIMRC` reads `~/.config/nvim/init.lua`, the
colourscheme is **monokai** (which is where the pink keywords come from), 373 Lua
modules are in `package.loaded`, lazy.nvim is up, the leader is space and there are
183 normal-mode keymaps. Your config, your plugins, your keymaps.

### The mode indicator

nvim reports the mode through `mode_change`, with clean names: `normal`, `insert`,
`visual`, `replace`, `operator`, `cmdline_normal`. Drawn as a three-column badge
between the prompt and the line, always the same width so the grid never needs
resizing: `I` green, `N` blue, `V` magenta, `R` red, `O` orange, `C` cyan. Turn it off
with `--no-mode`.

Checked against `nvim_get_mode` rather than against the paint: `i`, `A`, `I` and `o`
all reach insert, `Esc` returns to normal, `v` to visual, `R` to replace. And none of
`A`, `I` or `o` is remapped by your config.

### Submit returns every line, not the cursor's

`o`, `O` and a multiline paste all create a second line. Taking only
`nvim_get_current_line` dropped the rest **silently**: `echo uno`, Esc, `o`,
`echo dos` came back as just `echo dos`. It now joins all the buffer's lines with a
newline, and bash evals that fine. Verified both commands run.

### `nvim_input` does not take raw terminal bytes

This is the one that bites. Control bytes under 0x20 happen to work, which is why it
looked fine at first, but the rest does not:

| What the terminal sends | What happened before | What it needs |
|---|---|---|
| `0x7f` Backspace | inserted a literal 0x7f, so you could not delete | `<BS>` |
| `\e[3~` Delete | became Esc then `[3` then `~`, and `~` toggles case, so `hola` became `holA` | `<Del>` |
| `\e[A`..`\e[D` arrows | moved nothing | `<Up>`..`<Left>` |
| a typed `<` | starts key notation | `<lt>` |

So `KeyDecoder` translates everything, keeping any partial sequence for the next read,
since a sequence can be split across reads, and flushing a lone `Esc` when nothing
follows it. Verified: backspace, Delete mid-line, arrows, Home, End, C-Left, a literal
`<`, and the literal text `<Up>` all behave.

### The C-g chords, and why they are not nvim mappings

In **normal mode** your git macros work: `Esc` then `C-g s` runs `git status`, with the
same `(auto)➜` notice as everywhere else, and whatever you had half-typed comes back at
the next prompt. In insert mode they are not bound, because there `C-g` is nvim's own
prefix and you are typing text.

They started out as `nnoremap <expr> <C-g>s rpcnotify(...)`. That was flaky in a way
that would have been maddening to use: **your `timeoutlen` is 300 ms**, so pressing
`C-g` and the letter quickly worked, and hesitating meant `C-g` fired alone, invisibly
because messages are externalised, and the letter went on to do its normal-mode job,
`s` substituting a character for instance.

So nvline resolves the chord itself, which needs no mapping and no timeout. Two things
had to be right, and each was wrong first:

1. **The mode has to be synchronised.** Typing fast, Esc and `C-g` and the letter all
   arrive in one `read`, and at that moment `grid.mode` still says insert because nvim
   has not processed the Esc. Checking the mode first made the chord work only when you
   hesitated, exactly backwards. The fix is to send everything before the `C-g`, then
   call `nvim_get_mode`: that call is synchronous, so its reply means nvim has caught
   up and the answer is the mode that actually applies.
2. **The decoder has to be flushed first.** A lone Esc sits in its pending buffer
   waiting to see whether it is a sequence, so nvim had not seen it either and answered
   "insert" anyway.

Verified at 50 ms, 300 ms, 800 ms and a 2 second hesitation, twice each: all fire.

### The bug that cost the most

It rendered correctly but **with no colour at all**, every cell a plain reset, even
though treesitter was demonstrably active. The cause was in my RPC client, not in
nvim: `pump()` returned the notifications it had just read, and `call()` also pumps
while waiting for its reply, and threw away what it got. Every `hl_attr_define` event
arrives during the setup calls, so the colour table was always empty. Notifications
now go on a queue that the main loop drains, and the loop drains it on every pass, not
only after a read.

Worth remembering: the attributes were arriving all along. A highlight table that is
empty when it should not be points at who is consuming the events, not at nvim.

## The honest catch, still true

**nvim owns the keys.** The `C-g` macros and the `C-r` history picker would stop being
bash-side handlers and would have to become nvim keymaps calling back over RPC. That
is arguably nicer, since you would write them in Lua with the rest of your config, but
it is a rewrite of that layer, not a port.

Also `--embed` means one nvim process per shell, about 25 ms to start and a few tens
of MB resident. Lazily started on first use, like `hl` is now.

## Files

- `nvline.py` — the editor. Draws on /dev/tty, prints the command on stdout. Exit
  codes: 0 run it, 1 cancelled, 2 end of input.
- `nvim_ui_probe.py` — the original minimal probe, kept because it is the smallest
  thing that demonstrates the mechanism.
- `msgpack` is now installed in `venv/`.
