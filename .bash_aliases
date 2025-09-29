echo "Source .bash_aliases"

# There could be some aliases here but don't preserve other variables
source ${HOME}/.bash_secret;
source ${HOME}/.bash_unsecret;

# General helps
alias ls="ls --color=auto";
alias i3class="xprop | grep WM_CLASS | awk '{ print \$4 }'";
alias trackpad="${HOME}/./toggle_trackpad.sh";
alias notes="pushd ${HOME}/Documents/Obsidian/Graduate && git pull && popd && pushd ${HOME}/Documents/Obsidian/Personal && git pull && popd";
alias resource="source ~/.bashrc";
alias actualbudget="flatpak run com.actualbudget.actual";
alias heroic="flatpak run com.heroicgameslauncher.hgl";
# Improved screenshot goes to clipboard AND os
screenshot() {
    local PICTURE="${HOME}/Pictures/Screenshots/$(date).png";
    maim $@ "${PICTURE}" && xclip -selection clipboard -t image/png -i "${PICTURE}";
}

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
