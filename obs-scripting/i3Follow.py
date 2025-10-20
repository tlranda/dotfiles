import asyncio
import simpleobsws
from i3ipc.aio import Connection
from i3ipc import Event
import obs_ws_config as cfg

class i3OBSManager:
    def __init__(self):
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
        # Cache all OBS sources in target scene
        data = {'sceneName': cfg.scene}
        req = simpleobsws.Request('GetSceneItemList', data)
        result = await self.ws.call(req)
        sceneItems = result.responseData['sceneItems']
        self.obs_sources = dict((_['sourceName'], _['sceneItemId']) for _ in sceneItems)

        # Connect to i3 IPC and set up callback
        self.i3 = await Connection().connect()
        self.i3.on(Event.WORKSPACE_FOCUS, self.on_workspace_focus)

        print("Ready!")

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
        for source in self.obs_sources:
            data = {'sceneName': cfg.scene,
                    'sceneItemId': self.obs_sources[source],
                    'sceneItemEnabled': source == expect_obs_source,
                    }
            req = simpleobsws.Request('SetSceneItemEnabled', data)
            result = await self.ws.call(req)

i3OBSManager()

"""
ipc_data': {'change': 'focus',
'current':
    {'id': 105146819021808,
    'type': 'workspace',
    'orientation': 'horizontal',
    'scratchpad_state': 'none',
    'percent': None,
    'urgent': False,
    'marks': [],
    'focused': False,
    'output': 'HDMI-A-0',
    'layout': 'splith',
    'workspace_layout': 'default',
    'last_split_layout': 'splith',
    'border': 'normal',
    'current_border_width': -1,
    'rect': {'x': 1920, 'y': 0, 'width': 1920, 'height': 1055},
    'deco_rect': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
    'window_rect': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
    'geometry': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
    'name': '5: Obs',
    'window_icon_padding': -1,
    'num': 5,
    'gaps': {'inner': 0, 'outer': 0, 'top': 0, 'right': 0, 'bottom': 0, 'left': 0},
    'window': None,
    'window_type': None,
    'nodes': [{'id': 105146818512896, 'type': 'con', 'orientation': 'none', 'scratchpad_state': 'none', 'percent': 1.0, 'urgent': False, 'marks': [], 'focused': True, 'output': 'HDMI-A-0', 'layout': 'splith', 'workspace_layout': 'default', 'last_split_layout': 'splith', 'border': 'normal', 'current_border_width': 2, 'rect': {'x': 1920, 'y': 0, 'width': 1920, 'height': 1055}, 'deco_rect': {'x': 0, 'y': 0, 'width': 1920, 'height': 24}, 'actual_deco_rect': {'x': 0, 'y': 0, 'width': 1920, 'height': 24}, 'window_rect': {'x': 2, 'y': 24, 'width': 1916, 'height': 1029}, 'geometry': {'x': 0, 'y': 0, 'width': 1086, 'height': 729}, 'name': 'OBS 32.0.1 - Profile: Untitled - Scenes: Untitled', 'window_icon_padding': -1, 'window': 33554443, 'window_type': 'normal', 'window_properties': {'class': 'obs', 'instance': 'obs', 'machine': 'kismet', 'title': 'OBS 32.0.1 - Profile: Untitled - Scenes: Untitled', 'transient_for': None}, 'nodes': [], 'floating_nodes': [], 'focus': [], 'fullscreen_mode': 0, 'sticky': False, 'floating': 'auto_off', 'swallows': []}],
    'floating_nodes': [],
    'focus': [105146818512896],
    'fullscreen_mode': 1,
    'sticky': False,
    'floating': 'auto_off',
    'swallows': []
    },
'change': 'focus',
'current': <i3ipc.aio.connection.Con object at 0x7d847a5f4440>,
'old': <i3ipc.aio.connection.Con object at 0x7d847a5f4620>
}
"""
