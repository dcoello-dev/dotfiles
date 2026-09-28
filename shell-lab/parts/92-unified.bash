# One prompt, with vim's normal mode behind Esc.
#
# The idea: you are always in the fast editor, with highlighting, your C-g macros, the
# C-r history search and multiline continuation. Press **Esc** and the line is handed to
# a real nvim in normal mode, where you yank, move, delete words, and everything else.
# From there `i` and friends type in nvim, and Enter runs the line either way.
#
# So there is nothing to switch and nothing to remember. `C-g v` and `nv` are still
# there if you want to start inside nvim.
#
# Switch off with: LAB_ESC_TO_NVIM=0
[ "${LAB_ESC_TO_NVIM:-1}" = 1 ] || return 0
declare -F __lab_nvline_ok >/dev/null || return 0
__lab_nvline_ok || return 0

# editor.sh asks this on a bare Esc. Saying yes makes __read_line return 2.
__ed_on_escape() {
    __ED_HANDOVER=1
}

# One nvline invocation. Leaves the exit code in __LAB_NV_RC and stdout in __LAB_NV_RAW,
# so the callers do not each reimplement the call and its five exit codes.
__lab_nvline_once() {
    local prompt=$1 initial=$2 cursor=$3 chords=$4 extra=()
    [[ -n $initial ]] && extra+=(--initial "$initial")
    [[ -n $cursor ]] && extra+=(--cursor "$cursor")
    [[ $5 == normal ]] && extra+=(--start-normal)
    __LAB_NV_RAW=$("$LAB_POC/venv/bin/python" "$LAB_POC/nvline.py" \
        --prompt "$prompt" --cols "${COLUMNS:-80}" --chords "$chords" "${extra[@]}")
    __LAB_NV_RC=$?
}

# The letters for the C-g chords, from the one macro table.
__lab_chord_letters() {
    local k out=
    for k in "${!__LAB_MACROS[@]}"; do
        [[ ${k:0:1} == g ]] && out+=${k:1}
    done
    printf '%s' "$out"
}
