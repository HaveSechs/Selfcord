from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from .users import User, Member

if TYPE_CHECKING:
    from ..bot import Bot
    from .channels import Messageable
    from .guild import Guild

class Message:
    def __init__(self, data: dict, bot: Bot):
        self.bot = bot
        self.http = bot.http
        self.update(data)

    def update(self, payload: dict):
        self.id: Optional[str] = payload.get("id")
        self.content: Optional[str] = payload.get("content")
        self.type: int = payload.get("type", 0)
        self.tts: bool = payload.get("tts", False)
        self.timestamp: Optional[int] = payload.get("timestamp")
        self.replied_message: Optional[Message] = payload.get("referenced_message")
        self.pinned: Optional[bool] = payload.get("pinned")
        self.nonce: Optional[int] = payload.get("nonce")
        self.mentions: Optional[dict] = payload.get("mentions")
        self.channel_id: str = payload.get("channel_id", "")
        self.channel: Optional[Messageable] = self.bot.fetch_channel(self.channel_id)
        self.guild_id: str = payload.get("guild_id", "")
        self.guild: Optional[Guild] = self.bot.fetch_guild(self.guild_id)
        self.author: Optional[User] = (
            User(payload['author'], self.bot)
            if payload.get("author") is not None
            else None
        )
        # we will fix later 
        # self.member = Member(payload.get("member"), self.bot)
        self.flags: int = payload.get("flags", 0)
        # Create associated classes with these
        self.embeds = payload.get("embeds")
        self.components = payload.get("components")
        self.attachments = payload.get("attachments")

    async def delete(self):
        await self.http.request(
            "DELETE", f"/channels/{self.channel_id}/messages/{self.id}"
        )

    async def reply(self, content: str, files: Optional[list[str]] = None, delete_after: Optional[int] = None, tts: bool = False) -> Optional[Message]:
        json = await self.http.request(
            "POST", f"/channels/{self.channel_id}/messages",
            json={
                "mobile_network_type":"unknown",
                "content":content,
                "tts":tts,
                "message_reference":{
                    "channel_id":self.channel_id,
                    "message_id":self.id
                },
                "allowed_mentions":{"parse":["users","roles","everyone"],"replied_user":True},"flags":0}
        )
        if json is not None:
            return Message(json, self.bot)

    async def edit(self, content: str) -> Optional[Message]:
        json = await self.http.request(
            "PATCH", f"/channels/{self.channel_id}/messages/{self.id}", 
            json={"content": content}
        )
        if json is not None:
            return Message(json, self.bot)
        
class MessageAck:
    def __init__(self, payload: dict, bot) -> None:
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.channel_id: str = payload['channel_id']
        self.channel = self.bot.fetch_channel(self.channel_id)
        self.flags: Optional[int] = payload.get("flags")
        self.last_viewed = payload['last_viewed']
        self.message_id = payload['message_id']
        self.message = self.bot.fetch_message(self.message_id)
        self.version = payload['version']

class EmbedField:
    def __init__(self, payload: dict, bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.name = payload.get("name")
        self.value = payload.get("value")
        self.inline = payload.get("inline")

class EmbedThumbnail:
    def __init__(self, payload: dict, bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.url = payload['url']
        self.proxy_url = payload.get("proxy_url")
        self.height = payload.get("height")
        self.width = payload.get("width")

class EmbedVideo:
    def __init__(self, payload: dict, bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.url = payload['url']
        self.proxy_url = payload.get("proxy_url")
        self.height = payload.get("height")
        self.width = payload.get("width")

class EmbedImage:
    def __init__(self, payload: dict, bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.url = payload['url']
        self.proxy_url = payload.get("proxy_url")
        self.height = payload.get("height")
        self.width = payload.get("width")

class EmbedProvider:
    def __init__(self, payload: dict, bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.name = payload.get("name")
        self.url = payload.get("url")

class EmbedAuthor:
    def __init__(self, payload: dict, bot) -> None:
        self.bot = bot
        self.http = bot.http
        self.update(payload)
    
    def update(self, payload: dict):
        self.name = payload.get("name")
        self.url = payload.get("url")
        self.icon_url = payload.get("icon_url")
        self.proxy_icon_url = payload.get("proxy_icon_url")

class EmbedFooter:
    def __init__(self, payload: dict, bot) -> None:
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.text = payload.get("text")
        self.icon_url = payload.get("icon_url")
        self.proxy_icon_url = payload.get("proxy_icon_url")


class Embed:
    def __init__(self, payload: dict, bot):
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.fields: list[EmbedField] = [EmbedField(field, self.bot) for field in payload.get("fields", [])]
        self.title: Optional[str] = payload.get("title")
        self.description: Optional[str] = payload.get("description")
        self.type: Optional[str] = payload.get("type")
        self.url: Optional[str] = payload.get("url")
        self.timestamp: Optional[int] = payload.get("timestamp")
        self.color: Optional[int] = payload.get("color")
        self.footer: Optional[str] = payload.get("footer")
        self.image: Optional[dict] = payload.get("image")
        self.thumbnail: Optional[dict] = payload.get("thumbnail")
        self.video: Optional[dict] = payload.get("video")
        self.provider: Optional[dict] = payload.get("provider")
        self.author: Optional[str] = payload.get("author")


class MessageReactionAdd:
    def __init__(self, payload: dict, bot) -> None:
        self.bot = bot
        self.http = bot.http
        self.update(payload)

    def update(self, payload: dict):
        self.burst: bool = payload.get("burst", False)
        self.channel_id: Optional[str] = payload.get("channel_id")
        self.emoji: Optional[str] = payload.get("emoji")
        self.guild_id: Optional[str] = payload.get("guild_id")
        self.type: int = payload.get("type", 0)
        self.user_id: Optional[str] = payload.get("user_id")
        self.message_id: str = payload.get("message_id", "")
        self.message: Message = self.bot.fetch_message(self.message_id)
        self.author_id: Optional[str] = payload.get("message_author_id")
        self.author = self.bot.fetch_user(self.author_id)
        self.user = self.bot.fetch_user(self.user_id) 
