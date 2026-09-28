# Layer on top of editor.sh: colouring is done by the tree-sitter coprocess
# instead of the bash tokenizer.
#
# This used to be a full COPY of editor.sh with the colouring swapped, so every bug
# in the key loop had to be fixed twice. Now it only replaces the pluggable
# `__ed_colorize_into`.
#
# Needs TS_PY (the venv interpreter) and TS_HL (ts_highlighter.py).

__hl_start() {
    [[ -n ${__HL_DIR:-} ]] && return 0
    # NOT `coproc`. In an interactive shell coproc always prints a job notice like
    # "[1] 2481373", and nothing suppresses it: verified in a real pty with
    # `set +m` before, `set -m` after, `disown`, and every combination. That stray
    # line was the first thing you saw after typing `hl`, and it read like an error.
    #
    # Process substitution prints no notice. A fifo carries the way back, opened
    # with `<>` (read-write) so the open never blocks waiting for a writer.
    __HL_DIR=$(mktemp -d "${TMPDIR:-/tmp}/hl.XXXXXX") || return 1
    mkfifo "$__HL_DIR/out" 2>/dev/null || { rm -rf "$__HL_DIR"; __HL_DIR=; return 1; }
    exec {__HL_W}> >(exec "${TS_PY:?TS_PY is not set}" "${TS_HL:?TS_HL is not set}" > "$__HL_DIR/out")
    exec {__HL_R}<> "$__HL_DIR/out"
    IFS= read -r __hl_ready <&"$__HL_R"          # wait for READY
    return 0
}

__hl_stop() {
    [[ -z ${__HL_DIR:-} ]] && return 0
    exec {__HL_W}>&- 2>/dev/null
    exec {__HL_R}<&- 2>/dev/null
    rm -rf "$__HL_DIR" 2>/dev/null
    __HL_DIR=
}

# The colouriser: a line goes down the pipe and comes back coloured. 158 us warm,
# of which 69 us is the pipe and 45 us the actual work.
__ed_colorize_into() {
    if [[ -z ${__HL_DIR:-} ]]; then
        __COLORED=$1                            # no coprocess, no colour
        return 0
    fi
    printf '%s\n' "$1" >&"$__HL_W" 2>/dev/null || { __COLORED=$1; return 0; }
    IFS= read -r __COLORED <&"$__HL_R" || __COLORED=$1
    return 0
}

# the base loop, but starting the coprocess first
. "${SP_DIR:-$HOME/doc/shell-editor-poc}/editor.sh"

# keep editor.sh's bash -n implementation as the fallback and the tiebreaker
eval "__ed_syntax_status_bash() $(declare -f __ed_syntax_status | tail -n +2)"

# Two-stage completeness gate. This is where the elegance is: the coprocess is
# ALREADY parsing on every keystroke, so asking it whether the text is finished
# costs one pipe round trip, 158 us, and no fork.
#
# tree-sitter cannot fully separate "still typing" from "broken": `echo 'unclosed`
# and `echo )` give the same signature. So when it says `inc` we settle it with
# `bash -n`, which is authoritative but costs 4 ms. That fork only happens on Enter
# and only when the parse is suspicious, which is rare.
__ed_syntax_status() {
    if [[ -z ${__HL_DIR:-} ]]; then
        __ed_syntax_status_bash "$1"; return
    fi
    local q=$1 reply
    q=${q//\\/\\\\}          # escape backslashes
    q=${q//$'\n'/\\n}         # and newlines: the protocol is line-based
    printf '\001%s\n' "$q" >&"$__HL_W" 2>/dev/null || {
        __ed_syntax_status_bash "$1"; return; }
    IFS= read -r reply <&"$__HL_R" || { __ed_syntax_status_bash "$1"; return; }
    case $reply in
        ok)  __ED_STATUS=ok ;;
        err) __ED_STATUS=err ;;
        *)   __ed_syntax_status_bash "$1" ;;   # `inc`: let bash settle it
    esac
}


__repl() {
    __hl_start
    __ed_seed_history
    local line
    while __read_line; do
        line=$__LINE
        [[ -z $line ]] && continue
        history -s "$line"
        eval "$line"
    done
    __hl_stop
}
