import discord, shlex, traceback

from datamanager import config, get_data, load_data
from errors import BotError, DataError
from logs import log

class DiscordClient(discord.Client):
  def __init__(self):
    discord.Client.__init__(self, intents = discord.Intents.all())
    self.commands = []
    self.name = ""
    self.color = 0x3333AA
  
  async def on_ready(self):
    load_data()
    print("Ready!")
    await announce("Hello o/ I am now ready!")
  
  def command(self, section, match, syntax, description):
    return lambda func: self.commands.append((section, match, syntax, description, func)) or func
  
  async def on_message(self, message):
    if message.guild:
      print(f"[{message.guild.name} #{message.channel.name}] {message.author.name}#{message.author.discriminator}: {message.content}")
      if await get_data("silence", message.guild.id, message.author.id, default = False):
        await message.delete()
      if message.author.id not in config["sudo"] and await get_data("ignore", message.guild.id, message.author.id, default = False):
        return
    else:
      print(f"[DM Message] {message.author.name}#{message.author.discriminator}: {message.content}")
    try:
      command = shlex.split(message.content)
    except:
      command = []
    for _, match, _, _, func in self.commands:
      try:
        if isinstance(match, list):
          matched = command and command[0] in ["pls", "please"]
          if matched:
            for m, c in zip(match, command[1:]):
              if m == c or m == "?" or type(m) in (list, tuple, set) and c in m:
                continue
              if m == "...":
                matched = True
                break
              matched = False
              break
            if len(command) - 1 > len(match) and "..." not in match:
              matched = False
            if len(command) - 1 < len(match) and not (len(command) == len(match) and match and match[-1] == "..."):
              matched = False
        else:
          matched = match(message.content)
        if matched:
          try:
            await func(command, message)
          except (BotError, DataError) as e:
            await send(message, e.message, reaction = "x")
          except IndexError:
            await send(message, "IndexError: make sure you have enough arguments for this command!", reaction = "x")
          except discord.errors.Forbidden:
            await send(message, "This bot does not have sufficient permissions to execute this command!", reaction = "x")
          except:
            if message.content.startswith("pls"):
              await send(message, "An uncaught exception occurred! Prefix with `please` to debug, or contact a developer.", reaction = "x")
            elif message.content.startswith("please"):
              await send(message, "```\n" + traceback.format_exc()[:1990] + "\n```", reaction = "x")
      except:
        pass # some messages have single quotes and unavoidably will error, so we can just ignore all errors that arose from parsing since real errors are caught

client = DiscordClient()

async def announce(*args, **kwargs):
  for gid, cid in (await get_data("announcement_channels", default = set())):
    try:
      await client.get_guild(gid).get_channel(cid).send(*args, **kwargs)
    except:
      pass

def english_list(words):
  words = list(words)
  if len(words) == 0:
    return "<empty list>"
  if len(words) == 1:
    return words[0]
  if len(words) == 2:
    return words[0] + " and " + words[1]
  return ", ".join(words[:-1]) + ", and " + words[-1]

def quote(item):
  if isinstance(item, str):
    return "'" + item + "'"
  return list(map(quote, item))

def emoji(name, default = None):
  for guild in client.guilds:
    for emoji in guild.emojis:
      if emoji.name == name:
        return emoji
  if default is None:
    return name
  return default

emoji_shorthand = {
  "!": "❗",
  "?": "❔",
  "x": "❌",
  "check": "✅"
}

async def send(message, *args, **kwargs):
  if "embed" in kwargs:
    kwargs["embed"].set_footer(text = f"Requested by {message.author.display_name}")
  reply = await message.channel.send(*args, **{a: kwargs[a] for a in kwargs if a != "reaction"})
  if "reaction" in kwargs:
    if type(kwargs["reaction"]) == list:
      reaction_list = kwargs["reaction"]
    else:
      reaction_list = [kwargs["reaction"]]
  else:
    reaction_list = ["check"]
  for reaction in reaction_list:
    try:
      await message.add_reaction(emoji(emoji_shorthand.get(reaction, reaction)))
    except:
      log(f"Failed to add emoji {reaction}", "ERROR")
  return reply