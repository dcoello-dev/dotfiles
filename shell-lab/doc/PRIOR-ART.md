# Is a "bash LSP for the terminal" new? Reviewed 2026-09-26

**No. The field is fairly crowded, with named products and corporate backing. What
does seem absent is the protocol-shaped framing.**

## What already does exactly this

| Project | What it is | Status |
|---|---|---|
| **Amazon Q Developer CLI** | Formerly **Fig**. IDE-style completion for hundreds of CLIs via declarative *completion specs*. Literally the idea. | AWS acquired Fig in 2023; standalone Fig sunset 1 Sep 2024. The specs remain open. |
| **microsoft/inshellisense** | "IDE style command line auto complete". 600+ tools, bash/zsh/fish/PowerShell. Suggests commands, flags, arguments, paths and git branches as you type. | Alive, from Microsoft, on npm and homebrew. |
| **carapace-bin** | Parameter completion for 500+ commands from **a single Go binary**, across nine shells: bash, zsh, fish, PowerShell, nushell, elvish, oil, tcsh, xonsh. Its `carapace-bridge` reuses whatever completion systems you already have. Motto: "configure once, use everywhere". | Alive. The closest thing to a protocol. |
| **fish** | Highlighting as you type, unknown command in red. History autosuggestions. And `fish_update_completions` **parses the man pages installed on your system** to generate completions. | Since 2005. The "understands the system" part is 20 years old. |
| **nushell** + **reedline** | Line editor with content-aware highlighting, completion with a graphical menu, multiline. The shell's own parser. | Alive. |
| **shellcheck-repl** | Validates the command line with ShellCheck **at the bash prompt**. | Alive. See the nuance below. |
| **bash-language-server** | The bash LSP genuinely exists. Nobody has wired it to a terminal. | Alive. Measured in `LSP.md`. |

## The three gaps that do seem open

**1. shellcheck-repl validates on Enter, not as you type.** Checked in its
documentation: it hooks into the bash REPL, intercepts the line as read, runs it
through ShellCheck and **if there is a finding it does not execute the command**, it
shows the error and stops. Synchronous and blocking. You bypass it by adding two
trailing spaces.

That is a different thing from what the measurements in `LSP.md` point at:
asynchronous, debounced, **never blocking**, warning while you write rather than
refusing to run, and gated on tree-sitter's `has_error` so it stays quiet while the
line does not parse yet. Nobody seems to do it that way.

**2. Nobody speaks LSP in the terminal.** Every one of those tools reinvents its own
format: Fig's specs, carapace's, bash-completion's functions, fish's completion
files. Searching for a formal LSP-for-shell proposal turns up nothing, and
langserver.org lists no terminal client. The protocol framing, one protocol so any
shell gets completion, diagnostics and hover from any provider, is the real gap.

**3. No shell line editor delegates to tree-sitter.** reedline uses nu's parser,
ble.sh has a hand-written one, fish and zsh their own. I found none using tree-sitter,
which is what `ts_highlighter.py` does.

## And a TUI that looks like a terminal but works how we want?

Measured. Nothing prevents it, but "a TUI that looks like a terminal" **is** writing
a terminal emulator, and the cost sits in two places.

1. *Performance.* An emulator in Python (pyte) takes **0.9 MB/s**. A `find` over
   `~/code` is 1.3 MB, so 1.4 s just to parse before drawing anything. A native
   terminal does hundreds of MB/s. In Rust (the `vt100` or `wezterm-term` crates) this
   is solved, so the objection is against Python, not against the idea.
2. *Feature surface, and this one is language-independent.* Capturing real apps: htop
   uses 8 families of escape sequences, nvim 10 (mouse, RGB, OSC, bracketed paste) and
   less 3. **All three use the alternate screen.** Either you implement the full VT
   faithfully, or when vim opens you hand it the screen and your TUI adds nothing for
   the duration. And some apps query the terminal (`ESC[6n`) and expect an answer.

Here it would also be the third layer: Windows Terminal -> your TUI -> the apps. Warp
is exactly this approach, and to do it they wrote a GPU-accelerated terminal. That is
a company, not a dotfile.

The route that avoids all of it, and the one the industry converged on: **cooperate
with the terminal via OSC 133** (it paints the blocks, zero emulation) and **own only
the input line** (highlighting and ghost text, zero emulation). Both already work in
`~/shell-lab`.

## Practical advice

- If what you want are **the features**, they exist and you would have them in ten
  minutes: `carapace` for completion in bash, or `inshellisense`. Building it would be
  redoing maintained work.
- If what you want is **the protocol**, or non-blocking live diagnostics, that is open
  ground and it fits what is already built here.

## Sources

- https://github.com/microsoft/inshellisense
- https://github.com/aws/amazon-q-developer-cli-autocomplete
- https://github.com/withfig/autocomplete
- https://github.com/carapace-sh/carapace-bin
- https://github.com/carapace-sh/carapace-bridge
- https://github.com/HenrikBengtsson/shellcheck-repl
- https://fishshell.com/docs/current/cmds/fish_update_completions.html
- https://github.com/nushell/reedline
