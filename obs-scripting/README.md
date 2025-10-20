1) Install simpleobsws via your package manager
2) Run OBS via terminal so it can use local packages (like i3ipc, another dependency of the i3Follower.py script)
3) Enable WebSocket Servers in OBS
4) Set up your OBS scenes/sources and other files according to all instructions in obs\_ws\_config.py
5) Run the script in another terminal (you cannot run it as a script in OBS's script loader)

If you want to set up an OBS Virtual Camera, you may also need to:

1) Create a camera source with video4linux: `sudo modprobe v4l2loopback devices=1 video_nr=2 card_label="OBS Virtual Camera" exclusive_caps=1`
2) Ensure you have permissions: `sudo chmod 666 /dev/video*`
3) Add yourself to the video group for good measure: `sudo usermod -aG video $USER`
4) Run OBS

