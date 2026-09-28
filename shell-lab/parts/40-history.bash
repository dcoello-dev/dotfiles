# Your own history with metadata. Zero external tools.
#
# The hot path is a single `printf >>` to a text file: no sqlite at the prompt, no
# extra processes. Records are imported into SQLite only when you query, with
# `histdb`, which uses python3's standard-library sqlite3 module (there is no
# sqlite3 CLI on this machine, but the module is there).
#
# Tab-separated format:
#   unix_time  status  duration_us  directory  session  command
#
# In the command only backslash, tab and newline are escaped, with two parameter
# substitutions and no processes. Unambiguously reversible. (%q looks tempting but
# produces shell quoting and $'...' forms that Python does not reverse reliably.)
#
# Switch off with: LAB_HISTORY=0
[ "${LAB_HISTORY:-1}" = 1 ] || return 0

LAB_HISTFILE="${LAB_HISTFILE:-$LAB_VAR/history.tsv}"
# Session id: pid plus start instant. No forks.
LAB_SESSION="${LAB_SESSION:-$$-${EPOCHSECONDS:-0}}"
export LAB_SESSION

__lab_first_prompt=1

__lab_record() {
    local st=$1 dur=$2 line cmd
    # Without this guard, phantom entries got recorded: on an empty Enter and on
    # returning from the `hl` editor, `history 1` still yields the last command
    # and it was logged again with an invented duration.
    # $HISTCMD is no use here: it does not advance inside our own read loop.
    [[ -n ${__lab_ran:-} ]] || return 0
    # On the session's first prompt, `history 1` returns the last line of the
    # history file, i.e. the last command of the PREVIOUS session. Recording it
    # would be a lie, so that prompt is skipped.
    if [[ -n ${__lab_first_prompt:-} ]]; then
        __lab_first_prompt=
        return 0
    fi
    # `history 1` is the only reliable way to recover the whole line as you typed
    # it, pipelines included. It costs one process, once per command executed,
    # not per keystroke.
    line=$(HISTTIMEFORMAT= history 1) || return 0
    cmd=${line#*[0-9]  }          # drop the history number
    cmd=${cmd#"${cmd%%[![:space:]]*}"}
    [[ -z $cmd ]] && return 0
    cmd=${cmd//\\/\\\\}; cmd=${cmd//$'\t'/\\t}; cmd=${cmd//$'\n'/\\n}
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
        "${EPOCHSECONDS:-0}" "$st" "${dur:-0}" "$PWD" "$LAB_SESSION" "$cmd" \
        >> "$LAB_HISTFILE"
}
