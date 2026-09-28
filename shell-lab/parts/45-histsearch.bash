# Augmented history search on C-r, for both front ends.
#
# This is not a text search over ~/.bash_history: it queries your database and
# shows, per command, the exit status of the LAST run, how many times you have
# launched it, how many failed, the mean duration and how long ago it was. As you
# move, fzf's preview lists that exact command's latest runs with their status,
# duration and the directory you ran them in.
#
# A real example of why that helps: `git log --oneline -n3` shows up with status
# 128 in the list, and the preview explains it was launched from /tmp.
#
# Uses fzf when present (you have it at /usr/bin/fzf) and falls back to a numbered
# list otherwise. This DISPLACES hstr's shortcut, which was on C-r. hstr is still
# one word away by typing `hstr`, and its C-x k is untouched.
#
# Switch off with: LAB_HISTSEARCH=0
[ "${LAB_HISTSEARCH:-1}" = 1 ] || return 0

LAB_HISTDB="${LAB_HISTDB:-$LAB_HOME/bin/histdb}"

# Run the picker and leave the choice in __LAB_PICKED. Returns 1 if cancelled.
__lab_hist_pick() {
    __LAB_PICKED=
    [ -x "$LAB_HISTDB" ] || return 1
    local sel
    sel=$("$LAB_HISTDB" pick "$@") || return 1
    [[ -z $sel ]] && return 1
    __LAB_PICKED=$sel
    return 0
}

# --- front end 1: readline ---
# bind -x can write to READLINE_LINE and READLINE_POINT, so the chosen command
# lands on the line ready to review before you run it. Unlike hstr, it does not
# execute on its own.
__lab_hist_rl() {
    if __lab_hist_pick; then
        READLINE_LINE=$__LAB_PICKED
        READLINE_POINT=${#READLINE_LINE}
    fi
    # fzf ran inside a readline handler, outside the prompt cycle, so it armed the
    # timer and nothing would disarm it. Browsing history for a minute would then be
    # charged to whatever you ran next.
    declare -F __lab_timer_reset >/dev/null && __lab_timer_reset
}
__lab_hist_rl_here() {
    if __lab_hist_pick --here; then
        READLINE_LINE=$__LAB_PICKED
        READLINE_POINT=${#READLINE_LINE}
    fi
    declare -F __lab_timer_reset >/dev/null && __lab_timer_reset
}

if [[ $- == *i* ]]; then
    bind -x '"\C-r": __lab_hist_rl'      2>/dev/null   # whole history
    bind -x '"\er": __lab_hist_rl_here'  2>/dev/null   # Esc r: this directory only
fi

# --- front end 2: the `hl` line editor ---
__lab_hist_key() {
    if __lab_hist_pick; then
        __ED_HOOK_ACTION=buf
        __ED_HOOK_BUF=$__LAB_PICKED
    else
        __ED_HOOK_ACTION=redraw
    fi
    return 0
}
declare -p __LAB_KEYS >/dev/null 2>&1 && __LAB_KEYS[$'\022']=__lab_hist_key   # C-r
