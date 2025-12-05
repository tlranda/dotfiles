# System Configuration / Software Listing

Should make my environment easier to fully/partially port between machines.
Your Mileage May Vary from following any instructions here -- I'm not
responsible for any actions you take on your computer. Read the files before
using/running them. For more legalese version of this disclaimer, see the
[license](LICENSE).

# Initialization

Merge each file (prefixed with `.`) or directory with your existing installation
at `$HOME`. (Ie: directories under .config/ should be linked, but files to handle
`$HOME` such as .bashrc can be symlinked into the home directory). You may need
to install some/all software in subsequent steps before copying in all
of the available configurations in this repository.

Note: Your .gitconfig and the pair of .bash\_secret + .bash\_unsecret files
should NOT be linked, as they can leak sensitive information. They're
included in .gitignore to help with not committing changes to them.
You'll need to update both of these files, the rest should run out-of-the-box
without extra modification once all relevant software is installed.

I recommend making a cross-user group (sudo groupadd dotusers) and adding all
human users to the group (sudo usermod -a -G dotusers ${USER}) so that you can
make these files cross-user available easily.
Ie:

sudo mkdir /dotfiles;
sudo chgrp -R dotusers /dotfiles;
sudo chmod -R 2775 /dotfiles;

Then each user can link to/from /dotfiles transparently and updates should be
shared across all users without file duplication etc.

# Programs to Install / Configure

## Via Package-Manager

### Vim

Generally comes pre-installed, but for plugins to use with my .vimrc (included),
you'll need to install VimPlugged:

1) curl -fLo ~/.vim/autoload/plug.vim --create-dirs https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
2) Open any buffer with vim and run the command (ie: from normal mode ':' to enter command mode) "PlugInstall"

### Flatpak

1) sudo apt install flatpak
2) sudo apt install gnome-software-plugin-flatpak
3) flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

Now you can `flatpak install ${NAME}.flatpak` for applications distributed in that manner.

### Piper

Allows configuring mouse RBG etc on Linux

1) sudo apt install piper
2) piper
3) Under the LEDs tab, you can disable them now! Profile should load upon login but might not remain loaded if you log out (ie: idling while logged out or during boot -- most mice will turn off LEDs if logged out AND the system is sleeping)

### OpenSSH

Allows connecting to the device over SSH

1) Package manager install openssh-server
2) sudo service ssh start
3) sudo systemctl enable ssh

If connection times out, probably firewall related:
1) sudo ufw allow ssh
2) sudo ufw enable

### Ruby

Part of Jekyll builds for websites

1) sudo apt install ruby ruby-dev
2) Within website directory: sudo bundle install
* If step 2 fails: sudo bundle add webrick
* If this fails, delete webrick from the Gemfile, uninstall your bundle and reinstall it (sudo bundle clean --force; sudo bundle install; sudo bundle add webrick)
3) Serve website: bundle exec jekyll serve (should open on localhost:4000)

### Fastfetch

Fancy way to show off system configuration

1) Package manager install fastfetch
2) Copy .config/fastfetch files into ${HOME}/.config/fastfetch
3) fastfetch and enjoy!

### i3

Customizable window manager

1) Link .config/i3 files into ${HOME}/.config/i3 after basic setup is present
2) Ensure you have installed Python3 and the i3ipc package for python scripts to work

### dunst

Customizable notification manager

1) Link .dunstrc under ${HOME}/.config/dunst as "dunstrc" (no leading dot)
2) Restart dunst (restarting i3 should do, or killall dunst && dunst &)

## Via External

### OBS (Flatpak)

#### Set up i3 workspace follower

See instructions under [obs-scripting/README.md](obs-scripting/README.mD)

While this may technically work with the snap-installable version, snap is very
restrictive / difficult to work with for scripting by comparison.

#### Set up replay buffer

1) Set up the scene
  + Add a scene if necessary. I call mine "i3FollowerScene" per instructions for i3 workspace following
  + Add at least one source (preferablly display capture) to the scene.

2) Adjust the settings (button at the bottom of the rightmost menu pane)
  + Output pane
    + Recording/Recording Path: Update to where you want the videos to be saved
    + Recording/Recording Format: I prefer MPEG-4 (.mp4)
    + Replay Buffer: Enable the replay buffer
    + Replay Buffer/Maximum Replay Time: I set this to 240 seconds (4 minutes)
    + Replay Buffer/Maximum Memory: I set this to 4096 MB (4GB)
  + Hotkeys pane
    + Super+Control+Shift+S : Save replay buffer (Makes the clip)
    + Super+Control+Shift+A : Start replay buffer (Enable clipping)
    + Super+Control+Shift+Z : Stop replay buffer (Disable clipping)
  + Advanced pane
    + Hotkeys/Hotkey Focus Behavior: Never disable hotkeys


### Firefox

1) [Install Firefox on your system if it isn't already installed](https://www.firefox.com/en-US/)
2) Login to Firefox Sync for passwords, extensions, etc
3) Configure extensions (usually opening them once is enough to sync settings)

### Lutris

NOTE: Set this up AFTER configuring Steam

0) Install wine from your package manager. Lutris can install other wine versions itself, but the default one is often more stable to get things off the ground.
  + You may need to add 32-bit support to your package manager for 32-bit support (dpkg --add-architecture i386)
  + Also install winetricks to go along with things that require "Mono" etc
1) [Download lutris from the web](lutris.net/downloads)
2) Run your package manager to install locally (some package managers can handle the download for you).
3) Connect to Steam and retrieve games. If you fail to retrieve games, it may be because your steam profile is private.
4) Connect to Epic and retrieve games.

### Heroic

NOTE: Set this up AFTER configuring flatpak

1) Install via flatpak from their website
2) Log in on EGS/GOG/Prime accounts
3) Install/manage/play games

### Sunshine

1) [Download latest GitHub release](https://github.com/LizardByte/Sunshine/releases)
2) Add packages as needed (`apt-get install miniupnpc libminiupnpc17`)
  + https://github.com/unicode-org/icu/releases/tag/release-70-1
  + May have to manually toss these files into their respective directories in /usr/local
  + sudo ldconfig to reload cache
3) Install `sudo dpkg -i <sunshine*.deb>`
4) Visit localhost:47990 in your browser to configure your username and password. Save them! I don't recommend punching a hole into the firewall for this, but you can.
5) You should be able to log in to the proper portal for Sunshine now and set up client connections

### TagStudio

1) Fetch the [latest release from GitHub](https://github.com/TagStudioDev/TagStudio/releases)
2) Unzip the tarfile and run the client
* You may need to install ffmpeg
* Optional: It seems that TagStudio can use `ripgrep` for faster indexing if you install it.
4) I configure the settings (File-\>Settings) to disable opening library on start and use date format YYYY-MM-DD
5) Move the entire install folder into ${HOME}/.local/bin (it needs to have its "\_internal" folder moved with it, then link it for accessibility (ln -s tagstudio\_install/tagstudio tagstudio)

### Actual Budget

1) Grab the flatpak installer from [the actual budget website](https://actualbudget.org/download)
2) flatpak install Actual-linux-x86_64.flatpak
3) You may need to look up where the executable is (flatpak info --show-location com.actualbudget.actual) and then run it
4) Set up the server on localhost with a port of your choice (default 5007)
* Make sure the port is permitted in the ufw firewall
5) Configure or import your data

### Ollama

For LLMs running locally

1) Fetch your local installer from [the website](https://ollama.com/download)
2) Ensure that 11434/tcp has a hole in UFW firewall (if applicable)
3) For AMDGPU support in Ollama, you will need to [download the AMD Linux drivers](https://www.amd.com/en/support/download/linux-drivers.html) and set up the [AMDGPU-Install](https://amdgpu-install.readthedocs.io/en/latest/install-overview.html) script on your machine. This will involve one reboot.
4) Assuming you continue to run ollama via the service, you may need to root-edit the /etc/systemd/system/ollama.service to add new "Environment=" lines to pass in various overrides and settings (if the system cannot detect them properly -- you'll see the errors/suggestions in the journalctl entries by following it and restarting the service)
5) Per expectations, small LLMs that fit on a single GPU can return results in tractable/useful time but are lobotomized child levels of intellect. Larger models are more intelligent but may be unable to run on GPU or just run very very slowly.

### AnythingLLM

For easier access to text-embedding and RAG. Note that at the last time of inspection, AnythingLLM can ONLY embed documents of the following filetypes: txt,md,docx,pdf, py,js,html,css, csv,json.

1) Download the installer as instructed on [the website](https://anythingllm.com/desktop)
2) You may need to `sudo chown root:root anythingllm-desktop/chrome-sandbox; sudo chmod 4755 anythingllm-desktop/chrome-sandbox` for Ubuntu's sandboxing rules to permit the app to run.
3) Connect AnythingLLM to your local LLM runner (I used Ollama, you can install other tools it indicates support for if you please)

### CopyParty

For filesharing locally

1) Download the copyparty python file [from the GitHub releases](https://github.com/9001/copyparty/)
2) Place it in your desired directory (ie: /mnt/Shareable)
3) Set up a copyparty config similar to the following:
```
# File: ~/.config/copyparty/my\_party\_config.conf

# not actually YAML but pretend for syntax highlighting
# -*- mode: yaml -*-
# vim: ft=yaml:

# Arguments for commandline
[global]
    e2ts   # Enable multimedia indexing
    qr     # Enable QRCode
    #e2dsa # Enable file indexing and filesystem scanning

# Create users
[accounts]
    tlranda: <PASSWORD GOES HERE>
    guest:   <PASSWORD GOES HERE>

# Create vomes
[/] # Webroot location 'root'
    /mnt/Shareable # Shares content of this local directory
    accs:
        # Guest user has read access, I have read/write/modify/delete
        r: guest
        rwmd: tlranda

# You can make separate permissions by doing something like the following
[/GuestUploads]
    ./GuestUploads
    accs:
        rwmd: tlranda
        wG: * # G for GET, anyone can upload but only sees their own uploads
    flags:
        nodupe # Reject duplicate uploads
        e2d    # Enable uploads database

```
4) When you want the server to run, PRTY_CONFIG=~/.config/copyparty/my_party_config.conf python3 copyparty-sfx.py
5) Set a hole in the firewall for copyparty: ufw allow 3923/tcp
6) Use the QRCode to log into the server (localhost:3923) using an accepted account

### Jellyfin

Used for media serving from the CopyParty-hosted directories, as CopyParty cannot stream video well

1) Install via the curl | sh pattern or other relevant [installer from the website](https://jellyfin.org/downloads/server
2) Punch the UFW hole required for service: ufw allow 8096/tcp
3) Visit localhost:8096 to continue setting up via the wizard
* Save your admin user/pass in password manager or something!
* You should ensure the fully filepath to desired host-folders are set to permissions 755 for Jellyfin to properly index them!

Later: You can install official clients for various devices [from the website if you please](https::/jellyfin.org/downloads)

## Via Snap Apps

Install via snap-store or `snap install` in terminal

### Discord

Published by snapcrafters

1) Log in.

### Audacity

Published by snapcrafters

1) Set up the amplify macro
  + Tools -> Macro Manager
  + New Macro (Give it a name)
  + Insert the following commands:
    + Select All
    + Mix Stereo Down to Mono
    + Amplify (Ratio=2.26)

2) Set up the keyboard shortcut
  + Edit -> Preferences -> Shortcuts
  + Search for your macro name (Tools Menu / Apply Macro / `YOUR MACRO`
  + Click the blank box and set a keyboard shortcut (I typically bind this to CTRL+SHIFT+D) and click "Set"
  + Click OK to close preferences. All set.

### Kdenlive

Published by kde

I usually set things up as follows:

1) In editing view, click View -> {Clip Monitor, Library} to have the project monitor as a full view

2) Click View -> Save Layout -> Editing to preserve this as the default editing layout

3) When installed as Snap, you can copy-paste custom effect XML files into ${HOME}/snap/kdenlive/<VERSION>/.local/share/kdenlive/effects/

### Obsidian

Published by obsidianmd

### Zotero

Published by extraymond

1) Log in to Zotero (Edit -> Settings -> Sync -> Login)

### GIMP

Published by snapcrafters

### Moonlight

Published by maxiberta

1) After starting streams on your host computer with Sunshine (see Sunshine section), you can pair on Moonlight

2) Ensure Sunshine is running on the host and that you have the Web portal open (localhost:47990)

3) Select the device on Moonlight to initiate a pairing PIN request. In the web portal, click the "PIN" tab and type in this PIN, then give the client a name

4) Select Desktop for the simplest experience to ensure you can see / manipulate the computer via Moonlight

### Steam

Published by canonical

1) Open Steam, it takes a bit the first time to unpackage itself.

2) Log in to your account.

3) Disable hardware acceleration (known to make the library/store hang when unattended for small periods of time)
    3.1) Click 'Steam' in the upper left corner and navigate to settings
    3.2) Navigate to the 'Interface' panel and ensure 'Enable GPU accelerated rendering in web views (requires restart)' is DISABLED
    3.3) Enabling smooth scrolling in web views is OK -- you don't have to turn that off
    3.4) While we're here, ensure your Start Up Location is set to Library and that 'Notify me about ...' is DISABLED

4) Download a small game to trigger the proton compatibility layer installs / test.

5) For Lutris compatibility, make sure your profile has the following:
  + Visibility: Public
  + Game Visibility: Public

