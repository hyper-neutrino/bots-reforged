from commands import *

with open("data/krone.json", "r") as f:
  krone = json.load(f)

def show_title(title):
  return title and ", " + title

def display_char(character):
  return character["name"] + show_title(character.get("title", ""))

def rpgcommand(func):
  async def _inner(command, message):
    if not await has_rpg_data(message):
      return
    return await func(command, message)
  return _inner

def get_character(characters, x):
  matches = []
  for i, char in enumerate(characters):
    if str(i + 1) == x:
      return i
    if char["name"] == x or char["name"] + ", " + char["title"] == x:
      matches.append(i)
  if len(matches) == 0:
    raise BotError(f"Could not identify character '{x}'! Please check your spelling, or if you are accessing by index, that the character at that index exists.")
  elif len(matches) == 1:
    return matches[0]
  else:
    raise BotError(f"Found multiple characters matching '{x}'! Please access by index instead, or if possible, you can use the full <name>, <title>.")

def to_uid(user):
  if isinstance(user, int):
    return user
  return user.id

async def get_rpg_data(message, *a, **k):
  return await get_data("dungeons", message.channel.id, *a, **k)

async def get_player_data(message, *a, user = None, **k):
  return await get_data("dungeons", message.channel.id, "players", to_uid(user) if user else message.author.id, *a, **k)

async def set_rpg_data(message, *a, **k):
  return await set_data("dungeons", message.channel.id, *a, **k)

async def set_player_data(message, *a, user = None, **k):
  return await set_data("dungeons", message.channel.id, "players", to_uid(user) if user else message.author.id, *a, **k)

async def has_rpg_data(message, *a, **k):
  return await has_data("dungeons", message.channel.id, *a, **k)

async def has_player_data(message, *a, user = None, **k):
  return await has_data("dungeons", message.channel.id, "players", to_uid(user) if user else message.author.id, *a, **k)

async def del_rpg_data(message, *a, **k):
  return await del_data("dungeons", message.channel.id, *a, **k)

async def user_chars(message, user = None):
  return await get_player_data(message, "characters", user = user, default = [])

async def set_chars(message, characters, user = None):
  return await set_player_data(message, "characters", characters, user = user)

async def active_char(message, user = None):
  return await get_player_data(message, "active", user = user, default = 0)

async def set_active(message, active, user = None):
  return await set_player_data(message, "active", active, user = user)

async def get_combat_data(message, *a):
  return await get_rpg_data(message, "combat", *a, default = None)

async def set_combat_data(message, *a):
  return await set_rpg_data(message, "combat", *a)

async def has_combat_data(message, *a):
  return await has_rpg_data(message, "combat", *a)

async def get_active(message, user = None):
  characters = await user_chars(message, user = user)
  if not characters:
    raise BotError("You have no characters!")
  else:
    active = await active_char(message, user = user)
    if active >= len(characters):
      raise BotError(f"<@!{to_uid(user)}>'s active character position is out of bounds (this should not happen). Please manually switch the character in the meantime.")
    return characters[active]

async def mod_active(message, unit, user = None):
  characters = await user_chars(message, user = user)
  if not characters:
    raise BotError("You have no characters!")
  else:
    active = await active_char(message)
    if active >= len(characters):
      raise BotError("Your active character position is out of bounds (this should not happen). Please manually switch your character in the meantime.")
    return await set_player_data(message, "characters", active, unit, user = user)

async def base_combat_embed(message, combat):
  return discord.Embed(
    title = "Combat",
    description = "Players: " + " + ".join([display_char(await get_active(message, user = user)) for user in combat["teams"][1]]) +
    "\nEnemies: " + " + ".join(enemy["name"] for enemy in combat["enemies"].values())
  )

@client.command("", ["update", "combat"], "", "")
@rpgcommand
async def update_combat(command, message):
  if not await has_combat_data(message):
    return

  combat = await get_combat_data(message)
  
  unit_cache = {}
  async def get_unit(uid):
    if uid in unit_cache: return unit_cache[uid]
    if isinstance(uid, int):
      unit = await get_active(message, user = uid)
    else:
      unit = combat["enemies"][uid]
    unit_cache[uid] = unit
    return unit
    
  aid = combat["units"][0]
  actor = await get_unit(aid)
  
  triggers = {k: [[], [], [], []] for k in ["allturn", "turn", "instant", "normal", "counter", "reaction", "bonus"]}
  for uid in combat["units"]:
    unit = await get_unit(uid)
    for tid in unit["talents"]:
      talent = krone["talents"][tid]
      triggers[talent["trigger"]][isinstance(uid, int)].append((unit, tid))
      triggers[talent["trigger"]][2].append((unit, tid))
      if uid == aid:
        triggers[talent["trigger"]][3].append(tid)
  
  if combat["phase"] == 0:
    combat["casts"] = {uid: {
      "instant": 0,
      "normal": 0
    } for uid in combat["units"]}
    combat["skip"] = {}
    for unit, tid in triggers["allturn"][2]:
      await send(message, "TODO: Activate passive talent (all turns)", reaction = "")
    
    for unit, tid in triggers["turn"][2]:
      await send(message, "TODO: Activate passive talent (self turns)", reaction = "")
    
    await send(message, embed = (await base_combat_embed(message, combat)).add_field(name = "Order", value = " -> ".join([display_char(await get_unit(uid)) for uid in combat["units"]])), reaction = "")
    
    combat["phase"] = 1
  
  if combat["phase"] == 1:
    # TODO more sophisticated check for instant actions
    remainder = {unit["owner"] for unit, tid in triggers["instant"][1] if await has_action(message, unit["owner"]) and unit["charges"].get(tid, 0)}
    if remainder:
      await send(message, f"The following players may still cast instant actions: {english_list('<@!%d>' % unit for unit in remainder)}. Please cast an instant action or skip.", reaction = "")
      combat["waiting"] = remainder
      await set_rpg_data(message, "restriction", ["instant"])
    else:
      await send(message, "No more instant actions to cast; moving to the next phase.", reaction = "")
      combat["phase"] = 2
      combat["waiting"] = set()
      combat["skip"] = {}
      combat["casts"] = {u: {k: 0 for k in combat["casts"][u]} for u in combat["casts"]}
  
  if combat["phase"] == 2:
    if await has_action(message, aid) and any(actor["charges"].get(tid, 0) for tid in triggers["instant"][3] + triggers["normal"][3]):
      await send(message, f"<@!{aid}>: you may cast an instant or normal action/attack or skip.", reaction = "")
      combat["waiting"] = remainder
      await set_rpg_data(message, "restriction", ["instant", "normal"])
    else:
      await send(message, "Action complete; moving to the next phase.", reaction = "")
      combat["phase"] = 3
      combat["waiting"] = set()
      combat["skip"] = {}
      combat["casts"] = {u: {k: 0 for k in combat["casts"][u]} for u in combat["casts"]}
  
  if combat["phase"] == 3:
    combat["phase"] = 0
    combat["waiting"] = set()
    combat["skip"] = {}
    combat["casts"] = {u: {k: 0 for k in combat["casts"][u]} for u in combat["casts"]}
    combat["units"] = combat["units"][1:] + [combat["units"][0]]
    await set_combat_data(message, combat)
    await send(message, "Turn ended! Use `please update combat` to proceed to the next turn when you are ready.", reaction = "")
    return
  
  await set_combat_data(message, combat)

async def has_action(message, uid):
  if not await has_combat_data(message):
    return True
  combat = await get_combat_data(message)
  if combat["phase"] == 0:
    return False
  elif combat["phase"] == 1:
    return combat["casts"][uid]["instant"] < 1 and not combat["skip"].get(uid)
  else:
    return combat["casts"][uid]["normal"] < 1 and combat["casts"][uid]["instant"] < 1 and not combat["skip"].get(uid)

@client.command("Combat Commands", ["skip"], "skip", "skip your turn", prefix = False)
@rpgcommand
async def command_combat_skip(command, message):
  if not await has_combat_data(message):
    await send(message, "You cannot skip a turn (not in combat)!", reaction = "x")
  combat = await get_combat_data(message)
  if await has_action(message, message.author.id):
    combat["skip"][message.author.id] = True
    await set_combat_data(message, combat)
    await send(message, "Skipped your turn!")
    await update_combat([], message)
  else:
    await send(message, "You do not have a turn right now (ended or skipped)!", reaction = "x")

@client.command("Combat Commands", ["cast", "?", "..."], "cast <talent> [targets...]", "cast a talent", prefix = False)
@rpgcommand
async def command_combat_cast(command, message):
  character = await get_active(message)
  if command[1] in character["talents"]:
    talent = krone["talents"][command[1]]
    await cast_talent(message, message.author.id, character, command[1], parse_targets(talent["syntax"], command[2:]))
    await mod_active(message, character)
    if await has_combat_data(message):
      await update_combat([], message)
  else:
    await send(message, "Your character does not have that talent unlocked!", reaction = "")

async def cast_talent(message, uid, unit, tid, variables):
  charges = unit["charges"].get(tid, 0)
  talent = krone["talents"][tid]
  if charges == 0:
    await send(message, f"{display_char(unit)} does not have any charges of {talent['name']} left!", reaction = "")
  elif talent["trigger"] not in (await get_rpg_data(message, "restriction", default = ["instant", "normal", "bonus"])):
    await send(message, f"{talent['name']} cannot be cast at this time!", reaction = "")
  else:
    unit["charges"][tid] = max(-1, charges - 1)
    if await has_combat_data(message):
      combat = await get_combat_data(message)
      combat["casts"][uid][talent["trigger"]] += 1
      await set_combat_data(message, combat)
    await send(message, f"{display_char(unit)} cast {talent['name']}!", reaction = "")

def parse_targets(syntax, command):
  return {} # TODO

@client.command("RPG Commands", ["rpg", "create"], "rpg create", "convert this channel into an RPG channel")
async def command_rpg_create(command, message):
#   await set_rpg_data(message, {})
#   await send(message, "A Krone instance has been started in this channel!")
  pass

@client.command("RPG Commands", ["prep"], "prep", "prepare a set of actions; this is a debug command")
@rpgcommand
async def command_rpg_prep(command, message):
  character = await get_active(message)
  character["talents"] = ["battle-resilience", "instant-heal", "megumin-mega-explosion"]
  character["charges"] = {
    "battle-resilience": -1,
    "instant-heal": 1,
    "megumin-mega-explosion": 1
  }
  await mod_active(message, character)
  await send(message, "Prepped your debug config!")

@client.command("RPG Commands", ["talents"], "talents", "list your talents")
@rpgcommand
async def command_rpg_talents(command, message):
  character = await get_active(message)
  if character["talents"]:
    await send(message, f"{display_char(character)} - Talents\n" + "\n".join(f"{index + 1}. `{talent}`: {krone['talents'][talent]['name']} - {krone['talents'][talent]['description']}" for index, talent in enumerate(character["talents"])))
  else:
    await send(message, f"{display_char(character)} has no talents currently!")

@client.command("RPG Commands", ["fight"], "fight", "summon a basic enemy to fight; this is a debug command")
@rpgcommand
async def command_rpg_fight(command, message):
  if await has_combat_data(message):
    await send(message, "You are already in combat!", reaction = "x")
  else:
    combat = {"enemies": {"joe": {"name": "Joe", "level": 1, "hp": 100, "mhp": 100, "armor": 50, "shield": 10, "talents": [], "charges": [], "passives": [], "statuses": [], "damage_in": 1, "damage_out": 1, "heal_rate": 1, "loot": [(1, ["1 coin"])]}}}
    pcs = []
    for uid in await get_rpg_data(message, "players"):
      if await user_chars(message, user = uid):
        pcs.append(uid)
    if len(pcs) == 0:
      await send(message, "You cannot start a fight with no allies! Please create at least one character.", reaction = "x")
    else:
      npcs = list(combat["enemies"])
      units = pcs + npcs
      random.shuffle(units)
      combat["units"] = units
      combat["teams"] = (npcs, pcs)
      combat["phase"] = 0
      await set_combat_data(message, combat)
      await send(message, "Initialized a fight!")
      await update_combat(command, message)

@client.command("RPG Commands", ["end", "fight"], "end fight", "ends combat; this is a debug command")
@rpgcommand
async def command_rpg_end_fight(command, message):
  if await has_combat_data(message):
    await del_rpg_data(message, "combat")
    await send(message, "Combat ended!")
  else:
    await send(message, "You are not currently in combat!", reaction = "x")

@client.command("", ["create", "character", "?"], "", "")
@client.command("RPG Commands", ["create", "character", "?", "?"], "create character <name> [title]", "create an RPG character with a specified name and an optional title")
@rpgcommand
async def command_rpg_create_character(command, message):
  name = command[3]
  title = command[4] if len(command) == 5 else ""
  characters = await user_chars(message)
  characters.append({"name": name, "owner": message.author.id, "level": 1, "title": title, "hp": 100, "mhp": 100, "armor": 0, "shield": 0, "talents": [], "charges": [], "passives": [], "statuses": [], "damage_in": 1, "damage_out": 1, "heal_rate": 1, "mastery": {
    "magic": {"central": 0, "damage": 0, "defense": 0, "utility": 0, "healing": 0},
    "weaponry": {"central": 0, "heavy": 0, "light": 0, "bow": 0, "martial": 0},
    "defense": {"central": 0, "resistance": 0, "adaptation": 0, "resilience": 0, "alliance": 0},
    "elemental": {"central": 0, "damage": 0, "buff": 0, "debuff": 0, "resistance": 0}
  }})
  await set_chars(message, characters)
  await send(message, f"Welcome to Aevum, {name}{show_title(title)}! (You are {message.author.mention}'s character #{len(characters)})")

@client.command("RPG Commands", ["details", "?"], "details <x>", "show character details")
@rpgcommand
async def command_rpg_details(command, message):
  characters = await user_chars(message)
  x = get_character(characters, command[2])
  char = characters[x]
  await send(message, embed = discord.Embed(
    title = f"{message.author.display_name}'s #{x + 1}: {display_char(char)} (Level {char['level']})",
    description = f"""{char['hp']}/{char['mhp']} HP, {char['armor']} armor, {char['shield']} shields
takes {char['damage_in'] * 100}% damage, deals {char['damage_out'] * 100}% damage, healing is {char['heal_rate'] * 100}% effective""",
    color = client.color
  ).add_field(
    name = "Status Effects",
    value = f"{english_list(char['statuses']) if char['statuses'] else 'None'}",
    inline = False
  ).add_field(
    name = f"Mastery of Incantations - {char['mastery']['magic']['central']}",
    value = f"""Damage: {char['mastery']['magic']['damage']}
Defense: {char['mastery']['magic']['defense']}
Utility: {char['mastery']['magic']['utility']}
Healing: {char['mastery']['magic']['healing']}"""
  ).add_field(
    name = f"Mastery of Weaponry - {char['mastery']['weaponry']['central']}",
    value = f"""Heavy Melee: {char['mastery']['weaponry']['heavy']}
Light Melee: {char['mastery']['weaponry']['light']}
Artillery: {char['mastery']['weaponry']['bow']}
Martial Artist: {char['mastery']['weaponry']['martial']}"""
  ).add_field(
    name = f"Talent Slots - {len(char['talents'])}",
    value = "\n".join(f"{index + 1}. {krone['talents'][talent]['name']}" for index, talent in enumerate(char["talents"])) or "No talents yet!"
  ).add_field(
    name = f"Mastery of Defense - {char['mastery']['defense']['central']}",
    value = f"""Resistance: {char['mastery']['defense']['resistance']}
Adaptation: {char['mastery']['defense']['adaptation']}
Resilience: {char['mastery']['defense']['resilience']}
Team Tank: {char['mastery']['defense']['alliance']}"""
  ).add_field(
    name = f"Mastery of Elements - {char['mastery']['elemental']['central']}",
    value = f"""Damage: {char['mastery']['elemental']['damage']}
  Buffs: {char['mastery']['elemental']['buff']}
  Debuffs: {char['mastery']['elemental']['debuff']}
  Resistance: {char['mastery']['elemental']['resistance']}"""
  ).add_field(
    name = "Equipment",
    value = f"""Primary: TODO
Secondary: TODO
Armor: TODO
TODO"""
  ))

@client.command("", ["release", "?", "?"], "", "")
@client.command("RPG Commands", ["release", "?", "?", "?"], "release <id> <name> [title]", "release a character with the specified index; this is permanent, and you must input the exact name and title")
@rpgcommand
async def command_rpg_release(command, message):
  try:
    index = int(command[2]) - 1
    if index < 0: raise
    characters = await user_chars(message)
    if len(characters) <= index:
      await send(message, "Index is too high; you do not have that many characters!", reaction = "x")
    else:
      title = command[4] if len(command) == 5 else ""
      if characters[index]["name"] == command[3] and characters[index]["title"] == title:
        del characters[index]
        await set_chars(message, characters)
        active = await active_char(message)
        await set_active(message, max(0, min(active, len(characters) - 1)))
        await send(message, f"You are released from your duty. Farewell, {command[3]}{show_title(title)}!")
      else:
        await send(message, "Please enter your character's details exactly to release them!", reaction = "x")
  except:
    await send(message, "Please enter a positive integer index that is in range!", reaction = "x")

@client.command("RPG Commands", ["swap", "?", "?"], "swap <x> <y>", "switch character positions in your party")
@rpgcommand
async def command_rpg_swap(command, message):
  if await has_combat_data(message):
    await send(message, "You cannot perform that action in combat!", reaction = "x")
  else:
    characters = await user_chars(message)
    x = get_character(characters, command[2])
    y = get_character(characters, command[3])
    if x == y:
      await send(message, "Swapping a character with themselves. Nothing has changed.")
    else:
      characters[x], characters[y] = characters[y], characters[x]
      await set_chars(message, characters)
      active = await active_char(message)
      if active in [x, y]: active = x + y - active
      await set_active(message, active)
      await send(message, f"Swapped {characters[y]['name']} and {characters[x]['name']}!")

@client.command("RPG Commands", ["switch", "?"], "switch <x>", "switch your active character")
@rpgcommand
async def command_rpg_switch(command, message):
  if await has_combat_data(message):
    await send(message, "You cannot perform that action in combat!", reaction = "x")
  else:
    characters = await user_chars(message)
    x = get_character(characters, command[2])
    await set_active(message, x)
    await send(message, f"{message.author.mention} switched to {display_char(characters[x])}!")

@client.command("RPG Commands", ["list", ("my", "all"), "characters"], "list <my | all> characters", "list your characters or the whole party's characters")
@rpgcommand
async def command_rpg_list_characters(command, message):
  if command[2] == "my":
    characters = await user_chars(message)
    active = await active_char(message)
    if characters:
      msg = "Your characters are:"
      for key, character in enumerate(characters):
        msg += "\n" + f"{key + 1}. {display_char(character)}" + (" (active)" if key == active else "")
    else:
      msg = "You have no characters yet! Create one with `pls create character <name> [title]`."
    await send(message, msg)
  else:
    players = await get_rpg_data(message, "players", default = [])
    charmap = {}
    count = 0
    for key in players:
      charlist = await user_chars(message, user = key)
      if charlist:
        charmap[key] = charlist
        count += len(charlist)
    if count == 0:
      msg = "Nobody has any characters yet! Create one with `pls create character <name> [title]`."
    else:
      out = []
      for key in charmap:
        sub = client.get_user(key).display_name
        active = await active_char(message, user = key)
        for index, char in enumerate(charmap[key]):
          sub += "\n" + f"{index + 1}. {display_char(char)}" + (" (active)" if index == active else "")
        out.append(sub)
      msg = "\n\n".join(out)
    await send(message, msg)