function __exe {
    local GREEN="$(tput setaf 118)"
    local CYAN="$(tput setaf 6)"
    str="$*"
    echo -e "\e[1A\e[K"${CYAN}"(auto)➜"${GREEN} $str
    tput init
    eval $str
}

function __ring {
    ( speaker-test -t sine -f 440 >/dev/null )& pid=$! ; sleep 0.4s ; kill -9 $pid
}