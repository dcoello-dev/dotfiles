# Entry point for the lab. Used as --rcfile.
#
# Loads your real .bashrc, which skips ble.sh when SHELL_LAB=1, then stacks the
# pieces in parts/ in order. That way the lab always inherits your actual setup
# (PATH, aliases, functions, prompt) and only changes what it means to change.

export SHELL_LAB=1
LAB_HOME="${LAB_HOME:-$HOME/shell-lab}"
LAB_VAR="$LAB_HOME/var"
mkdir -p "$LAB_VAR"

# 1. your real config, without ble.sh
[ -r "$HOME/.bashrc" ] && . "$HOME/.bashrc"

# 2. the lab pieces. Each one can be switched off with its variable.
for __p in "$LAB_HOME"/parts/*.bash; do
    [ -r "$__p" ] || continue
    . "$__p"
done
unset __p

# 3. hook everything into the prompt. Must come after the pieces.
__lab_install

# 4. say what is on, or you type `hl` and get a bare 127 with no explanation.
__lab_banner() {
    local on=() off=()
    [ "${LAB_MACROS:-1}"     = 1 ] && on+=(macros)  || off+=(macros)
    [ "${LAB_TIMING:-1}"     = 1 ] && on+=(timing)  || off+=(timing)
    [ "${LAB_OSC133:-1}"     = 1 ] && on+=(marks)   || off+=(marks)
    [ "${LAB_HISTORY:-1}"    = 1 ] && on+=(history) || off+=(history)
    [ "${LAB_HISTSEARCH:-1}" = 1 ] && on+=(search)  || off+=(search)
    [ "${LAB_META:-1}"       = 1 ] && on+=(meta)    || off+=(meta)
    printf '\033[38;5;66mshell-lab\033[0m  no ble.sh  |  on: %s' "${on[*]}"
    [ ${#off[@]} -gt 0 ] && printf '  |  off: %s' "${off[*]}"
    printf '\n'
    printf '\033[38;5;66m          Esc\033[0m vim normal mode   '
    printf '\033[38;5;66mC-r\033[0m history   '
    printf '\033[38;5;66mC-g s\033[0m git macros   '
    printf '\033[38;5;66mexit\033[0m back to your shell\n'
}
[[ $- == *i* ]] && __lab_banner
unset -f __lab_banner

# 5. Drop straight into the editor, so one command gets you everything.
#
# `$-` carries a `c` when bash was given -c, so `lab -c 'command'` must not enter the
# editor: it has one command to run and leave. Checked, `bash -i -c` reports `hiBHc`.
#
# LAB_AUTO_EDITOR=0 starts in readline instead. C-d inside the editor drops you to
# readline without closing the shell, and C-g e brings it back.
if [[ $- == *i* && $- != *c* && "${LAB_AUTO_EDITOR:-1}" = 1 ]]; then
    hl || printf '\033[38;5;66m── starting in readline: the editor did not load.\033[0m\n'
fi
