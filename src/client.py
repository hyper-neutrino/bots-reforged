import asyncio, discord, json, re, shlex, time, traceback

from datamanager import config, get_data, has_data, set_data, load_data
from errors import BotError, DataError
from logs import log

with open("data/genshin.json", "r") as f:
  genshin_data = json.load(f)

def emojilist(key, count, sep = None):
  a = [emoji(key + str(i)) for i in range(1, count + 1)]
  if sep is None:
    return a
  return sep.join(map(str, a))

def charfield(characters):
  return {
    "name": "Characters",
    "value": "\n".join("- " + str(emoji("traveler" if cid.endswith("_mc") else cid)) + " " + cdata["name"] for cid, cdata in characters),
    "inline": False
  }

def charfilter(field, value):
  return [(cid, cdata) for cid, cdata in genshin_data["characters"].items() if cdata[field] == value]

async def add_char_reacts(msg, characters):
  for cid, _ in characters:
    await msg.add_reaction(emoji("traveler" if cid.endswith("_mc") else cid))

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
  
  def command(self, section, match, syntax, description, prefix = True):
    if prefix and isinstance(match, list):
      return lambda func: self.commands.append((section, [("pls", "please")] + match, "please " + syntax, description, func)) or func
    else:
      return lambda func: self.commands.append((section, match, syntax, description, func)) or func

  async def on_reaction_add(self, reaction, user):
    if user.id == self.user.id: return
    await self.nhentai_process(reaction)
    await self.genshin_info(reaction.emoji.name, reaction.message.channel)
  
  async def on_reaction_remove(self, reaction, user):
    if user.id == self.user.id: return
    await self.nhentai_process(reaction)
    await self.genshin_info(reaction.emoji.name, reaction.message.channel)

  async def genshin_info(self, name, channel):
    for key, value in genshin_data["talent_books"].items():
      if re.match(key + "\\d?", name):
        chars = [k for k in genshin_data["characters"] if genshin_data["characters"][k].get("talent_book") == key]
        if value["region"] == "mondstadt":
          chars.append("anemo_mc")
        elif value["region"] == "liyue":
          chars.append("geo_mc")
        msg = await channel.send(embed = discord.Embed(
          title = value["category_name"],
          description = f"{value['category_name']} can be farmed from {genshin_data['domains'][value['source']]['name']} in {genshin_data['regions'][value['region']]['name']}."
        ).add_field(
          name = "Items",
          value = f"- {emoji(key + '1')} Teachings of {value['name']}" + "\n" +
                  f"- {emoji(key + '2')} Guide to {value['name']}" + "\n" +
                  f"- {emoji(key + '3')} Philosophies of {value['name']}",
          inline = False
        ).add_field(
          **charfield([(k, genshin_data["characters"][k]) for k in chars])
        ).set_thumbnail(url = emoji(key + "2").url))
        await msg.add_reaction(emoji(value["region"]))
        for k in chars:
          await msg.add_reaction(emoji("traveler" if "_mc" in k else k))
        return
    for key, value in genshin_data["weapon_ascension"].items():
      if re.match(key + "\\d?", name):
        msg = await channel.send(embed = discord.Embed(
          title = value["category_name"],
          description = f"{value['category_name']} can be farmed from {genshin_data['domains'][value['source']]['name']} in {genshin_data['regions'][value['region']]['name']}." +
            "\n\nThere are four tiers to this item:\n" +
            "\n".join(f"- {emoji(key + str(i + 1))} {value['names'][i]}" for i in range(4))
        ).set_thumbnail(url = emoji(key + "3").url))
        await msg.add_reaction(emoji(value["region"]))
        return
    for key, value in genshin_data["characters"].items():
      if key == name:
        msg = await channel.send(embed = discord.Embed(
          title = value["name"],
          description = ""
        ).add_field(
          name = "Element",
          value = genshin_data["elements"][value["element"]] + " " + str(emoji(value["element"]))
        ).add_field(
          name = "Weapon",
          value = genshin_data["weapon_types"][value["weapon"]] + " " + str(emoji(value["weapon"]))
        ).add_field(
          name = "Rarity",
          value = "⭐" * value["tier"]
        ).add_field(
          name = "Region",
          value = genshin_data["regions"][value["region"]]["name"] + " " + str(emoji(value["region"]))
        ).add_field(
          name = "Birthday",
          value = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][value["birthmonth"]] + " " + str(value["birthdate"])
        ).add_field(
          name = "Constellation",
          value = value["constellation"]
        ).add_field(
          name = "Character Ascension Materials",
          value = "- " + genshin_data["elements"][value["element"]] + " Gem (" + genshin_data["ascension_gems"][value["element"]] + ") (" + "".join(str(emoji(value["element"] + k)) for k in ["_sliver", "_fragment", "_chunk", "_gemstone"]) + ")\n" +
                  "- " + genshin_data["elemental_materials"][value["boss_drop"]]["name"] + " (" + str(emoji(value["boss_drop"])) + ")\n" +
                  "- " + genshin_data["regional_specialties"][value["specialty"]]["name"] + " (" + str(emoji(value["specialty"])) + ")\n" +
                  "- " + genshin_data["general_ascension"][value["ascension"]]["category_name"] + " (" + emojilist(value["ascension"], 3, "") + ")" + "\n",
          inline = False
        ).add_field(
          name = "Talent Ascension Materials",
          value = "- " + genshin_data["talent_books"][value["talent_book"]]["category_name"] + " (" + emojilist(value["talent_book"], 3, "") + ")" + "\n" +
                  "- " + genshin_data["general_ascension"][value["talent_common"]]["category_name"] + " (" + emojilist(value["talent_common"], 3, "") + ")" + "\n",
          inline = False
        ).set_thumbnail(url = emoji(key).url))
        await msg.add_reaction(emoji(value["region"]))
        await msg.add_reaction(emoji(value["element"]))
        await msg.add_reaction(emoji(value["weapon"]))
        await msg.add_reaction(emoji(value["element"] + "_chunk"))
        await msg.add_reaction(emoji(value["boss_drop"]))
        await msg.add_reaction(emoji(value["specialty"]))
        await msg.add_reaction(emoji(value["talent_book"] + "2"))
        await msg.add_reaction(emoji(value["talent_common"] + "3"))
        await msg.add_reaction(emoji(value["ascension"] + "3"))
        return
    for key, value in genshin_data["elements"].items():
      if key == name:
        characters = charfilter("element", key)
        msg = await channel.send(embed = discord.Embed(
          title = value,
          description = ""
        ).add_field(
          **charfield(characters)
        ).add_field(
          name = "Ascension Gem",
          value = genshin_data["ascension_gems"][key] + " Sliver (" + str(emoji(key + "_sliver")) + ") / Fragment (" + str(emoji(key + "_fragment")) + ") / Chunk (" + str(emoji(key + "_chunk")) + ") / Gemstone (" + str(emoji(key + "_gemstone")) + ")",
          inline = False
        ).set_thumbnail(url = emoji(key).url))
        await msg.add_reaction(emoji(key + "_chunk"))
        await add_char_reacts(msg, characters)
        return
    for key, value in genshin_data["weapon_types"].items():
      if key == name:
        characters = charfilter("weapon", key)
        msg = await channel.send(embed = discord.Embed(
          title = value,
          description = ""
        ).add_field(
          **charfield(characters)
        ).set_thumbnail(url = emoji(key).url))
        await add_char_reacts(msg, characters)
        return
    for key, value in genshin_data["elements"].items():
      for suffix in ["_sliver", "_fragment", "_chunk", "_gemstone"]:
        if key + suffix == name:
          class_name = genshin_data["ascension_gems"][key]
          characters = charfilter("element", key)
          msg = await channel.send(embed = discord.Embed(
            title = value + " Ascension Gem (" + class_name + ")",
            description = ""
          ).add_field(
            name = "Items",
            value = "\n".join("- " + str(emoji(key + suffix)) + " " + class_name + " " + suffname for suffix, suffname in [("_sliver", "Sliver"), ("_fragment", "Fragment"), ("_chunk", "Chunk"), ("_gemstone", "Gemstone")])
          ).add_field(
            **charfield(characters)
          ).set_thumbnail(url = emoji(key + "_chunk").url))
          await msg.add_reaction(emoji(key))
          await add_char_reacts(msg, characters)
          return
    for key, value in genshin_data["elemental_materials"].items():
      if key == name:
        characters = charfilter("boss_drop", key)
        msg = await channel.send(embed = discord.Embed(
          title = value["name"] + " (Normal Boss Material)",
          description = value["name"] + " can be obtained from the " + value["boss"]
        ).add_field(
          **charfield(characters)
        ).set_thumbnail(url = emoji(key).url))
        await add_char_reacts(msg, characters)
        return
    for key, value in genshin_data["domains"].items():
      if key == name:
        embed = discord.Embed(
          title = value["name"],
          description = ""
        ).add_field(
          name = "Region",
          value = genshin_data["regions"][value["region"]]["name"] + " " + str(emoji(value["region"]))
        ).add_field(
          name = "Type",
          value = genshin_data["domain_types"][value["type"]]
        )
        er = []
        if value["type"] == "mastery":
          embed.add_field(
            name = "Drops",
            value = "\n".join("- [" + days + "] " + genshin_data["talent_books"][item]["category_name"] + " (" + emojilist(item, 3, "") + ")" for days, item in zip(["Mon/Thu/Sun", "Tue/Fri/Sun", "Wed/Sat/Sun"], value["drops"])),
            inline = False
          )
          er.extend(item + "2" for item in value["drops"])
        if value["type"] == "forgery":
          embed.add_field(
            name = "Drops",
            value = "\n".join("- [" + days + "] " + genshin_data["weapon_ascension"][item]["category_name"] + " (" + emojilist(item, 4, "") + ")" for days, item in zip(["Mon/Thu/Sun", "Tue/Fri/Sun", "Wed/Sat/Sun"], value["drops"])),
            inline = False
          )
          er.extend(item + "3" for item in value["drops"])
        msg = await channel.send(embed = embed)
        await msg.add_reaction(emoji(value["region"]))
        for e in er:
          await msg.add_reaction(emoji(e))
        return
    for key, value in genshin_data["regions"].items():
      if key == name:
        msg = await channel.send(embed = discord.Embed(
          title = value["name"],
          description = ""
        ).add_field(
          name = "Element",
          value = genshin_data["elements"][value["element"]] + " " + str(emoji(value["element"]))
        ).add_field(
          name = "Archon",
          value = value["archon"]
        ).add_field(
          name = "Governing Entity",
          value = value["government"]
        ).add_field(
          name = "Domains",
          value = "\n".join("- " + genshin_data["domain_types"][ddata["type"]] + ": " + ddata["name"] for did, ddata in genshin_data["domains"].items() if ddata["region"] == key)
        ).set_thumbnail(url = emoji(key).url))
        await msg.add_reaction(emoji(value["element"]))
        return
    
  async def nhentai_process(self, reaction):
    if await has_data("nhentai_embed", reaction.message.id):
      nhid, page = await get_data("nhentai_embed", reaction.message.id)
      title, subtitle, sauce, urls = await get_data("nhentai", nhid)
      if str(reaction.emoji) == "⬅️":
        page -= 1
        if page == -1: page = len(urls) - 1
      elif str(reaction.emoji) == "➡️":
        page += 1
        if page >= len(urls): page = 0
      else:
        return
      await reaction.message.edit(embed = discord.Embed(title = title + " " + subtitle, url = f"https://nhentai.net/g/{nhid}", description = f"Page {page + 1} / {len(urls)}").set_image(url = urls[page]))
      await set_data("nhentai_embed", reaction.message.id, (nhid, page))
  
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
          matched = command
          if matched:
            for m, c in zip(match, command):
              if m == c or m == "?" or type(m) in (list, tuple, set) and c in m:
                continue
              if m == "...":
                matched = True
                break
              matched = False
              break
            if len(command) > len(match) and "..." not in match:
              matched = False
            if len(command) < len(match) and not (len(command) + 1 == len(match) and match and match[-1] == "..."):
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
  for cid in await get_data("announcement_channels", default = set()):
    try:
      await client.get_channel(cid).send(*args, **kwargs)
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

next_slot = 0

async def send(message, *args, **kwargs):
  global next_slot
  if next_slot > time.time():
    async with message.channel.typing():
      await asyncio.sleep(next_slot - time.time())
      next_slot += 1
  else:
    next_slot = time.time() + 1
  if "embed" in kwargs:
    kwargs["embed"].set_footer(text = f"Requested by {message.author.display_name}")
  reply = await message.channel.send(*args, **{a: kwargs[a] for a in kwargs if a != "reaction"})
  if "reaction" in kwargs:
    if type(kwargs["reaction"]) == list:
      reaction_list = kwargs["reaction"]
    elif kwargs["reaction"] == "":
      reaction_list = []
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