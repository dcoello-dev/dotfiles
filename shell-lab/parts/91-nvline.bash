# Editor mode backed by a real nvim, rendered inline on one row.
#
#   nv        start it          C-g v     enter from anywhere
#   C-d       leave, on an empty line     C-c   clear the line
#   C-g e     switch to the other editor (nvline exits with code 3)
#   C-g s etc your git macros, in NORMAL mode. In insert mode C-g is nvim's own
#             prefix and you are typing, so they only bind in normal. The letters come
#             from the same table as everywhere else, and whatever you had half-typed
#             comes back after the macro runs.
#
# nvim's own modal editing, your own keymaps, your own colourscheme. Measured 1.51 ms
# per keystroke with your full config, against ble.sh's 27.7.
#
# How: `nvim --embed` makes stdin/stdout a msgpack-rpc channel; nvline.py calls
# nvim_ui_attach and becomes its UI, painting the single-row grid into the terminal
# past the prompt. Keys go straight through, so nothing about editing is ours.
#
# Switch off with: LAB_NVLINE=0
[ "${LAB_NVLINE:-1}" = 1 ] || return 0

# Where the editor code lives. Prefer a copy sitting next to this lab (which is how the
# dotfiles layout has it), and fall back to the standalone prototype directory. Either
# way LAB_POC in the environment wins.
if [ -z "${LAB_POC:-}" ]; then
    if [ -d "$LAB_HOME/editor" ]; then
        LAB_POC="$LAB_HOME/editor"
    else
        LAB_POC="$HOME/doc/shell-editor-poc"
    fi
fi
LAB_NVLINE_TAG="${LAB_NVLINE_TAG:-$'\033[36m(nvim)\033[0m'}"

__lab_nvline_ok() {
    [ -x "$LAB_POC/venv/bin/python" ] && [ -r "$LAB_POC/nvline.py" ] \
        && command -v nvim >/dev/null 2>&1
}

__lab_in_nvline=

nv() {
    if [[ -n ${__lab_in_nvline:-} ]]; then
        printf '\033[38;5;66m── already in nvim mode. C-d or C-g v leaves.\033[0m\n'
        return 0
    fi
    if ! __lab_nvline_ok; then
        echo "nv: need nvim plus $LAB_POC/nvline.py and its venv" >&2
        return 1
    fi
    printf '\033[38;5;66m── nvim mode. C-d on an empty line leaves. '
    printf 'readline is off in here.\033[0m\n'
    __lab_in_nvline=1
    __lab_nvline_repl
    __lab_in_nvline=
    printf '\033[38;5;66m── nvim mode off.\033[0m\n'
    if [[ ${__lab_switch_to:-} == editor ]]; then
        __lab_switch_to=
        declare -F hl >/dev/null && hl
    fi
}

__lab_nvline_repl() {
    local line st=0 full prompt rc raw letter pending= chords=
    while true; do
        # the previous command's metadata, with its exit status intact
        (exit "$st"); __lab_precmd

        # your PS1 as text, markers and OSC stripped, upper lines printed once
        full=${PS1@P}
        full=${full//$'\x01'/}
        full=${full//$'\x02'/}
        declare -F __lab_strip_osc >/dev/null && { __lab_strip_osc "$full"; full=$__LAB_STRIPPED; }
        if [[ $full == *$'\n'* ]]; then
            printf '%s\n' "${full%$'\n'*}"
            prompt=${full##*$'\n'}
        else
            prompt=$full
        fi
        prompt=$LAB_NVLINE_TAG$prompt

        if declare -F __lab_osc >/dev/null; then __lab_osc A; __lab_osc B; fi

        # The C-g letters come from the one macro table, so adding a macro in
        # 10-macros.bash makes it work here too with no change.
        chords=
        for k in "${!__LAB_MACROS[@]}"; do
            [[ ${k:0:1} == g ]] && chords+=${k:1}
        done

        # nvline draws on /dev/tty and prints the finished command on stdout, the way
        # fzf does, so a command substitution is the whole interface.
        raw=$("$LAB_POC/venv/bin/python" "$LAB_POC/nvline.py" \
                 --prompt "$prompt" --cols "${COLUMNS:-80}" \
                 --chords "$chords" --initial "$pending")
        rc=$?
        pending=
        case $rc in
            0) line=$raw ;;               # run it
            1) st=0; continue ;;          # cancelled, new prompt
            3) __lab_switch_to=editor; break ;;   # C-g e: the other editor
            4)  # a C-g chord fired: first line the letter, the rest what was typed
                letter=${raw%%$'\n'*}
                pending=${raw#*$'\n'}
                [[ $pending == "$letter" ]] && pending=
                line=${__LAB_MACROS[g$letter]:-}
                [[ -z $line ]] && { st=0; continue; }
                printf '\n\033[36m(auto)\xe2\x9e\x9c\033[38;5;118m %s\033[0m\n' "$line"
                ;;
            *) break ;;                   # end of input
        esac
        [[ -z $line ]] && { st=0; continue; }
        history -s "$line"
        declare -F __lab_osc >/dev/null && __lab_osc C
        __lab_ran=1
        __lab_t0=${EPOCHREALTIME/./}
        eval "$line"
        st=$?
    done
}

__lab_nvline_off() { __ED_HOOK_ACTION=quit; }

if [[ $- == *i* ]]; then
    bind -x '"\C-gv": nv' 2>/dev/null
fi
