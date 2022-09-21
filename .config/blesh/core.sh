function __exe {
    local GREEN="$(tput setaf 118)"
    local CYAN="$(tput setaf 6)"
    str="$*"
    echo -e "\e[1A\e[K"${CYAN}"(auto)➜"${GREEN} $str
    tput init
    eval $str
}