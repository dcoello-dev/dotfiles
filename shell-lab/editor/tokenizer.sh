# Bash-only tokenizer and colouriser. No subshells.
#
# Five categories: valid command, unknown command, string, variable, operator.
# Command existence is cached in an associative array.
#
# This is the dependency-free colouriser. It is less accurate and scales worse
# than the tree-sitter coprocess: at 432 characters it is 10x slower, and it gets
# escaped quotes and commands after `do` wrong. See README.md.

declare -A __cmd_cache=()
__is_cmd() {
    local w=$1
    [[ -z $w ]] && return 1
    if [[ -n ${__cmd_cache[$w]+x} ]]; then return "${__cmd_cache[$w]}"; fi
    # `$(type -t ...)` would be a command substitution, i.e. a fork per keystroke.
    # `type -t x >/dev/null` gives the same yes/no without forking.
    if type -P "$w" >/dev/null 2>&1 || type -t "$w" >/dev/null 2>&1
    then __cmd_cache[$w]=0; return 0
    else __cmd_cache[$w]=1; return 1; fi
}

__COLORED=
__colorize() {
    # CAREFUL: bash expands ALL arguments of `local` before assigning them, so
    # `n=${#line}` in the same statement would read the OUTER scope's `line`, not
    # the one just assigned. It came out 0, the colouriser did nothing and I spent
    # a while benchmarking a no-op. Hence two statements.
    local line=$1
    local out= tok ch state=cmd q= i=0 n
    n=${#line}
    local C_CMD=$'\033[38;5;118m' C_BAD=$'\033[38;5;197m' C_STR=$'\033[38;5;70m'
    local C_VAR=$'\033[38;5;208m' C_OP=$'\033[38;5;37m'  C_OFF=$'\033[0m'
    while (( i < n )); do
        ch=${line:i:1}
        if [[ -z $q && ( $ch == "'" || $ch == '"' ) ]]; then
            q=$ch; out+=$C_STR$ch; ((i++)); continue
        fi
        if [[ -n $q ]]; then
            out+=$ch; [[ $ch == "$q" ]] && { q=; out+=$C_OFF; }
            ((i++)); continue
        fi
        case $ch in
            '$') tok=${line:i}; tok=${tok%%[^a-zA-Z0-9_$]*}
                 [[ -z $tok ]] && tok=$ch
                 out+=$C_VAR$tok$C_OFF; (( i += ${#tok} )); continue ;;
            '|'|'&'|';'|'>'|'<') out+=$C_OP$ch$C_OFF; state=cmd; ((i++)); continue ;;
            ' ') out+=$ch; ((i++)); continue ;;
        esac
        if [[ $state == cmd ]]; then
            tok=${line:i}; tok=${tok%%[ $'\t'|\&\;\<\>]*}
            if [[ -n $tok ]]; then
                if __is_cmd "$tok"; then out+=$C_CMD$tok$C_OFF; else out+=$C_BAD$tok$C_OFF; fi
                (( i += ${#tok} )); state=arg; continue
            fi
        fi
        out+=$ch; ((i++))
    done
    __COLORED=$out
}
__redraw() { __colorize "$1"; printf '\r\033[K%s%s' "$__mini_prompt" "$__COLORED"; }
