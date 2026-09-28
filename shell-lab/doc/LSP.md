# A language server in the prompt? Measured 2026-09-26

**Summary: possible, but for a prompt an LSP adds almost nothing. The one thing worth
having out of that whole ecosystem is ShellCheck, and calling it directly is better.**

Actually built and measured: `bash-language-server` installed via npm, `shellcheck`
0.11.0 downloaded by the npm package of the same name, and a minimal stdio LSP client
with `Content-Length` framing in `lsp_client.py`.

## The numbers

| Operation | Cost |
|---|---|
| bash-language-server's `initialize` handshake | 7100 ms |
| the same with `rootUri` on an empty directory | 7248 ms |
| `publishDiagnostics` after `didOpen` or `didChange` | ~510 ms |
| **shellcheck called directly, fork included** | **5 to 6 ms** |
| `textDocument/completion` | 2 to 5 ms |
| `textDocument/hover` | 1 ms |

Two things dismantle the case for the LSP:

1. **The 7 seconds are not workspace indexing.** With `rootUri` pointing at an empty
   directory it takes the same, 7.2 s. It is the server's own startup. For a shell
   that opens in 52 ms that is unusable except as a background lazy load.
2. **The 510 ms of diagnostics is debounce, not work.** ShellCheck run directly gives
   the same two findings in 5 ms. The LSP makes the one valuable thing it offers 100
   times slower.

## The LSP's completion is worse than bash's

Same four cases, the LSP against native completion with bash-completion loaded:

| Input | bash | bash-language-server |
|---|---|---|
| `git ch` | `checkout`, `cherry-pick`, `cherry` | `chcpu`, `chgpasswd`, `chmem`, `chroot`: it treats it as a command name, it knows nothing about subcommands |
| `ec` | `echo`, `ec2metadata` | same |
| `echo $HO` | `HOME`, `HOSTNAME`, `HOSTTYPE` | only `HOSTNAME.EXE` |
| `cat /etc/pass` | `/etc/passwd`, `/etc/passwd-` | nothing, no path completion |

bash wins three of four and ties the other. Which makes sense: native completion
knows your aliases, your functions, bash-completion's specs (`complete -p git`
returns `-F __git_wrap__git_main`) and the real environment. The LSP has access to
none of that.

`hover` is genuinely nice: 1 ms and it returns bash's `help` text. But it is the one
thing `man` already gives you a key away.

## What is worth having: ShellCheck directly, async, with a gate

ShellCheck costs 5-6 ms per run. It has no server mode, it is a one-shot binary, but
that does not matter: diagnostics are asynchronous by nature. Fire it after a delay
once you stop typing and it never blocks a keystroke.

The noise is manageable, and there is a clean, free gate to filter it:
**tree-sitter's parse state, which we already have in the coprocess.**

| Line | Parses? | shellcheck findings |
|---|---|---|
| `g`, `git`, `git st`, `git status` | yes | 0, silent |
| `echo hello` | yes | 0 |
| `if [[ -n $x` | **NO** | 3, all syntax errors SC1009/SC1073 |
| `echo 'unclosed` | **NO** | noise |
| `echo hello \|` | **NO** | noise |
| `if [[ -n "$x" ]]; then echo yes; fi` | yes | 0 |
| `for f in $(ls); do echo $f; done` | yes | 2 useful: SC2045, SC2086 |
| `cd /tmp && rm -rf $DIR/*` | yes | 2 useful: SC2115, SC2086 |

So: **run shellcheck only when `tree.root_node.has_error` is false.** While the line
is half-written, stay quiet; once it parses, warn. And what it warns about is exactly
what you want to know before pressing Enter, the `rm -rf $DIR/*` kind with no quotes
and no `${var:?}`.

## Files

- `lsp_client.py` — minimal stdio LSP client, `Content-Length` framing, a reader
  thread and separate queues for responses and notifications. Reusable to measure any
  server.
- `bench_lsp.py` — the harness that produced the numbers above.

To reinstall the pieces:

    npm install bash-language-server shellcheck
