from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from .message import Message
from .assets import Asset
import random
import asyncio
import datetime
import time
from .permissions import Permission

if TYPE_CHECKING:
    from .users import User
    from ..bot import Bot
    from ..api import HttpClient


class PermissionOverwrite:
    def __init__(self, payload: dict, bot: Bot):
        self.bot: Bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.id: str = payload["id"]
        self.type: int = payload["type"]
        self.allow: int = Permission(payload["allow"], self.bot)
        self.deny: int = Permission(payload["deny"], self.bot)

class Channel:
    def __init__(self, payload: dict, bot: Bot):
        self.bot: Bot = bot
        self.http: HttpClient = bot.http
        self.update(payload)

    def update(self, payload):
        self.id = payload["id"]
        self.type = payload["type"]
        self.flags = payload.get("flags")
        self.last_message_id = payload.get("last_message_id")
        self.guild_id = payload.get("guild_id")

    async def delete(self):
        await self.http.request(
            "delete", "/channels/" + self.id, json={}
        )


class Callable(Channel):
    def __init__(self, payload: dict, bot: Bot):
        self.bot: Bot = bot
        self.http: HttpClient = bot.http
        self.update(payload)

    def update(self, payload):
        pass

    async def call(self):
        if self.type in (1,3):
            await self.bot.gateway.call(self.id, None)
        else:
            await self.bot.gateway.call(self.id, self.guild_id)
        await self.ring()

    async def ring(self):
        await self.http.request(
            "POST", f"/channels/{self.id}/call/ring",
            json={"recipients": None}
        )

    async def leave_call(self):
        await self.bot.gateway.leave_call()



class Messageable(Channel):
    def __init__(self, payload: dict, bot: Bot):
        self.bot: Bot = bot
        self.http: HttpClient = bot.http
        self.update(payload)

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id}>"

    def __str__(self):
        return self.name

    def update(self, payload):
        self.id: str = payload["id"]
        self.type: int = int(payload["type"])
        self.flags = payload.get("flags")
        self.last_message_id: Optional[str] = payload.get("last_message_id")

    def calc_nonce(self, date="now"):
        if date == "now":
            unixts = time.time()
        else:
            unixts = time.mktime(date.timetuple())
        return (int(unixts)*1000-1420070400000)*4194304

    @property
    def nonce(self) -> int:
        return self.calc_nonce()

    async def delayed_delete(self, message, time):
        await asyncio.sleep(time)
        await message.delete()

    async def send(
        self, content: str, files: Optional[list[str]] = None, delete_after: Optional[int] = None, tts: bool = False
    ) -> Optional[Message]:
        if self.type in (1, 3):
            headers = {"referer": f"https://canary.discord.com/channels/@me/{self.id}"}
        else:
            headers = {"referer": f"https://canary.discord.com/channels/{self.guild_id}/{self.id}"}
        json = await self.http.request(
            "POST",
            f"/channels/{self.id}/messages",
            headers=headers,
            json={"content": content, "flags": 0, "tts": tts, "nonce": self.nonce},
        )
        if json is not None:
            if delete_after != None:
                msg = Message(json, self.bot)
                await asyncio.create_task(self.delayed_delete(msg, delete_after))
                return msg

            return Message(json, self.bot)

    async def delete(self) -> Optional[Messageable]:
        if self.type in (1,3):
            json = await self.http.request(
                "DELETE", f"/channels/{self.id}?silent=false",
                headers = {"referer": f"https://canary.discord.com/channels/@me/{self.id}"}
            )
        else:
            json = await self.http.request(
                "DELETE", f"/channels/{self.id}",
                headers = {"referer": f"https://canary.discord.com/channels/{self.guild_id}/{self.id}"}
            )

    async def history(self, limit: int = 50, bot_user_only: bool = False):
        n = 0
        if self.type in (1, 3):
            headers = {"referer": f"https://canary.discord.com/channels/@me/{self.id}"}
        else:
            headers = {
                "referer": f"https://canary.discord.com/channels/{self.guild_id}/{self.id}"
            }
        json = await self.http.request(
            "GET", f"/channels/{self.id}/messages?limit=50",
            headers=headers
        )
        msgs = []

        for message in json:
            msg = Message(message, self.bot)
            if bot_user_only:
                if msg.author.id == self.bot.user.id:
                    msgs.append(msg)
            else:
                msgs.append(msg)
            self.bot.cached_messages[msg.id] = msg
            n += 1

        while n < limit:
            last = msgs[-1]
            json = await self.http.request(
                "GET", f"/channels/{self.id}/messages?before={last.id}&limit=50",
                headers=headers
            )

            for message in json:
                msg = Message(message, self.bot)
                if bot_user_only:
                    if msg.author.id == self.bot.user.id:
                        msgs.append(msg)
                else:
                    msgs.append(msg)
                self.bot.cached_messages[msg.id] = msg
                n += 1

        return msgs[:limit]

    async def purge(self, amount: int):
        msgs = await self.history(amount, bot_user_only=True)
        for i in range(0, len(msgs), 2):
            await asyncio.gather(*(msg.delete()
                                   for msg in msgs[i:i+2]))



class DMChannel(Messageable, Callable):
    def __init__(self, payload: dict, bot: Bot):
        super().__init__(payload, bot)
        super().update(payload)
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.recipient: Optional[User] = self.bot.fetch_user(
            payload["recipient_ids"][0] if payload.get("recipient_ids") is not None else ""
        )
        self.is_spam: Optional[bool] = payload.get("is_spam")



class GroupChannel(Messageable, Callable):
    def __init__(self, payload: dict, bot: Bot):
        super().update(payload)
        super().__init__(payload, bot)
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.recipient: list[Optional[User]] = (
            [self.bot.fetch_user(user) for user in payload["recipient_ids"]]
            if payload.get("recipient_ids") is not None
            else []
        )
        self.is_spam: Optional[bool] = payload.get("is_spam")
        self.icon: Optional[Asset] = (
            Asset(self.id, payload["icon"]).from_icon()
            if payload.get("icon") is not None
            else None
        )
        self.name: Optional[str] = payload.get("name")
        self.last_pin_timestamp: Optional[int] = payload.get("last_pin_timestamp")


class TextChannel(Messageable):
    """
    This class is used to represent a text channel in Discord.
    """
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.nsfw = payload.get("nsfw")
        self.guild_id = payload.get("guild_id")
        self.category_id = payload.get("parent_id")
        self.position = payload.get("position")
        self.rate_limit_per_user = payload.get("rate_limit_per_user")
        self.name = payload.get("name")
        self.last_pin_timestamp = payload.get("last_pin_timestamp")

        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore

    async def edit(self, name: str="", topic: str="", nsfw: bool=False, timeout: int=0):
        self.name = name
        self.nsfw = nsfw
        self.rate_limit_per_user = timeout

        await self.http.request(
            "patch", "/channels/" + self.id, json={
                    "name": name,
                    "type": 0,
                    "topic": topic,
                    "bitrate": 64000,
                    "user_limit": 0,
                    "nsfw": nsfw,
                    "flags": 0,
                    "rate_limit_per_user": timeout
            }
        )


class VoiceChannel(Messageable, Callable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.guild_id = payload.get("guild_id")
        self.category_id = payload.get("parent_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore
        self.user_limit = payload.get("user_limit")
        self.topic = payload.get("topic")
        self.rtc_region = payload.get("rtc_region")
        self.slowdown = payload.get("rate_limit_per_user")
        self.nsfw = payload.get("nsfw")
        self.name = payload.get("name")
        self.icon_emoji = payload.get("icon_emoji")
        self.bitrate = payload.get("bitrate")


class Category(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore


class Announcement(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore


class AnnouncementThread(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore


class PublicThread(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore


class PrivateThread(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore


class StageChannel(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.last_message_id: Optional[str] = payload.get("last_message_id")
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore


class Directory(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore


class ForumChannel(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.topic = payload.get("topic")
        self.template = payload.get("template")
        self.slowdown = payload.get("rate_limit_per_user")
        self.category_id = payload.get("category_id")
        self.nsfw = payload.get("nsfw")
        self.default_thread_rate_limit_per_user = payload.get(
            "default_thread_rate_limit_per_user"
        )
        self.default_sort_order = payload.get("default_sort_order")
        self.default_reaction_emoji = payload.get("default_reaction_emoji")
        self.default_forum_layout = payload.get("default_forum_layout")
        self.available_tags = payload.get("available_tags")

        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore


class MediaChannel(Messageable):
    def __init__(self, payload: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)
        super().update(payload)
        super().__init__(payload, bot)

    def update(self, payload):
        self.name = payload.get("name")
        self.guild_id = payload.get("guild_id")
        self.position = payload.get("position")
        self.permission_overwrites = [PermissionOverwrite(overwrite, self.bot) for overwrite in payload.get("permission_overwrites", [])] # type: ignore




class Convert(Messageable):
    def __new__(cls, payload: dict, bot: Bot) -> Messageable:
        tpe = payload["type"]
        if tpe == 0:
            return TextChannel(payload, bot)
        if tpe == 1:
            return DMChannel(payload, bot)
        if tpe == 2:
            return VoiceChannel(payload, bot)
        if tpe == 3:
            return GroupChannel(payload, bot)
        if tpe == 4:
            return Category(payload, bot)
        if tpe == 5:
            return Announcement(payload, bot)
        if tpe == 10:
            return AnnouncementThread(payload, bot)
        if tpe == 11:
            return PublicThread(payload, bot)
        if tpe == 12:
            return PrivateThread(payload, bot)
        if tpe == 13:
            return StageChannel(payload, bot)
        if tpe == 14:
            return Directory(payload, bot)
        if tpe == 15:
            return ForumChannel(payload, bot)
        if tpe == 16:
            return MediaChannel(payload, bot)
        return TextChannel(payload, bot)
