# Terminal shell-integration marks (OSC 133).
#
# Windows Terminal understands them: it paints each command as a block, green if
# it succeeded and red if not, shows marks on the scrollbar with
# "showMarksOnScrollbar" and jumps between commands with the "scrollToMark"
# action. It is Warp's blocks idea without changing terminal.
#
# To turn it on in the terminal, in settings.json:
#     "autoMarkPrompts": true, "showMarksOnScrollbar": true
#
# The protocol's four marks:
#   A = prompt starts            B = user input starts
#   C = command output starts    D;<code> = command finished
#
# Switch off with: LAB_OSC133=0
[ "${LAB_OSC133:-1}" = 1 ] || return 0

# Inside tmux the sequence has to be wrapped to get through. Your tmux.conf
# already has `set -gq allow-passthrough on`, which is what allows it.
if [[ -n ${TMUX:-} ]]; then
    __lab_osc()     { printf '\ePtmux;\e\e]133;%s\a\e\\' "$1"; }
    __lab_osc_ps1() { printf '\\[\ePtmux;\e\e]133;%s\a\e\\\\]' "$1"; }
else
    __lab_osc()     { printf '\e]133;%s\a' "$1"; }
    __lab_osc_ps1() { printf '\\[\e]133;%s\a\\]' "$1"; }
fi

# C goes out right before execution, and PS0 is the right place for it because
# PS0 is meant to print.
#
# CAREFUL: PS0 does NOT understand \[ \]. This first reused the PS1 helper, which
# wraps the sequence in \[ \], and bash turned those into the control bytes 0x01
# and 0x02 and spat them out LITERALLY, right in front of whatever each command
# printed. Invisible on screen, but it pollutes any captured output. It showed up
# when dumping the raw pty stream. So PS0 uses the unwrapped sequence.
if [[ -n ${TMUX:-} ]]; then
    PS0=$(printf '\ePtmux;\e\e]133;C\a\e\\')
else
    PS0=$(printf '\e]133;C\a')
fi
