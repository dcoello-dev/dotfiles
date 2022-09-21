function set_gcc_version () {
    if [ -z "$1" ]; then
        echo "usage: $0 version" 1>&2
        exit 1
    fi

    if [ ! -f "/usr/bin/gcc-$1" ] || [ ! -f "/usr/bin/g++-$1" ]; then
        echo "no such version gcc/g++ installed" 1>&2
        exit 1
    fi

    update-alternatives --set gcc "/usr/bin/gcc-$1"
    update-alternatives --set g++ "/usr/bin/g++-$1"
}

function enter_dev_env () {
    docker run --rm -it --security-opt apparmor=unconfined --cap-add=sys_nice \
                    --user "$UID:$GID" \
                    --volume="/etc/group:/etc/group:ro" \
                    -e "HOME=/home/$USER" \
                    -e "DISPLAY=$DISPLAY" \
                    --pid=host \
                    --volume="/tmp/.X11-unix:/tmp/.X11-unix" \
                    --volume="/home/$USER:/home/$USER" \
                    --volume="/etc/passwd:/etc/passwd:ro" \
                    --volume="/etc/shadow:/etc/shadow:ro" \
                    --volume="${PWD}:/opt/workspace" \
                    --network host dev /bin/bash
}


function home_net () {
    unset http_proxy
    unset https_proxy  
}

function connect_cluster () {
    case $1 in
    default)
        echo "no server"
        ;;

    esac
}

# Copy file with a progress bar
function cpp() {
	set -e
	strace -q -ewrite cp -- "${1}" "${2}" 2>&1 \
	| awk '{
	count += $NF
	if (count % 10 == 0) {
		percent = count / total_size * 100
		printf "%3d%% [", percent
		for (i=0;i<=percent;i++)
			printf "="
			printf ">"
			for (i=percent;i<100;i++)
				printf " "
				printf "]\r"
			}
		}
	END { print "" }' total_size=$(stat -c '%s' "${1}") count=0
}

function extract () {
   if [ -f $1 ] ; then
       case $1 in
           *.tar.bz2)   tar xvjf $1    ;;
           *.tar.gz)    tar xvzf $1    ;;
           *.bz2)       bunzip2 $1     ;;
           *.rar)       unrar x $1       ;;
           *.gz)        gunzip $1      ;;
           *.tar)       tar xvf $1     ;;
           *.tbz2)      tar xvjf $1    ;;
           *.tgz)       tar xvzf $1    ;;
           *.zip)       unzip $1       ;;
           *.Z)         uncompress $1  ;;
           *.7z)        7z x $1        ;;
           *)           echo "don't know how to extract '$1'..." ;;
       esac
   else
       echo "'$1' is not a valid file!"
   fi
 }

# get current branch in git repo
git_branch() {
    git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/(\1)/'
}

function update_git_config() {
    echo "[user]" > ~/.gitconfig
    echo "	email = davidcoello@eprosima.com" >> ~/.gitconfig

    echo "	name = David Coello Pulido" >> ~/.gitconfig
    echo "[core]" >> ~/.gitconfig
    echo "	editor = micro" >> ~/.gitconfig
    echo "[alias]" >> ~/.gitconfig
    echo "	lg = log --color --pretty=format:'%Cred%h %Cgreen(%cr) %C(bold blue)<%an> %Creset - %s %C(yellow)%d %Creset' --abbrev-commit" >> ~/.gitconfig
    echo "[credential]" >> ~/.gitconfig

    echo "	helper = \"cache\"" >> ~/.gitconfig
}

ros2d() { 
    docker run -it --rm --net=host --cap-add=SYS_PTRACE \
                    --security-opt seccomp=unconfined \
                    --privileged=true \
                    -v /dev:/dev \
                    -v /dev/shm:/dev/shm \
                    -e DISPLAY=$DISPLAY \
                    -v /tmp/.X11-unix:/tmp/.X11-unix \
                    ros:humble; 
}

