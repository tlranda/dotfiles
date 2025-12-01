# Host (probably local) and port (default OBS websocket port provided)
host = '127.0.0.1'
port = '4455'

# Set == False if you just want to write the password in this file in plaintext
# (not advised, write your password in a file relative to this file's location)
# You'll need to copy the OBS password from its websocket settings
password_from_file = True
password = 'obs_ws_password.secret'
if password_from_file:
    import pathlib
    with open(pathlib.Path(__file__).with_name(password), 'r') as f:
        password = "".join([_.strip() for _ in f.readlines()])

i3_follower_scene = 'i3Follower'
# Set == None to allow all workspaces,
# else set to list of strings of numbered workspaces that CAN be followed (allowlist)
# ie: [str(_) for _ in range(1,10)]
allowed_workspaces = None

# After setting up this config, ensure the OBS scene above has properly configured sources
# Each source should be a display capture with appropriate settings
# Each source should be named how i3 sees the monitor named
# ie: DisplayPort-0, HDMI-A-0 ...

stream_scene = 'StreamContent'
# Add a text item named "NowPlaying" for the script to indicate the name of your current game without worrying too much
# Relies upon .desktop files in ~/.local/share/applications to fetch nicer names for Steam games, otherwise just uses your container/workspace name
now_playing_source = 'NowPlaying'
