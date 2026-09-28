# The custom line editor with tree-sitter highlighting: 0.16 ms per keystroke
# against ble.sh's 27.7 ms.
#
#   hl      starts it            C-d     leaves it, back to readline
#
# This file defines `hl` ALWAYS, no variables, no ceremony.
#
# (It used to exist only with LAB_HIGHLIGHT=1, so anyone starting the lab plainly
# typed `hl` and got a bare 127 with no explanation. My bad design.)
#
# Measured: loading this code costs 0 ms, and starting the highlighter coprocess
# 42 ms, paid the first time you type `hl`. So LAB_HIGHLIGHT=1 buys nothing and can
# be ignored; it is kept only for compatibility.
#
# THE PRICE. While the editor is active you lose readline entirely: C-r search via
# hstr, bash's programmable completion (TAB becomes a toy `compgen -f`), multiline
# continuation, bracketed paste. C-d brings them all back.
#
# WHY A CUSTOM EDITOR IS NEEDED. tree-sitter works fine: it returns the coloured
# line in 158 us. The problem is not tinting, it is that readline owns the drawing
# of the line and exposes no hook to colour it. To see colours you must take over
# the redraw, and that means replacing it.

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
__lab_hl_loaded=

__lab_hl_load() {
    [[ -n ${__lab_hl_loaded:-} ]] && return 0
    if [ ! -x "$LAB_POC/venv/bin/python" ] || [ ! -r "$LAB_POC/ts_highlighter.py" ]; then
        echo "hl: cannot find the highlighter prototype at $LAB_POC" >&2
        echo "    check LAB_POC, or rebuild its venv:" >&2
        echo "    python3 -m venv $LAB_POC/venv && $LAB_POC/venv/bin/pip install tree_sitter tree_sitter_bash" >&2
        return 1
    fi
    export TS_PY="$LAB_POC/venv/bin/python"
    export TS_HL="$LAB_POC/ts_highlighter.py"
    export SP_DIR="$LAB_POC"
    . "$LAB_POC/editor-treesitter.sh" || return 1
    __lab_hl_loaded=1
    return 0
}

# Strip OSC sequences from a string: cut from ESC ] to the BEL that closes it.
# Leaves the result in a global rather than printing it, to avoid paying a command
# substitution per prompt.
__LAB_STRIPPED=
__lab_strip_osc() {
    local s=$1 out=
    while [[ $s == *$'\e]'* ]]; do
        out+=${s%%$'\e]'*}
        s=${s#*$'\e]'}
        s=${s#*$'\a'}
    done
    __LAB_STRIPPED=$out$s
}

# The prototype's __repl is its own read loop, so it does NOT go through PS0 or
# PROMPT_COMMAND. As-is, inside the editor the metadata line, the OSC marks and the
# duration were all lost (it logged 11 seconds for a `sleep 0.35`, because the
# timer never started), and it drew a fake prompt. This loop calls the lab hooks by
# hand and gets your real prompt out of ${PS1@P}.
__lab_repl() {
    local line full st=0 rc letter pending= chords prompt
    # Start the highlighter coprocess. The prototype's __repl does this on its first
    # line; writing this loop I forgot, and nothing got coloured, because the pipe
    # writes went to a nonexistent descriptor. The greens that looked like they worked
    # were the prompt arrow, which happens to use the same 118.
    declare -F __hl_start >/dev/null && __hl_start
    # the up arrow must see your real history, not start empty
    declare -F __ed_seed_history >/dev/null && __ed_seed_history 500
    while true; do
        # the PREVIOUS command's metadata, with its exit status intact
        (exit "$st"); __lab_precmd

        # your PS1, expanded to text. The 0x01 and 0x02 markers bash turns \[ \] into
        # are stripped, because here we do the drawing ourselves.
        full=${PS1@P}
        full=${full//$'\x01'/}
        full=${full//$'\x02'/}
        # And out go the OSC sequences: left inside the prompt being redrawn, the
        # terminal receives ten "user input starts here" marks per command. They are
        # emitted by hand, once, just below.
        __lab_strip_osc "$full"; full=$__LAB_STRIPPED
        if [[ $full == *$'\n'* ]]; then
            # multiline prompt: the upper lines print once and only the last one is
            # redrawn on every keystroke.
            printf '%s\n' "${full%$'\n'*}"
            prompt=${full##*$'\n'}
        else
            prompt=$full
        fi
        # Permanent marker, same idea as the (auto) the macros print.
        __mini_prompt=$LAB_EDITOR_TAG$prompt

        # A and B, exactly once per prompt
        if declare -F __lab_osc >/dev/null; then __lab_osc A; __lab_osc B; fi

        __ED_SEED=$pending; pending=
        __read_line; rc=$?
        case $rc in
            0) line=$__LINE ;;
            2)  # A bare Esc: hand the line to nvim in normal mode. This is what makes
                # it one prompt instead of modes you have to switch between.
                chords=
                declare -F __lab_chord_letters >/dev/null && chords=$(__lab_chord_letters)
                __lab_nvline_once "$LAB_NVLINE_TAG$prompt" \
                    "$__ED_HANDOVER_BUF" "$__ED_HANDOVER_POS" "$chords" normal
                case $__LAB_NV_RC in
                    0) line=$__LAB_NV_RAW ;;
                    4)  letter=${__LAB_NV_RAW%%$'\n'*}
                        pending=${__LAB_NV_RAW#*$'\n'}
                        [[ $pending == "$letter" ]] && pending=
                        line=${__LAB_MACROS[g$letter]:-}
                        [[ -z $line ]] && { st=0; continue; }
                        printf '\n\033[36m(auto)\xe2\x9e\x9c\033[38;5;118m %s\033[0m\n' "$line"
                        ;;
                    *)  st=0; continue ;;      # cancelled or handed back
                esac ;;
            *) break ;;                         # end of input
        esac
        [[ -z $line ]] && { st=0; continue; }
        history -s "$line"
        declare -F __lab_osc >/dev/null && __lab_osc C
        # no DEBUG trap applies here: the loop is ours, so both signals are set by hand
        __lab_ran=1
        __lab_t0=${EPOCHREALTIME/./}
        eval "$line"
        st=$?
    done
}

# The marker the prompt carries while the editor is on. Cyan, like the (auto) the
# macros print, so the two read as the same family.
#
# (This and __ed_ps2 were eaten twice by range-based edits that replaced everything
# between two function definitions. Assignments living between functions are exactly
# what that kind of patch loses.)
LAB_EDITOR_TAG="${LAB_EDITOR_TAG:-$'\033[36m(editor)\033[0m'}"

# The continuation prompt carries the marker too, so a `>` never leaves you wondering
# which mode you are in.
__ed_ps2=$LAB_EDITOR_TAG$'\033[38;5;66m> \033[0m'

hl() {
    # Typing `hl` while already inside used to start a NESTED editor: it worked, but
    # then one C-d only dropped you back to the outer one and you needed two to reach
    # readline. Since the editor now starts on its own, that is easy to do by accident.
    if [[ -n ${__lab_in_editor:-} ]]; then
        printf '\033[38;5;66m── already in the editor. C-d or C-g e leaves.\033[0m\n'
        return 0
    fi
    __lab_hl_load || return 1
    printf '\033[38;5;66m── editor on. C-d leaves. no hstr and no TAB subcommands in here.\033[0m\n'
    __lab_in_editor=1
    __lab_repl
    __lab_in_editor=
    printf '\033[38;5;66m── editor off.\033[0m\n'
    if [[ ${__lab_switch_to:-} == nvim ]]; then
        __lab_switch_to=
        declare -F nv >/dev/null && nv
    fi
}

# --- C-g e toggles the editor ------------------------------------------------
# Two sides of the same chord, because entering happens in readline and leaving
# happens inside the editor, which are different worlds.
#
# On the readline side `bind -x` runs `hl` straight from the handler. Verified that
# this works: the editor loop starts nested inside readline's handler, colours, and
# readline comes back alive when it returns.
#
# On the editor side the chord asks the read loop to quit, which is C-d's path
# without needing an empty line first.
__lab_editor_off() { __ED_HOOK_ACTION=quit; }

# C-g v from inside the editor switches to nvim mode. It was only ever bound in
# readline, so pressing it inside the editor did nothing at all and you stayed where
# you were, which read as "it just puts me in editor mode".
__lab_switch_to=
__lab_editor_to_nvim() { __lab_switch_to=nvim; __ED_HOOK_ACTION=quit; }

if [[ $- == *i* ]]; then
    bind -x '"\C-ge": hl' 2>/dev/null
fi
if declare -p __LAB_CHORDS >/dev/null 2>&1; then
    __LAB_CHORDS[ge]=__lab_editor_off
    __LAB_CHORDS[gv]=__lab_editor_to_nvim
fi

[ "${LAB_HIGHLIGHT:-0}" = 1 ] && __lab_hl_load
