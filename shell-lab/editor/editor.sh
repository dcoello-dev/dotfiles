# Custom line editor. Read loop in bash, readline out of the picture.
#
# Colouring is PLUGGABLE: this file calls `__ed_colorize_into`, which must leave
# the result in $__COLORED. By default that is tokenizer.sh's bash tokenizer;
# editor-treesitter.sh swaps it for the tree-sitter coprocess. There used to be two
# copies of __read_line and every bug had to be fixed twice.
#
# There is also a key hook: if the function `__ed_key_hook` exists it gets every
# key before it is handled. Returning 0 means the key was dealt with and the loop
# moves on. That is what the lab uses for its C-g macros and C-r search, which
# being readline bindings do not exist here.

[ -n "${__ED_TOKENIZER_LOADED:-}" ] || {
    . "${SP_DIR:-$HOME/doc/shell-editor-poc}/tokenizer.sh" 2>/dev/null && __ED_TOKENIZER_LOADED=1
}

# default colouriser: the bash tokenizer
declare -F __ed_colorize_into >/dev/null || __ed_colorize_into() { __colorize "$1"; }

__mini_prompt=$'\033[38;5;118m\xe2\x9e\x9c\033[0m '
declare -a __hist=()
__ed_kill=                 # kill buffer, for C-y
__ED_SEED=                 # text to preload the next line with

# Seed the editor's history from bash's. Without this the up arrow inside the
# editor started empty on every session and only remembered what you typed there,
# which was the most annoying gap against ble.sh.
# `history` is a builtin; the command substitution costs one fork, once.
__ed_seed_history() {
    (( ${#__hist[@]} )) && return 0
    local n=${1:-500} line
    while IFS= read -r line; do
        line=${line#"${line%%[![:space:]]*}"}      # drop indentation
        line=${line#*[0-9] }                        # drop the history number
        line=${line#"${line%%[![:space:]]*}"}
        [[ -n $line ]] && __hist+=("$line")
    done < <(HISTTIMEFORMAT= history "$n" 2>/dev/null)
    return 0
}

# --- is the line finished? ---------------------------------------------------
# Sets __ED_STATUS to ok / inc / err. `inc` means "keep reading".
#
# Default implementation: ask bash, which is the authority on what it will run.
# It costs about 4 ms per check, only on Enter. editor-treesitter.sh overrides this
# with a two-stage gate that makes the fork almost never happen.
__ED_STATUS=ok
__ed_syntax_status() {
    local msg
    msg=$(bash -n <<< "$1" 2>&1)
    if [[ -z $msg ]]; then
        __ED_STATUS=ok
    elif [[ $msg == *"unexpected end of file"*                     \
         || $msg == *"unexpected EOF while looking for matching"*   \
         || $msg == *"delimited by end-of-file"* ]]; then
        __ED_STATUS=inc
    else
        __ED_STATUS=err        # broken for real: run it and let bash say so
    fi
}

__ed_pending=                  # accepted continuation lines
# Default continuation prompt, but respect one already set: the lab sets it before
# this file is sourced so it can carry the (editor) marker.
__ed_ps2="${__ed_ps2:-$'\033[38;5;66m> \033[0m'}"

# __read_line returns 0 with the line in __LINE, 1 on end of input, and 2 when a bare
# Esc asked to hand the line over (see __ed_on_escape); the buffer and cursor are then
# in __ED_HANDOVER_BUF and __ED_HANDOVER_POS.
__ED_HANDOVER_BUF=
__ED_HANDOVER_POS=0

__read_line() {
    local buf=${__ED_SEED:-} pos ch seq c2 cand prompt0=$__mini_prompt hi=${#__hist[@]}
    __ED_SEED=
    pos=${#buf}
    __LINE=
    while true; do
        __ed_colorize_into "$buf"
        printf '\r\033[K%s%s' "$__mini_prompt" "$__COLORED"
        (( ${#buf} - pos > 0 )) && printf '\033[%dD' $(( ${#buf} - pos ))
        IFS= read -rsn1 ch || { printf '\n'; return 1; }

        # hook for whoever integrates this: if it handles the key, move on
        if declare -F __ed_key_hook >/dev/null; then
            if __ed_key_hook "$ch" "$buf" "$pos"; then
                case ${__ED_HOOK_ACTION:-} in
                    # `line`: the hook wants a command run. Nothing is printed
                    # here; the hook owns the display, since it knows whether it
                    # wants to announce the command. A half-typed buffer is saved
                    # and comes back at the next prompt.
                    line)   __LINE=$__ED_HOOK_LINE; __ED_SEED=$buf; return 0 ;;
                    # `buf`: the hook brings text for the line, for instance what a
                    # history picker returned.
                    buf)    buf=$__ED_HOOK_BUF; pos=${#buf}
                            __ED_HOOK_BUF=; continue ;;
                    # `quit`: the hook wants out of the editor, same as C-d but
                    # without needing an empty line.
                    quit)   __ed_pending=; __mini_prompt=$prompt0
                            printf '\n'; return 1 ;;
                    redraw) continue ;;
                    *)      continue ;;
                esac
            fi
        fi

        case $ch in
            $'\n'|'')   # Multiline continuation. If what we have so far is not a
                        # finished command, print the newline, stash the line and
                        # keep reading with a continuation prompt, the way bash
                        # does with its `>`.
                        if [[ -n $__ed_pending ]]; then cand=$__ed_pending$'\n'$buf
                        else cand=$buf; fi
                        if [[ -n $cand ]]; then
                            __ed_syntax_status "$cand"
                            if [[ $__ED_STATUS == inc ]]; then
                                printf '\n'
                                __ed_pending=$cand
                                buf= ; pos=0
                                __mini_prompt=$__ed_ps2
                                continue
                            fi
                        fi
                        printf '\n'; __LINE=$cand
                        [[ -n $cand ]] && __hist+=("$cand")
                        __ed_pending=; __mini_prompt=$prompt0
                        return 0 ;;
            $'\177'|$'\010')                              # Backspace
                        (( pos > 0 )) && { buf=${buf:0:pos-1}${buf:pos}; (( pos-- )); } ;;
            $'\004')    # C-d: exits on an empty line, deletes forward otherwise
                        if [[ -z $buf ]]; then
                            __ed_pending=; __mini_prompt=$prompt0
                            printf '\n'; return 1
                        elif (( pos < ${#buf} )); then buf=${buf:0:pos}${buf:pos+1}; fi ;;
            $'\003')    # C-c also abandons an unfinished continuation
                        buf= pos=0; __ed_pending=; __mini_prompt=$prompt0
                        printf '\n' ;;
            $'\001')    pos=0 ;;                          # C-a
            $'\005')    pos=${#buf} ;;                    # C-e
            $'\002')    (( pos > 0 )) && (( pos-- )) ;;    # C-b
            $'\006')    (( pos < ${#buf} )) && (( pos++ )) ;;  # C-f
            $'\013')    __ed_kill=${buf:pos}; buf=${buf:0:pos} ;;   # C-k
            $'\025')    __ed_kill=${buf:0:pos}; buf=${buf:pos}; pos=0 ;;  # C-u
            $'\027')    __ed_del_word_back ;;             # C-w
            $'\031')    # C-y: paste the last kill
                        buf=${buf:0:pos}$__ed_kill${buf:pos}; (( pos += ${#__ed_kill} )) ;;
            $'\014')    printf '\033[2J\033[H' ;;         # C-l
            $'\020')    (( hi > 0 )) && { (( hi-- )); buf=${__hist[hi]}; pos=${#buf}; } ;;  # C-p
            $'\016')    (( hi < ${#__hist[@]} )) && { (( hi++ )); buf=${__hist[hi]:-}; pos=${#buf}; } ;;  # C-n
            $'\033')    # Escape sequences. Read until the final byte, because they
                        # are not all the same length: \e[D is 2, \e[3~ is 3 and
                        # \e[1;5D is 5. Reading a fixed count left junk in the
                        # stream, which then got inserted as text.
                        #
                        # 0.4 s for the key after ESC. At 0.06 s a person pressing
                        # Esc and then f did not make it in time and the f ended up
                        # inserted. readline uses 0.5 s by default (keyseq-timeout)
                        # for the same reason. A bare ESC does nothing here, so
                        # waiting costs nothing.
                        if ! read -rsn1 -t 0.4 c2; then
                            # A bare Esc. If someone registered `__ed_on_escape` and it
                            # asks for it, hand the line over: that is what makes one
                            # prompt with a vim normal mode behind Esc possible, instead
                            # of separate editor modes you have to remember to switch.
                            if declare -F __ed_on_escape >/dev/null; then
                                __ED_HANDOVER=
                                __ed_on_escape "$buf" "$pos"
                                if [[ -n ${__ED_HANDOVER:-} ]]; then
                                    __ED_HANDOVER_BUF=$buf
                                    __ED_HANDOVER_POS=$pos
                                    __ed_pending=; __mini_prompt=$prompt0
                                    return 2
                                fi
                            fi
                            continue
                        fi
                        if [[ $c2 == '[' || $c2 == 'O' ]]; then
                            seq=$c2
                            while read -rsn1 -t 0.1 c2; do
                                seq+=$c2
                                [[ $c2 == [A-Za-z~] ]] && break
                            done
                        else
                            seq=$c2                                     # Meta key
                        fi
                        case $seq in
                            '[D'|'OD')       (( pos > 0 )) && (( pos-- )) ;;
                            '[C'|'OC')       (( pos < ${#buf} )) && (( pos++ )) ;;
                            '[A'|'OA')       (( hi > 0 )) && { (( hi-- )); buf=${__hist[hi]}; pos=${#buf}; } ;;
                            '[B'|'OB')       (( hi < ${#__hist[@]} )) && { (( hi++ )); buf=${__hist[hi]:-}; pos=${#buf}; } ;;
                            '[H'|'OH'|'[1~') pos=0 ;;
                            '[F'|'OF'|'[4~') pos=${#buf} ;;
                            '[3~')           (( pos < ${#buf} )) && buf=${buf:0:pos}${buf:pos+1} ;;
                            '[1;5D'|'[1;3D'|'b') __ed_word_back ;;
                            '[1;5C'|'[1;3C'|'f') __ed_word_fwd ;;
                            'd')             __ed_del_word_fwd ;;
                            $'\177')         __ed_del_word_back ;;       # Meta-Backspace
                        esac ;;
            $'\t')      __ed_complete ;;
            *)          # Never insert a control character. The default branch used
                        # to drop them into the line as raw bytes: C-w and C-g did
                        # not delete or launch anything, they dirtied the buffer.
                        [[ $ch == [[:cntrl:]] ]] && continue
                        buf=${buf:0:pos}$ch${buf:pos}; (( pos++ )) ;;
        esac
    done
}

# --- word helpers ------------------------------------------------------------
# "Word" = whatever whitespace there is and then the non-whitespace run, like
# readline. Walked character by character rather than with extended patterns, so
# there is no need to turn extglob on in the user's shell.
#
# These read and write `buf` and `pos`, which are locals of __read_line: bash uses
# dynamic scoping, so a function called from there can see them.

__ed_word_start() {                  # index where the word to the left begins
    local i=${1:-$pos}
    while (( i > 0 )) && [[ ${buf:i-1:1} == [[:space:]] ]]; do (( i-- )); done
    while (( i > 0 )) && [[ ${buf:i-1:1} != [[:space:]] ]]; do (( i-- )); done
    printf '%s' "$i"
}
__ed_word_end() {                    # index where the word to the right ends
    local n=${#buf} i=${1:-$pos}
    while (( i < n )) && [[ ${buf:i:1} == [[:space:]] ]]; do (( i++ )); done
    while (( i < n )) && [[ ${buf:i:1} != [[:space:]] ]]; do (( i++ )); done
    printf '%s' "$i"
}
__ed_word_back()     { local i; i=$(__ed_word_start); pos=$i; }
__ed_word_fwd()      { local i; i=$(__ed_word_end);   pos=$i; }
__ed_del_word_back() {
    local i; i=$(__ed_word_start)
    __ed_kill=${buf:i:pos-i}
    buf=${buf:0:i}${buf:pos}
    pos=$i
}
__ed_del_word_fwd() {
    local i; i=$(__ed_word_end)
    __ed_kill=${buf:pos:i-pos}
    buf=${buf:0:pos}${buf:i}
}
__ed_complete() {
    local w=${buf:0:pos} tail=${buf:pos} frag pre m
    frag=${w##* }; pre=${w%"$frag"}
    mapfile -t m < <(compgen -f -- "$frag" 2>/dev/null)
    (( ${#m[@]} == 1 )) && { w=$pre${m[0]}; buf=$w$tail; pos=${#w}; }
}

__repl() {                 # the loop: read, record, run
    local line
    __ed_seed_history
    while __read_line; do
        line=$__LINE
        [[ -z $line ]] && continue
        history -s "$line"
        eval "$line"
    done
}
