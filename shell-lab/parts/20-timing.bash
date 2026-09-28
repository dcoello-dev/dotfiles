# How long the last command took, without forking.
#
# Uses $EPOCHREALTIME, a bash 5 internal variable: 14 us per read against
# 1217 us for $(date +%s%N), which spawns a process.
#
# And it uses a DEBUG trap rather than PS0, because PS0 PRINTS the result of the
# expansion. Verified: neither the bare expansion nor one wrapped in \[ \] stays
# quiet, both spit the timestamp onto the screen. The trap prints nothing.
#
# Switch off with: LAB_TIMING=0
[ "${LAB_TIMING:-1}" = 1 ] || return 0

__lab_dur_us=          # duration of the last command, in microseconds
__lab_t0=
__lab_ran=             # 1 if a command actually ran in this cycle

__lab_mark_start() {
    # The DEBUG trap ALSO fires for PROMPT_COMMAND itself, and it fires even when
    # you press Enter on an empty line and nothing runs. Verified by dumping
    # $BASH_COMMAND on every fire: an empty Enter gives two fires, both carrying
    # the name of the PROMPT_COMMAND function; a real command shows up between
    # them.
    #
    # Filtering that is what tells "a command ran" apart from "the prompt just
    # redrew". Without it the history filled with phantom entries carrying
    # invented durations.
    [[ $BASH_COMMAND == '__lab_precmd' ]] && return 0
    __lab_ran=1
    [[ -z ${__lab_t0:-} ]] && __lab_t0=${EPOCHREALTIME/./}
    return 0
}

__lab_timing_end() {
    if [[ -n ${__lab_ran:-} && -n ${__lab_t0:-} ]]; then
        __lab_dur_us=$(( ${EPOCHREALTIME/./} - __lab_t0 ))
        __lab_t0=
    else
        __lab_dur_us=
    fi
}

# Format microseconds into something readable. No forks.
__lab_fmt_dur() {
    local us=${1:-0}
    if   (( us < 1000    )); then printf '%dus' "$us"
    elif (( us < 1000000 )); then printf '%d.%01dms' $(( us/1000 )) $(( (us%1000)/100 ))
    elif (( us < 60000000 )); then printf '%d.%02ds' $(( us/1000000 )) $(( (us%1000000)/10000 ))
    else printf '%dm%02ds' $(( us/60000000 )) $(( (us%60000000)/1000000 ))
    fi
}

# Any readline handler that RUNS a command has to call this when it finishes.
#
# Why: a `bind -x` handler like the C-g macros fires the DEBUG trap, which arms the
# timer, but it never goes through the prompt cycle, so nothing disarms it. The next
# real command then inherited all the time you spent reading the macro's output. It
# showed up as a `true` reporting 11.38s, and in the wild as an 8m38s.
__lab_timer_reset() {
    __lab_t0=
    __lab_ran=
    __lab_dur_us=
}

trap '__lab_mark_start' DEBUG
