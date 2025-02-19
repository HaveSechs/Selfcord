from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from zlib import decompressobj
import time
import asyncio
from .events import Handler
import websockets
import ujson

if TYPE_CHECKING:
    from ..bot import Bot
    from websockets import Connect
    from ..models import Capabilities, Guild, Messageable


class Gateway:

    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE = 3
    VOICE_STATE = 4
    VOICE_PING = 5
    RESUME = 6
    RECONNECT = 7
    REQUEST_MEMBERS = 8
    INVALIDATE_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11
    GUILD_SYNC = 12

    def __init__(self, bot: Bot, decompress: bool = True) -> None:
        self.decompress = decompress
        self.bot: Bot = bot
        self.capabilities: Capabilities = self.bot.capabilities
        self.handler: Handler = Handler(bot)
        self.token: Optional[str] = None
        self.zlib = decompressobj(15)
        self.zlib_suffix: bytes = b"\x00\x00\xff\xff"
        self.last_ack: float = 0
        self.last_send: float = 0
        self.latency: float = float("inf")
        self.ws: Optional[Connect] = None
        self.alive = False
        self.URL = (
            "wss://gateway.discord.gg/?encoding=json&v=9&compress=zlib-stream"
            if self.decompress else 
            "wss://gateway.discord.gg/?encoding=json&v=9"
        )


    async def send_json(self, payload: dict):
        if self.ws:
            await self.ws.send(ujson.dumps(payload))

    async def load_async(self, item):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, ujson.loads, item)

    async def recv_json(self):
        if self.ws:
            
            item = await self.ws.recv()
    
            if self.decompress:
                buffer = bytearray()
                buffer.extend(item)
                if len(item) < 4 or item[-4:] != self.zlib_suffix:
                    return
                n = len(item)
                try:
                    item = self.zlib.decompress(item)
                    self.zlib.flush(n)
                    # self.zlib = decompressobj(15)
                except Exception as e:
                    # with open("test.txt", "a+") as f:
                    #     f.write(f"{item}\n")
                    print(e)
            item = await self.load_async(item)

            # await asyncio.sleep(1)

            if item:
                op = item["op"]
                data = item["d"]
                event = item["t"]

                if op == self.HELLO:
                    interval = data["heartbeat_interval"] / 1000.0
                    await self.identify()
                    asyncio.create_task(self.heartbeat(interval))

                elif op == self.HEARTBEAT_ACK:
                    self.heartbeat_ack()

                elif op == self.DISPATCH:
                    if hasattr(self.handler, f"handle_{event.lower()}"):
                        method = getattr(
                            self.handler, f"handle_{event.lower()}")
                        asyncio.create_task(method(data))

    async def connect(self):
        self.ws = await websockets.connect(
            self.URL, origin="https://discord.com", max_size=None,
            extra_headers={"user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0"},
            read_limit=1000000, max_queue=100, write_limit=1000000,
        )

    async def start(self, token: str):
        await self.connect()
        self.alive = True
        self.token = token
        while self.alive:
            await self.recv_json()

    async def close(self):
        """This function closes the websocket
        """
        self.alive = False
        if self.ws:
            await self.ws.close()

    async def identify(self):
        payload = {
            "op": 2,
            "d": {
                "capabilities": self.capabilities.value,
                "token": self.token,
                "client_state": {
                    "guild_versions": {},
                    "api_code_version": 0,
                    "highest_last_message_id": "0",
                    "initial_guild_id": None,
                    "private_channels_version": "0",
                    "read_state_version": 0,
                    "user_guild_settings_version": -1,
                    "user_settings_version": -1,
                },
                "compress": False,
                "presence": {
                    "activities": [],
                    "afk": False,
                    "since": 0,
                    "status": "online",
                },
                "properties": {
                    "os": "Linux",
                    "browser": "Discord Client",
                    "browser_version": "22.3.12",
                    "client_build_number": 221132,
                    "client_event_source": None,
                    "client_version": "0.0.162",
                    "browser_useragent": (
                        "Mozilla/5.0 (X11; Linux x86_64)"
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "discord/0.0.157 "
                        "Chrome/108.0.5359.215 "
                        "Electron/22.3.2 "
                        "Safari/537.36"
                    ),
                    "distro": '"Manjaro Linux"',
                    "native_build_number": None,
                    "os_version": "5.10.189-1-MANJARO",
                    "release_channel": "canary",
                    "window_manager": "KDE, unknown",
                    "system-locale": "en-GB",
                    "os_arch": "x64",
                },
            },
        }
        await self.send_json(payload)

    async def gather_members(self, guild_id: str, channel_id: str):
        payload = {
            "op": 14,
            "d": {
                "guild_id": guild_id,
                "channels": {
                    channel_id: [[0, 99]]
                }
            },
        }
        await self.send_json(payload)

    async def heartbeat(self, interval: int):
        heartbeat_json = {"op": 1, "d": time.time()}
        while True:
            await asyncio.sleep(interval)
            await self.send_json(heartbeat_json)
            self.last_send = time.perf_counter()

    def heartbeat_ack(self):
        self.last_ack = time.perf_counter()
        self.latency = self.last_ack - self.last_send

    def roundup(self, n):
        import math
        return int(math.ceil(n / 100.0)) * 100
    
    def chunks(self, lst, n):
        for i in range(0, len(lst), 1):
            if len(lst[: i + 1]) > 3:
                for i in range(i, len(lst), n):
                    yield lst[i : i + n]
                break
            yield lst[: i + 1]

    async def chunk_members(self, guild: Guild):
        roles = guild.me.roles
        print(roles)
        channels = []
        for channel in guild.channels:
            print(channel.permission_overwrites)
            if len(channel.permission_overwrites) > 0:
                for overwrite in channel.permission_overwrites:
                    if overwrite.id in [role.id for role in roles]:
                        pass

        
        ranges = []

        if guild.member_count is not None:
            for i in range(0, guild.member_count, 100):
                ranges.append(
                    [i, self.roundup(i + (guild.member_count - i)) - 1]
                ) if i + 99 > guild.member_count else ranges.append([i, i + 99])
            
        for item in self.chunks(ranges, 3):

            queries = {}
            payload = {
                "op": 14,
                "d": {
                    "guild_id": guild.id,
                    "typing": True,
                }
            }
            data = payload['d']

            # For now
            for channel in channels:
                queries[channel.id] = item

            data['channel'] = queries
            
            await self.send_json(payload)

            await asyncio.sleep(2.0)
        

    async def call(self, channel: str, guild: Optional[str] = None):
        payload = {
            "op": 4,
            "d": {
                "guild_id": guild,
                "channel_id": channel,
                "preferred_region": "rotterdam",
                "self_mute": False,
                "self_deaf": False,
                "self_video": False,
            },
        }
        await self.send_json(payload)

    async def leave_call(self):
        payload = {
            "op": 4,
            "d": {
                "guild_id": None,
                "channel_id": None,
                "self_mute": False,
                "self_deaf": False,
                "self_video": False,
            },
        }
        await self.send_json(payload)
