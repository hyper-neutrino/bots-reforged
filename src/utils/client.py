import datamanager, discord

from .datamanager import get_data

class DiscordClient(discord.Client):
  def __init__(self):
    self.commands = []
    self.name = ""
    self.prefix = "~"
    self.color = 0x3333AA
  
  async def on_ready(self):
    await self.announce("Hello o/ I am now ready!")
  
  async def announce(self):
    for guild_id, channel_id in (await get_data([], "announcement_channels")):
      try:
        await self.get_guild(gid).get_channel(cid).send(*args, **kwargs)
      except:
        pass
  
  def command(self, section, match, syntax, description):
    return lambda func: self.commands.append((section, match, syntax, description, func))
  
  async def on_message(self, message):
    pass