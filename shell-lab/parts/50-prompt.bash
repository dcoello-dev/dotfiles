# Composes everything with your prompt, without replacing it.
#
# Your __setprompt stays exactly as it was: the table that turns 127 into
# "Command not found" is yours, not ble.sh's, so nothing is lost. This piece only
# adds a metadata line ABOVE the prompt.
#
# Above and not inline on purpose: ghost text to the right of the cursor requires
# owning the redraw, i.e. owning the line editor. A line printed before the prompt
# does not fight readline at all.
#
# Switch the line off with: LAB_META=0
# Threshold for showing the duration: LAB_DUR_MIN_US (default 200000 = 200 ms)

LAB_DUR_MIN_US="${LAB_DUR_MIN_US:-200000}"

__lab_meta_line() {
    [ "${LAB_META:-1}" = 1 ] || return 0
    local st=$1 dur=$2 out=
    if [[ -n $dur ]] && (( dur >= LAB_DUR_MIN_US )); then
        out+=$'\033[38;5;66m'"$(__lab_fmt_dur "$dur")"$'\033[0m'
    fi
    if (( st != 0 )); then
        [[ -n $out ]] && out+='  '
        out+=$'\033[38;5;197m'"exit $st"$'\033[0m'
    fi
    [[ -z $out ]] && return 0
    printf '\033[38;5;66m\xe2\x95\xb0\xe2\x94\x80\033[0m %s\n' "$out"
}

# Called from lab.bash at the end, once every piece is loaded.
__lab_install() {
    __lab_precmd() {
        local st=$?
        declare -F __lab_timing_end >/dev/null && __lab_timing_end
        declare -F __lab_osc        >/dev/null && __lab_osc "D;$st"
        declare -F __lab_record     >/dev/null && __lab_record "$st" "${__lab_dur_us:-}"
        __lab_meta_line "$st" "${__lab_dur_us:-}"
        # put $? back to its original value before your prompt reads it
        (exit "$st")
        declare -F __setprompt >/dev/null && __setprompt
        # wrap the freshly built PS1 with the prompt-start marks
        if declare -F __lab_osc_ps1 >/dev/null; then
            PS1="$(__lab_osc_ps1 A)${PS1}$(__lab_osc_ps1 B)"
        fi
        # close the cycle: whatever comes now is a new command, and the timer must
        # start from scratch
        __lab_ran=
        __lab_t0=
    }
    PROMPT_COMMAND=__lab_precmd
}
