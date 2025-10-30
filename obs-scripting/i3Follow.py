# Builtin
import asyncio
import pathlib

# Dependencies
import simpleobsws
from i3ipc.aio import Connection
from i3ipc import Event

# Local
import obs_ws_config as cfg

class i3OBSManager:
    def __init__(self):
        # Index steam games to set identifiers
        self.known_steam_apps = dict()
        for fpath in pathlib.Path('~/.local/share/applications/').expanduser().iterdir():
            if fpath.suffix == '.desktop':
                with open(fpath, 'r') as f:
                    name = None
                    for line in f.readlines():
                        if line.startswith('Name='):
                            name = line.rstrip().split('=',1)[1]
                        if line.startswith('Exec='):
                            if 'steam' in line:
                                gameid = line.rstrip().rsplit('/',1)[1]
                                self.known_steam_apps[gameid] = name
                            break
        print(f"Found steam games: {self.known_steam_apps}")

        # Set up AIO loop
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.make_connections())
        loop.run_forever() # Hold event loop open

    async def make_connections(self):
        # Connect to OBS WebSocket using config Host:Port and password
        self.ws = simpleobsws.WebSocketClient(url=f"ws://{cfg.host}:{cfg.port}",
                                              password=cfg.password)
        await self.ws.connect()
        await self.ws.wait_until_identified()
        # Cache all OBS sources in target scene for i3Follower
        data = {'sceneName': cfg.i3_follower_scene}
        req = simpleobsws.Request('GetSceneItemList', data)
        result = await self.ws.call(req)
        sceneItems = result.responseData['sceneItems']
        self.obs_sources = dict((_['sourceName'], _['sceneItemId']) for _ in sceneItems)

        # Cache all OBS sources in target scene for stream
        data = {'sceneName': cfg.stream_scene}
        req = simpleobsws.Request('GetSceneItemList', data)
        result = await self.ws.call(req)
        sceneItems = result.responseData['sceneItems']
        self.stream_sources = dict((_['sourceName'], _['sceneItemId']) for _ in sceneItems)

        # Connect to i3 IPC and set up callback
        self.i3 = await Connection().connect()
        self.i3.on(Event.WORKSPACE_FOCUS, self.on_workspace_focus)
        self.i3.on(Event.WORKSPACE_FOCUS, self.rename_playing)
        self.i3.on(Event.WINDOW_FOCUS, self.rename_playing)

        print("Ready!")

    async def rename_playing(self, i3, event):
        print("Rename playing called!")
        # Change 'NowPlaying' text
        if hasattr(event, 'container'):
            workspace_name = event.container.window_class
        elif hasattr(event, 'current'):
            workspace_name = event.current.name

        # Edit the workspace name if it's in a known steam ID
        if workspace_name.startswith('steam_app_'):
            workspace_suffix = workspace_name[len('steam_app_'):]
            workspace_name = self.known_steam_apps.setdefault(workspace_suffix, workspace_suffix)
        else:
            workspace_name = workspace_name.capitalize()
        data = {'inputName': cfg.now_playing_source,
                'inputSettings': {'text': f"Now Playing: {workspace_name}"},
                }
        req = simpleobsws.Request('SetInputSettings', data)
        result = await self.ws.call(req)

    async def on_workspace_focus(self, i3, event):
        print("On workspace focus called!")
        # Output is not available except when digging into internals -- likely
        # NOT the correct way to access this information, may get broken!
        expect_obs_source = event.__dict__['ipc_data']['current']['output']
        focused_workspace = str(event.current.num)

        if cfg.allowed_workspaces is not None and focused_workspace not in cfg.allowed_workspaces:
            print(f"Not allowed to track workspace {focused_workspace}!")
            return
        print(f"Focus workspace {focused_workspace} -- target source {expect_obs_source}")
        # Change i3Follower's focused monitor by enabling one and disabling all others
        for source in self.obs_sources:
            data = {'sceneName': cfg.i3_follower_scene,
                    'sceneItemId': self.obs_sources[source],
                    'sceneItemEnabled': source == expect_obs_source,
                    }
            req = simpleobsws.Request('SetSceneItemEnabled', data)
            result = await self.ws.call(req)

i3OBSManager()

