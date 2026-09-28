# The 11 live ble.sh macros, in plain readline. No ble.sh involved.
# ble-bind -c 'X' 'cmd'  ==  bind -x '"sequence": cmd'
#
# Kept here as the standalone reference. The lab has a richer version in
# parts/10-macros.bash that serves both readline and the custom editor from one
# table, and that drops the C-e one so `end-of-line` keeps working.
__exe() {
    printf '\n\033[36m(auto)\xe2\x9e\x9c\033[38;5;118m %s\033[0m\n' "$*"
    eval "$*"
}
if [[ $- == *i* ]]; then
    bind -x '"\C-xh": htop'
    bind -x '"\C-ex": exit'
    bind -x '"\C-gh": __exe git log --oneline -n10'
    bind -x '"\C-gs": __exe git status'
    bind -x '"\C-ga": __exe git add --all'
    bind -x '"\C-gf": __exe git fetch'
    bind -x '"\C-gp": __exe git push -f'
    bind -x '"\C-gg": __exe git pull'
    bind -x '"\C-gc": __exe git commit -s'
    bind -x '"\C-gm": __exe git commit -s --amend'
    bind -x '"\C-g<": __exe git rebase --continue'
fi
