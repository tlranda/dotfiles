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

# Programs to Install / Configure

## Via Package-Manager

### Piper

Allows configuring mouse RBG etc on Linux

### OpenSSH

Allows connecting to the device over SSH

* Package manager install openssh-server
* sudo service ssh start
* sudo systemctl enable ssh

If connection times out, probably firewall related:
* sudo ufw allow ssh
* sudo ufw enable

### Fastfetch

Fancy way to show off system configuration

### i3

Customizable window manager

* Copy .config/i3 files into ${HOME}/.config/i3 after basic setup is present
* Ensure you have installed Python3 and the i3ipc package for python scripts to work

## Via External

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

### Sunshine

1) [Download latest GitHub release](https://github.com/LizardByte/Sunshine/releases)

2) Add packages as needed (`apt-get install miniupnpc libminiupnpc17`)
  + https://github.com/unicode-org/icu/releases/tag/release-70-1
  + May have to manually toss these files into their respective directories in /usr/local
  + sudo ldconfig to reload cache

3) Install `sudo dpkg -i <sunshine*.deb>`

4) Visit localhost:47990 in your browser to configure your username and password. Save them!

5) You should be able to log in to the proper portal for Sunshine now and set up client connections

### Davinci Resolve

0) You may need to install the following packages:
  + libapr1
  + libaprutil1
  + libasound2
  + libglib2.0-0
  + libxcb-composite0
  + libxcb-xinput0

1) [Install from BlackMagicDesign](https://www.blackmagicdesign.com/products/davinciresolve)

2) Unzip the file, then chmod +x the .run file

3) sudo ./DavinciResolve\*.run -i

4) You may retrieve [help from this post](https://www.dedoimedo.com/computers/davinci-resolve-ubuntu-24-04.html) if you run into additional errors

5) As of now, my install is nonfunctional (looks like changes to glibc from years ago are either not supported or they rely on things that were deprecated. I'm not sure)

6) It should run out of /opt/resolve/bin, you'll want to add that to PATH for it to be properly selectable as resolve.

## Via Snap Apps

Install via snap-store or `snap install` in terminal

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

3) Download a small game to trigger the proton compatibility layer installs / test.

4) For Lutris compatibility, make sure your profile has the following:
  + Visibility: Public
  + Game Visibility: Public

### OBS

Published by snapcrafters

#### Set up replay buffer

1) Set up the scene
  + Add a scene if necessary. I call mine "ReplayBufferScene"
  + Add a source to the scene. I use a display capture on the primary monitor. Rename if you want.

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

