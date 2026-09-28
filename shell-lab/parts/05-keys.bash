# Key registry for the `hl` line editor.
#
# editor.sh calls `__ed_key_hook` with every key before handling it. This file
# holds the single dispatcher, and the other pieces register their keys in
# __LAB_KEYS. That way two pieces never fight over defining the same hook, and
# adding a key is one line.
#
# A handler receives (key, buffer, position) and says what to do by setting:
#   __ED_HOOK_ACTION=line  + __ED_HOOK_LINE=<command>   run that command
#   __ED_HOOK_ACTION=buf   + __ED_HOOK_BUF=<text>       put that text on the line
#   __ED_HOOK_ACTION=redraw                             just repaint

declare -gA __LAB_KEYS=()

# Chords: a prefix plus a letter that call a FUNCTION rather than running a command.
# `__LAB_MACROS` maps a chord to a command line; this maps one to a handler, for
# things that are not commands, like toggling the editor off.
# Key format is the same: prefix letter plus the key, e.g. `ge` for C-g e.
declare -gA __LAB_CHORDS=()

__ed_key_hook() {
    local ch=$1 fn
    # Enter arrives as an empty string, and an empty subscript on an associative
    # array is an ERROR in bash, not "absent".
    [[ -z $ch ]] && return 1
    fn=${__LAB_KEYS[$ch]:-}
    [[ -z $fn ]] && return 1
    __ED_HOOK_ACTION=redraw
    "$fn" "$ch" "${2:-}" "${3:-}"
    return 0
}
