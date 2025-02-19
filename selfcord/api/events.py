import itertools
from time import perf_counter
from aioconsole import aprint
from ..models import Guild, Convert, User, Message, Member, MessageAck, MessageReactionAdd, PresenceUpdate
import ujson

class Handler:
    def __init__(self, bot) -> None:
        self.bot = bot

    async def handle_ready(self, data: dict):
        self._ready_data = data
        # with open("test.json", "a+") as f:
        #     ujson.dump(data, f, indent=4)

        self.bot.resume_url = data['resume_gateway_url']
        self.bot.session_id = data['session_id']
        
        guilds = data.get("guilds", [])
        private_channels = data.get("private_channels", [])
        users = data.get("users", [])
        relationships = data.get("relationships", [])
        merged_members = data.get("merged_members", [])
        for guild, channel, user, relation in itertools.zip_longest(
            guilds,
            private_channels,
            users,
            relationships,
        ):
            if guild is not None:
                self.bot.user.guilds.append(Guild(guild, self.bot))
            if channel is not None:
                chan = Convert(channel, self.bot)
                self.bot.user.private_channels.append(chan)
                self.bot.cached_channels[chan.id] = chan
            if user is not None:
                check_user = self.bot.fetch_user(user["id"])
                if check_user is None:
                    user = User(user, self.bot)
                    self.bot.cached_users[user.id] = user
                else:
                    check_user.partial_update(user)
            if relation is not None:
                check_user = self.bot.fetch_user(relation["id"])
                if check_user is None:
                    user = User(relation, self.bot)
                    self.bot.cached_users[user.id] = user
                
                    if relation["type"] == 1:
                        self.bot.user.friends.append(user)
                    if relation["type"] == 2:
                        self.bot.user.blocked.append(user)
                else:
                    check_user.partial_update(relation)

        await self.bot.emit("ready", perf_counter() - self.bot.startup)


    async def handle_ready_supplemental(self, data: dict):
        # Ok discord bad code
        # I have to use data from ready and this event to properly form payloads
        # Discord Bad CODE

        temp_members = {}
        temp_guilds = {}

        for guild, members, extra_members in itertools.zip_longest(
            data.get("guilds", []),
            self._ready_data.get("merged_members", []),
            data.get("merged_members", {}),
        ):
            if members is not None:
                index = self._ready_data.get("merged_members", []).index(members)
                temp_members.setdefault(str(index), []).extend(members)

                for member in members:
                    check_user = self.bot.fetch_user(member['user_id'])
                    if check_user is None:
                        member = Member(member, self.bot)
                        self.bot.cached_users[member.id] = member
                    else:
                        check_user.partial_update(member)
            
            if extra_members is not None:
                index = data.get("merged_members", []).index(extra_members)
                temp_members.setdefault(str(index), []).extend(extra_members)

                for member in extra_members:
                    check_user = self.bot.fetch_user(member['user_id'])
                    if check_user is None:
                        member = Member(member, self.bot)
                        self.bot.cached_users[member.id] = member
                    else:
                        check_user.partial_update(member)
            # DISCORD BAD
            if guild is not None:
                guilds: list = data.get("guilds", [])
                index = guilds.index(guild)
                temp_guilds.setdefault(str(index), []).append(guild)
                # print(temp_guilds[str(index)])
                # print(index, guild)

                check_guild = self.bot.fetch_guild(guild['id'])
                if check_guild is None:
                    guild = Guild(guild, self.bot)
                    self.bot.user.guilds.append(guild)
                    for member in temp_members[str(index)]:
                        check_user = guild.fetch_member(member['user_id'])
                        if check_user is None:
                            user = Member(member, self.bot)
                            
                            guild.members.append(user)
                        else:
                            check_user.partial_update(member)
                            
                            guild.members.append(check_user)

                else:
                    check_guild.partial_update(guild)
                    for member in temp_members[str(index)]:
                        check_user = check_guild.fetch_member(member['user_id'])
                        if check_user is None:
                            user = Member(member, self.bot)
                          
                            check_guild.members.append(user)
                        else:
                            check_user.partial_update(member)
                            
                            check_guild.members.append(check_user)


        # DISCORD BAD
        merged_presences = data.get("merged_presences", {})
        guilds = merged_presences.get("guilds")
        for index, users in enumerate(guilds):
            temp_members.setdefault(str(index), []).extend(users)
            for user in users:
                # print(user['user_id'])
                check_user = self.bot.fetch_user(user['user_id'])
                if check_user is None:
                    user = User(user, self.bot)
                    self.bot.cached_users[user.id] = user
                else:
                    check_user.partial_update(user)

        friends = merged_presences.get("friends")
        for user in friends:
            check_user = self.bot.fetch_user(user['user_id'])
            if check_user is None:
                user = User(user, self.bot)
                self.bot.cached_users[user.id] = user
            else:
                check_user.partial_update(user)

        # DISCORD BAD x100000
        for index, indexed_guild in temp_guilds.items():
            members = temp_members[str(index)]
            guild = self.bot.fetch_guild(indexed_guild[0]['id'])
            if guild is not None:
                guild.members.extend(members)
                guild.partial_update(indexed_guild[0])


        await self.bot.inbuilt_commands()
        await self.bot.emit("ready_supplemental")

    async def handle_message_create(self, data: dict):
        message = Message(data, self.bot)
        self.bot.cached_messages[message.id] = message
        if message.author.id not in self.bot.cached_users:
            self.bot.cached_users[message.author.id] = message.author
        await self.bot.process_commands(message)
        await self.bot.emit("message", message)

    async def handle_message_update(self, data: dict):
        message = Message(data, self.bot)
        self.bot.cached_messages[message.id] = message
        await self.bot.emit("message", message)

    async def handle_message_ack(self, data: dict):
        ack = MessageAck(data, self.bot)
        await self.bot.emit("message_ack", ack)

    async def handle_message_delete(self, data: dict):
        # Was thinking of maybe removing it from cache
        # But I think would be more useful to keep it
        # This can return None if there is no valid message in cache
        deleted_message = self.bot.fetch_message(data['id'])
        await self.bot.emit("message_delete", deleted_message)

    async def handle_message_reaction_add(self, data: dict):
        await self.bot.emit("message_reaction_add", MessageReactionAdd(data, self.bot))

    async def handle_channel_create(self, data: dict):

        channel = Convert(data, self.bot)
        self.bot.cached_channels[channel.id] = channel

        if hasattr(channel, "guild_id"):
            guild = self.bot.fetch_guild(channel.guild_id)
            guild.channels.append(channel)
        else:
            self.bot.user.private_channels.append(channel)

        await self.bot.emit("channel_create", channel)

    async def handle_channel_delete(self, data: dict):
        deleted_channel = self.bot.fetch_channel(data['id'])
        await self.bot.emit("channel_delete", deleted_channel)
        del deleted_channel

    async def handle_thread_create(self, data: dict):
        pass

    async def handle_thread_delete(self, data: dict):
        pass

    async def handle_guild_create(self, data: dict):
        guild = Guild(data, self.bot)
        self.bot.user.guilds.append(guild)
        await self.bot.emit("guild_create")

    async def handle_guild_delete(self, data: dict):
        guild = self.bot.fetch_guild(data['id'])
        await self.bot.emit("guild_delete", guild)
        del guild

    async def handle_guild_member_list_update(self, data: dict):
        print(data)
        pass

    async def handle_presence_update(self, data: dict):
        pres = PresenceUpdate(data, self.bot)
        if isinstance(pres.user, User):
            pres.user.partial_update(data)
        await self.bot.emit("presence_update",pres)


    async def handle_thread_list_sync(self, data: dict):
        pass

    async def handle_guild_member_chunk(self, data: dict):
        pass