export HSTR_CONFIG=hicolor,prompt-bottom

shopt -s histappend

export HISTCONTROL=ignorespace
export HISTFILESIZE=10000
export HISTSIZE=${HISTFILESIZE}

export PROMPT_COMMAND="history -a; history -n; ${PROMPT_COMMAND}"

if [[ $- =~ .*i.* ]]; then bind '"\C-r": "\C-a hstr -- \C-j"'; fi
if [[ $- =~ .*i.* ]]; then bind '"\C-xk": "\C-a hstr -k \C-j"'; fi
