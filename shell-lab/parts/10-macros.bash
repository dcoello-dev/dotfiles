# The macros from ble.sh that actually worked, defined ONCE and served to both
# front ends: readline (via bind -x) and the `hl` line editor (via its key hook).
#
# They used to exist only as readline bindings, so inside `hl` they did nothing.
# Worse: C-g fell through to the editor's default branch and got inserted into
# the line as a raw control byte.
#
# Of the 83 you had declared only 11 were alive; the other 72 called
# ~/.config/subset/subset.py, which does not exist, or missing binaries (amixer
# twice, spt, neovim, gitui). The `C-e x` one was dropped so `end-of-line` keeps
# working: hanging anything off C-e turns it into a prefix.
#
# Switch off with: LAB_MACROS=0
[ "${LAB_MACROS:-1}" = 1 ] || return 0

# key = prefix + letter.  g = C-g,  x = C-x
declare -gA __LAB_MACROS=(
    [gh]='git log --oneline -n10'
    [gs]='git status'
    [ga]='git add --all'
    [gf]='git fetch'
    [gp]='git push -f'
    [gg]='git pull'
    [gc]='git commit -s'
    [gm]='git commit -s --amend'
    [g<]='git rebase --continue'
    [xh]='htop'
)
declare -gA __LAB_PREFIX=( [$'\007']=g [$'\030']=x )   # C-g and C-x

# Same visual notice as ble.sh's __exe
__exe() {
    printf '\n\033[36m(auto)\xe2\x9e\x9c\033[38;5;118m %s\033[0m\n' "$*"
    eval "$*"
    # Disarm the timer: this ran inside a readline handler, outside the prompt cycle,
    # so nothing else will. Without it the next command you type inherits every
    # second you spent reading this output.
    declare -F __lab_timer_reset >/dev/null && __lab_timer_reset
}

# --- front end 1: readline ---
if [[ $- == *i* ]]; then
    for __k in "${!__LAB_MACROS[@]}"; do
        case ${__k:0:1} in
            g) __seq='\C-g' ;;
            x) __seq='\C-x' ;;
            *) continue ;;
        esac
        bind -x "\"${__seq}${__k:1}\": __exe ${__LAB_MACROS[$__k]}" 2>/dev/null
    done
    unset __k __seq
fi

# --- front end 2: the `hl` line editor ---
# Registers with the dispatcher in 05-keys.bash rather than defining the hook,
# which belongs to everyone. C-g and C-x are prefixes: read a second key, look up.
__lab_macro_key() {
    local ch=$1 pfx c key
    pfx=${__LAB_PREFIX[$ch]:-}
    [[ -z $pfx ]] && { __ED_HOOK_ACTION=redraw; return 0; }
    IFS= read -rsn1 -t 2 c || { __ED_HOOK_ACTION=redraw; return 0; }
    key=$pfx$c
    # chords first: they call a function, they are not commands to run
    if [[ -n ${__LAB_CHORDS[$key]:-} ]]; then
        "${__LAB_CHORDS[$key]}"
        return 0
    fi
    if [[ -n ${__LAB_MACROS[$key]:-} ]]; then
        printf '\n\033[36m(auto)\xe2\x9e\x9c\033[38;5;118m %s\033[0m\n' "${__LAB_MACROS[$key]}"
        __ED_HOOK_ACTION=line
        __ED_HOOK_LINE=${__LAB_MACROS[$key]}
    else
        __ED_HOOK_ACTION=redraw       # prefix followed by an unknown key
    fi
    return 0
}
if declare -p __LAB_KEYS >/dev/null 2>&1; then
    __LAB_KEYS[$'\007']=__lab_macro_key      # C-g
    __LAB_KEYS[$'\030']=__lab_macro_key      # C-x
fi
