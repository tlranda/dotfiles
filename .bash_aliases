echo "Source .bash_aliases"

# There could be some aliases here but don't preserve other variables
source ${HOME}/.bash_secret;
source ${HOME}/.bash_unsecret;

# General helps
alias i3class="xprop | grep WM_CLASS | awk '{ print \$4 }'";
alias trackpad="${HOME}/./toggle_trackpad.sh";
alias notes="pushd ${HOME}/Documents/Obsidian/Graduate && git pull && popd && pushd ${HOME}/Documents/Obsidian/Personal && git pull && popd";
alias resource="source ~/.bashrc";

# Improved screenshot goes to clipboard AND os
screenshot() {
    local PICTURE="${HOME}/Pictures/Screenshots/$(date).png";
    maim $@ "${PICTURE}" && xclip -selection clipboard -t image/png -i "${PICTURE}";
}

# Basic access to Steam library without running the windowed application
list-steam-games() {
    find ~/snap/steam/common/.local/share/Steam/steamapps/ -name "*.acf" -exec \
        awk -F '"' '/"appid|name/{ printf $4 "|" } END { print "" }' {} \;
}
find-steam-game() {
    if [[ $# -ne 1 ]]; then
        echo "USAGE: find-steam-game <grep-able part of name (case INsensitive)>";
        return;
    fi;
    list-steam-games | column -t -s '|' | sort -k 2 | grep -i "$1";
}
launch-steam-game() {
    if [[ $# -ne 1 ]]; then
        echo "USAGE: launch-steam-game <grep-able part of name (case IN sensitive)>";
        return;
    fi;
    game_match=`find-steam-game "$1"`;
    n_games=`echo -e "$game_match" | wc -l`;
    if [[ ${n_games} -eq 0 ]]; then
        echo "Could not find your game. Available games:";
        list-steam-games;
    else if [[ ${n_games} -gt 1 ]]; then
        echo "Ambiguous response (found ${n_games} games). Please narrow down between these options:";
        echo "${game_match}";
    else
        echo "Found your game: $game_match";
        game_id=`echo "${game_match}" | awk '{ print $1 }'`;
        echo "ID: ${game_id}";
        steam -applaunch ${game_id};
    fi;
    fi;
}

# Basic access to Flatpak library similar to Steam above
list-flatpak-apps() {
    flatpak list | tail -n +1 | awk '{print "|" $1 "|" $2 "|"}' | grep -E "\|((com)|(org))\.";
}
find-flatpak-app() {
    if [[ $# -ne 1 ]]; then
        echo "USAGE: find-flatpak-app <grep-able part of name (case INsensitive)>";
        return;
    fi;
    list-flatpak-apps | column -t -s '|' | sort -k 2 | grep -i "$1";
}
launch-flatpak-app() {
    if [[ $# -ne 1 ]]; then
        echo "USAGE: launch-flatpak-app <grep-able part of name (case IN sensitive)>";
        return;
    fi;
    app_match=`find-flatpak-app "$1"`;
    n_apps=`echo -e "$app_match" | wc -l`;
    if [[ ${n_apps} -eq 0 ]]; then
        echo "Could not find your app. Available apps:";
        list-flatpak-apps;
    else if [[ ${n_apps} -gt 1 ]]; then
        echo "Ambiguous response (found ${n_apps} apps). Please narrow down between these options:";
        echo "${app_match}";
    else
        echo "Found your app: ${app_match}";
        app_id=`echo "${app_match}" | awk '{ print $2 }'`;
        echo "ID: ${app_id}";
        flatpak run $app_id;
    fi;
    fi;
}
alias actualbudget="flatpak run com.actualbudget.actual";
alias heroic="flatpak run com.heroicgameslauncher.hgl";

# Common typos for builtins
sl() {
    ls ${@};
}

# SSH tweaks
alias ssh-find="pgrep -fu ${USER} \"ssh-agent\"";
ssh-killagent() {
    for pid in `ssh-find`; do
        kill ${pid};
    done;
}
ssh-startagent() {
    echo "Init new SSH agent";
    ssh-agent > "${SSH_ENV}"; #| sed 's/^echo/#echo/' > "${SSH_ENV}"; # Silences startup name
    chmod 600 "${SSH_ENV}";
    source "${SSH_ENV}"; # > /dev/null; # Silences startup name
    #ssh-find;
}
ssh-reconnect() {
    source "${SSH_ENV}" > /dev/null;
    ps -ef | grep "${SSH_AGENT_PID}" | grep ssh-agent$ > /dev/null || {
        ssh-startagent;
    };
}
ssh-auth() {
    agent_pid=$(ssh-find);
    source ${HOME}/.bash_secret;
    default_key=${secret_default_key};
    source ${HOME}/.bash_unsecret;
    if [[ $# -gt 0 ]]; then
        desired_key="${1}";
    else
        desired_key="${default_key}";
    fi
    echo "SSH-Auth: Agent pid = '${agent_pid}', desired key = '${desired_key}'";

    if [[ -n "${agent_pid}" ]]; then
        # Agent is already running, check if desired key is loaded
        ssh-reconnect;
        loaded_keys=$(ssh-add -L);
        if echo "${loaded_keys}" | grep -q "$(< ${desired_key}.pub)" ; then
            echo "SSH agent exists and is already running ${desired_key} for you";
            return;
        else
            echo "Adding ${desired_key} to existing SSH-agent";
        fi
    else
        # No agent running; make one and add the key
        echo "Starting new SSH agent with key ${desired_key}";
        ssh-startagent;
    fi
    ssh-add ${desired_key};
}

who-is-on() {
    who | awk '{uname[$1] = uname[$1] + 1} END {for(name in uname) print "[" name " has " uname[name] "x active logins]"}';
}

folder-usage() {
    du -sh ${1}/* | gawk '{
        nf = split($0, a, /[KGM]/, seps)
        for (i = 1; i < nf; ++i) {
            if (seps[i] == "K") {
                printf "B%s %s", seps[i], a[i]
            }
            else if(seps[i] == "G" || seps[i] == "M") {
                printf "A%s %s", seps[i], a[i]
            }
            else {
                printf "%s\n", a[i]
            }
        }
    }' #|
        #sort -k1,1 -k2,2n -r #|
        #sed -e 's/BK/K/g' -e 's/AM/M/g' -e 's/AG/G/g' #-e 's/^K//' -e 's/^M//' -e 's/^G//'
}
