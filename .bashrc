# source besh
source "$HOME/.local/share/blesh/ble.sh" --rcfile "$HOME/.config/blesh/.blerc"

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# make less more friendly for non-text input files, see lesspipe(1)
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# Color for manpages in less makes manpages a little easier to read
export LESS_TERMCAP_mb=$'\E[01;31m'
export LESS_TERMCAP_md=$'\E[01;31m'
export LESS_TERMCAP_me=$'\E[0m'
export LESS_TERMCAP_se=$'\E[0m'
export LESS_TERMCAP_so=$'\E[01;44;33m'
export LESS_TERMCAP_ue=$'\E[0m'
export LESS_TERMCAP_us=$'\E[01;32m'


# colored GCC warnings and errors
export GCC_COLORS='error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01'

# enable programmable completion features (you don't need to enable
# this, if it's already enabled in /etc/bash.bashrc and /etc/profile
# sources /etc/bash.bashrc).
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

# Source goto
[[ -s "/usr/local/share/goto.sh" ]] && source /usr/local/share/goto.sh

# Source all auxiliary config bash files
for f in ~/.config/bash/.bash_*; do source $f; done

export EDITOR=micro

update_git_config

# Write the following line at the bottom of .bashrc
[[ ${BLE_VERSION-} ]] && ble-attach


function config_screens () {
	xrandr --output HDMI-1 --auto --right-of eDP-1
 	xrandr --output DP-2 --auto --right-of HDMI-1
}

function copyq_history () {
    green=$(tput setaf 2)
    normal=$(tput sgr0)

    for n in {0..9}; do
	echo -e -n "\n${green}${n}:${normal} "
	copyq read "$n" | head -1 | tr -d '\n' | tr -d '\t' | cut -c 1-141
	echo
    done | sed '/^$/d'

    read -p "Select item: " i

    copyq select "$i"
}

export HISTSIZE=1000
export HISTFILESIZE=2000
export HISTCONTROL=ignoredups:erasedups

# Guardar el historial después de cada comando
shopt -s histappend
