import asyncio, datetime, discord, json, random, re, shlex, time, traceback

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
    "value": "\n".join("- " + str(emoji("traveler" if cid.endswith("_mc") else cid)) + " " + cdata["name"] for cid, cdata in characters) or "N/A",
    "inline": False
  }

def charfilter(field, value):
  return [(cid, cdata) for cid, cdata in genshin_data["characters"].items() if cdata[field] == value]

def enemydropfilter(id, type, group = False):
  return [(eid, edata) for eid, edata in genshin_data["enemy_groups" if group else "enemies"].items() if "drops" in edata and {"id": id, "type": type} in edata["drops"]]

async def add_char_reacts(msg, characters):
  for cid, _ in characters:
    await msg.add_reaction(emoji("traveler" if cid.endswith("_mc") else cid))

async def add_enemy_reacts(msg, enemies):
  for _, edata in enemies:
    await msg.add_reaction(emoji(edata["emoji"]))

def name_item(item, type):
  if type == "ascension_gems":
    return genshin_data["elements"][item] + " Ascension Gem (" + genshin_data["ascension_gems"][item] + ")"
  elif type == "elemental_materials":
    return genshin_data["elemental_materials"][item]["name"]
  elif type == "general_ascension":
    return genshin_data["general_ascension"][item]["category_name"]
  elif type == "regional_specialties":
    return genshin_data["regional_specialties"][item]["name"]
  elif type == "artifacts":
    data = genshin_data["artifacts"][item]
    return data["set_name"] + f" (Artifact Set)"
  else:
    return item + " [" + type + "]"

def emoji_item(item, type):
  if type == "ascension_gems":
    return item + "_chunk"
  elif type == "elemental_materials":
    return item
  elif type == "general_ascension":
    return item + "3"
  elif type == "regional_specialties":
    return item
  elif type == "artifacts":
    return item
  else:
    return "[??]"

def query(category, day, region):
  for key, value in genshin_data[category].items():
    if day in value["days"] and region == value["region"]:
      return (key, value)
  return ("null", {})

rome_numerals = {
  "M": 1000,
  "CM": 900,
  "D": 500,
  "CD": 400,
  "C": 100,
  "XC": 90,
  "L": 50,
  "XL": 40,
  "X": 10,
  "IX": 9,
  "V": 5,
  "IV": 4,
  "I": 1
}

def roman(n):
  if n == 0: return ""
  if n < 0: return "-" + roman(-n)
  for k in rome_numerals:
    if rome_numerals[k] <= n:
      return k + roman(n - rome_numerals[k])

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
    if user.id in await get_data("tsr"):
      await reaction.remove(user)
      return
    if user.id == self.user.id: return
    if reaction.emoji == "🗑️" and reaction.message.author == self.user:
      await reaction.message.delete()
    await self.nhentai_process(reaction)
    if type(reaction.emoji) != str:
      await self.genshin_info(reaction.emoji.name, reaction.message.channel)
  
  async def on_reaction_remove(self, reaction, user):
    if user.id == self.user.id: return
    await self.nhentai_process(reaction)
    if type(reaction.emoji) != str:
      await self.genshin_info(reaction.emoji.name, reaction.message.channel)
  
  async def genshin_daily(self, channel, wd):
    if wd == 6:
      await channel.send(embed = discord.Embed(
        title = "Sunday",
        description = "**All talent books and weapon ascension materials** are available for farming today; you may select the reward type you want before entering each Domain of Mastery and Forgery. If you wish to get details about these items, run `please genshin info <item>`."
      ))
    else:
      embed = discord.Embed(
        title = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][wd],
        description = "It is the weekly reset, so all bosses (Stormterror, Wolf of the North, Tartaglia) are available again." if wd == 0 else ""
      )
      el = []
      for region in genshin_data["regions"]:
        tid, tval = query("talent_books", wd, region)
        wid, wval = query("weapon_ascension", wd, region)
        el.append(emoji(f"{tid}2"))
        el.append(emoji(f"{wid}3"))
        te = [str(emoji(f"{tid}{i}")) for i in range(1, 4)]
        we = [str(emoji(f"{wid}{i}")) for i in range(1, 5)]
        embed.add_field(
          name = genshin_data["regions"][region]["name"],
          value = f"- {tval['category_name']} ({''.join(te)})" + "\n" +
                  f"- {wval['category_name']} ({''.join(we)})" + "\n",
          inline = False
        )
      msg = await channel.send(embed = embed)
      for e in el:
        await msg.add_reaction(e)

  async def genshin_info(self, name, channel):
    months = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for key, value in enumerate(weekdays):
      if value.lower() == name:
        await self.genshin_daily(channel, key)
    if name == "today":
      n = datetime.datetime.now()
      await self.genshin_daily(channel, (n.weekday() - (n.hour < 4)) % 7)
    for key, value in genshin_data["talent_books"].items():
      if re.match(key + "\\d?$", name):
        chars = [k for k in genshin_data["characters"] if genshin_data["characters"][k].get("talent_book") == key]
        if value["region"] == "mondstadt":
          chars.append("anemo_mc")
        elif value["region"] == "liyue":
          chars.append("geo_mc")
        msg = await channel.send(embed = discord.Embed(
          title = value["category_name"],
          description = f"{value['category_name']} can be farmed from {genshin_data['domains'][value['source']]['name']} in {genshin_data['regions'][value['region']]['name']} on {english_list(weekdays[x] for x in value['days'])}."
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
      if re.match(key + "\\d?$", name):
        msg = await channel.send(embed = discord.Embed(
          title = value["category_name"],
          description = f"{value['category_name']} can be farmed from {genshin_data['domains'][value['source']]['name']} in {genshin_data['regions'][value['region']]['name']} on {english_list(weekdays[x] for x in value['days'])}."
        ).add_field(
          name = "Items",
          value = "\n".join(f"- {emoji(key + str(i + 1))} {value['names'][i]}" for i in range(4))
        ).set_thumbnail(url = emoji(key + "3").url))
        await msg.add_reaction(emoji(value["region"]))
        return
    for key, value in genshin_data["characters"].items():
      if key == name:
        msg = await channel.send(embed = discord.Embed(
          title = value["name"],
          description = value["title"]
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
          name = "HP",
          value = str(value["stats"]["hp"])
        ).add_field(
          name = "ATK",
          value = str(value["stats"]["atk"])
        ).add_field(
          name = "DEF",
          value = str(value["stats"]["def"])
        ).add_field(
          name = value["stats"]["secondary_stat"],
          value = str(value["stats"]["secondary"]) + ("%" if value["stats"]["secondary_stat"] != "Elemental Mastery" else "")
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
        regions = [(rid, rdata) for rid, rdata in genshin_data["regions"].items() if rdata["element"] == key]
        msg = await channel.send(embed = discord.Embed(
          title = value,
          description = ""
        ).add_field(
          name = "Region",
          value = "\n".join(rdata["name"] for _, rdata in regions) or "N/A"
        ).add_field(
          **charfield(characters)
        ).add_field(
          name = "Ascension Gem",
          value = genshin_data["ascension_gems"][key] + " Sliver (" + str(emoji(key + "_sliver")) + ") / Fragment (" + str(emoji(key + "_fragment")) + ") / Chunk (" + str(emoji(key + "_chunk")) + ") / Gemstone (" + str(emoji(key + "_gemstone")) + ")",
          inline = False
        ).set_thumbnail(url = emoji(key).url))
        for rid, _ in regions:
          await msg.add_reaction(emoji(rid))
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
        elif value["type"] == "forgery":
          embed.add_field(
            name = "Drops",
            value = "\n".join("- [" + days + "] " + genshin_data["weapon_ascension"][item]["category_name"] + " (" + emojilist(item, 4, "") + ")" for days, item in zip(["Mon/Thu/Sun", "Tue/Fri/Sun", "Wed/Sat/Sun"], value["drops"])),
            inline = False
          )
          er.extend(item + "3" for item in value["drops"])
        elif value["type"] == "blessing":
          embed.add_field(
            name = "Drops",
            value = "\n".join(f"- {emoji(id)} {name_item(id, 'artifacts')}" for id in value["drops"]),
            inline = False
          )
          er.extend(value["drops"])
        eg = []
        for i, tier in enumerate(value["tiers"]):
          embed.add_field(
            name = f"{value['name']} {roman(i + 1)}",
            value = "__" + tier["objective"] + "__ " + tier["disorder"] + "\n" + "\n".join(f"**Wave {j + 1}**: " + ", ".join(str(emoji(edata["emoji"])) + " " + edata["name"] + " x " + str(count) for edata, count in [(genshin_data["enemies"][cluster["enemy"]], cluster["count"]) for cluster in wave]) for j, wave in enumerate(tier["waves"])),
            inline = False
          )
          for wave in tier["waves"]:
            for cluster in wave:
              group = genshin_data["enemies"][cluster["enemy"]]["group"]
              if group not in eg:
                eg.append(group)
        msg = await channel.send(embed = embed)
        await msg.add_reaction(emoji(value["region"]))
        for e in er:
          await msg.add_reaction(emoji(e))
        for g in eg:
          await msg.add_reaction(emoji(genshin_data["enemy_groups"][g]["emoji"]))
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
    for key, value in genshin_data["general_ascension"].items():
      if re.match(key + "\\d?$", name):
        characters = charfilter("talent_common", key)
        for q in charfilter("ascension", key):
          if q not in characters:
            characters.append(q)
        groups = enemydropfilter(key, "general_ascension", True)
        enemies = enemydropfilter(key, "general_ascension")
        msg = await channel.send(embed = discord.Embed(
          title = value["category_name"],
          description = ""
        ).add_field(
          name = "Items",
          value = "\n".join("- " + str(emoji(key + str(i + 1))) + " " + value["tiers"][i] for i in range(3))
        ).add_field(
          **charfield(characters)
        ).add_field(
          name = "Enemies",
          value = "\n".join(["- " + str(emoji(gdata["emoji"])) + " " + gdata["name"] + " (Group)" for gid, gdata in groups] + ["- " + str(emoji(edata["emoji"])) + " " + edata["name"] for eid, edata in enemies])
        ).set_thumbnail(url = emoji(key + "3").url))
        await add_char_reacts(msg, characters)
        await add_enemy_reacts(msg, groups + enemies)
        return
    for key, value in genshin_data["enemy_emoji_map"].items():
      if re.match(key + "$", name):
        id = value["id"]
        if value["group"]:
          group = genshin_data["enemy_groups"][id]
          embed = discord.Embed(
            title = group["name"] + " (Group)",
            description = ""
          )
          drops = group["drops"]
        else:
          enemy = genshin_data["enemies"][value["id"]]
          group = genshin_data["enemy_groups"][enemy["group"]]
          embed = discord.Embed(
            title = enemy["name"],
            description = ""
          ).add_field(
            name = "Group",
            value = group["name"]
          )
          drops = enemy.get("drops", []) + group.get("drops", [])
        embed = embed.add_field(
          name = "Faction",
          value = genshin_data["enemy_factions"][group["faction"]]
        ).add_field(
          name = "Tier",
          value = genshin_data["enemy_tiers"][group["type"]]
        ).add_field(
          name = "Drops",
          value = "\n".join("- " + str(emoji(emoji_item(drop["id"], drop["type"]))) + " " + name_item(drop["id"], drop["type"]) for drop in drops),
          inline = False
        )
        if value["group"]:
          embed = embed.add_field(
            name = "Enemies",
            value = "\n".join("- " + str(emoji(edata["emoji"])) + " " + edata["name"] for _, edata in genshin_data["enemies"].items() if edata["group"] == id),
            inline = False
          )
        try:
          embed.set_thumbnail(url = emoji(name).url)
        except:
          pass
        msg = await channel.send(embed = embed)
        for drop in drops:
          await msg.add_reaction(emoji(emoji_item(drop["id"], drop["type"])))
        return
    for key, value in genshin_data["artifacts"].items():
      if key == name:
        # TODO domain emojis
        sources = [("", val["name"]) for dkey, val in genshin_data["domains"].items() if key in val["drops"]] + \
                  [(emoji(val["emoji"]), val["name"]) for ekey, val in genshin_data["enemies"].items() if {"id": key, "type": "artifacts"} in val.get("drops", [])] + \
                  [(emoji(val["emoji"]), val["name"]) for gkey, val in genshin_data["enemy_groups"].items() if {"id": key, "type": "artifacts"} in val.get("drops", [])]
        msg = await channel.send(embed = discord.Embed(
          title = value["set_name"] + " (Artifact Set)",
          description = "⭐" * value["min_tier"] + " - " + "⭐" * value["max_tier"]
        ).add_field(
          name = "Artifact Names",
          value = "\n".join("- " + name for name in value["names"].values() if name),
          inline = False
        ).add_field(
          name = "Set Bonuses",
          value = "\n".join(f"{i}-piece bonus: {k}" for i, k in enumerate(value["set"]) if k) or "N/A",
          inline = False
        ).add_field(
          name = "Sources",
          value = "\n".join(f"- {emoji} {name}" for emoji, name in sources),
          inline = False
        ).set_thumbnail(url = emoji(key).url))
        for se, _ in sources:
          if se: await msg.add_reaction(se) # TODO remove the condition and fix the emojis
        return
    for key, value in genshin_data["regional_specialties"].items():
      if key == name:
        characters = charfilter("specialty", key)
        msg = await channel.send(embed = discord.Embed(
          title = value["name"],
          description = "Regional Specialty"
        ).add_field(
          name = "Region",
          value = genshin_data["regions"][value["region"]]["name"]
        ).add_field(
          **charfield(characters)
        ).set_thumbnail(url = emoji(key).url))
        await msg.add_reaction(emoji(value["region"]))
        await add_char_reacts(msg, characters)
        return
    for key, value in genshin_data["weapons"].items():
      if key == name:
        embed = discord.Embed(
          title = value["name"],
          description = ""
        ).add_field(
          name = "Type",
          value = genshin_data["weapon_types"][value["type"]] + " " + str(emoji(value["type"]))
        ).add_field(
          name = "Rarity",
          value = "⭐" * value["tier"]
        ).add_field(
          name = "Series",
          value = value["series"]
        ).add_field(
          name = "Sources",
          value = ", ".join(value["sources"]) or "N/A"
        ).add_field(
          name = "Max Level",
          value = "90/90" if value["tier"] >= 3 else "70/70"
        ).add_field(
          name = "Base ATK",
          value = value["base_atk"]
        )
        if value["tier"] >= 3:
          embed = embed.add_field(
            name = value["secondary_type"],
            value = str(value["secondary_stat"]) + ("%" if value["secondary_type"] != "Elemental Mastery" else "")
          ).add_field(
            name = value["passive_name"],
            value = value["passive"],
            inline = False
          )
        embed = embed.add_field(
          name = "Weapon Ascension Materials",
          value = "- " + genshin_data["weapon_ascension"][value["ascension"]]["category_name"] + " (" + emojilist(value["ascension"], 4, "") + ")\n" +
                  "- " + genshin_data["general_ascension"][value["material_1"]]["category_name"] + " (" + emojilist(value["material_1"], 3, "") + ")\n" +
                  "- " + genshin_data["general_ascension"][value["material_2"]]["category_name"] + " (" + emojilist(value["material_2"], 3, "") + ")" + "\n",
          inline = False
        )
        msg = await channel.send(embed = embed.set_thumbnail(url = emoji(key).url))
        await msg.add_reaction(emoji(value["type"]))
        await msg.add_reaction(emoji(value["ascension"] + "3"))
        await msg.add_reaction(emoji(value["material_1"] + "3"))
        await msg.add_reaction(emoji(value["material_2"] + "3"))
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
    if message.content == "👍":
      await message.add_reaction("😩")
      await message.add_reaction("👌")
    if message.content == "😩👌":
      await message.add_reaction("👍")
    if message.author == self.user and message.embeds:
      await message.add_reaction("🗑️")
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

def fuck_with(m):
  r = ""
  for c in m:
    if c == "b" and random.random() < 0.02:
      r += "🅱️"
    else:
      r += c
  return r

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
  reply = await message.channel.send(*map(fuck_with, args), **{a: kwargs[a] for a in kwargs if a != "reaction"})
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