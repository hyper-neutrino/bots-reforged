import asyncio, datetime, discord, json, pycountry, random, re, requests, time, traceback

from aioconsole import ainput

from word2number import w2n

from client import *
from datamanager import config, del_data, get_data, has_data, mod_data, set_data, batch_set_data
from discordutils import *
from league import *

async def dm(user, *a, **k):
  channel = user.dm_channel
  if channel is None:
    channel = await user.create_dm()
  await channel.send(*a, **k)

@client.command("", ["help"], "", "")
@client.command("General Commands", ["help", "rpg"], "help [rpg]", "post a list of commands")
async def command_help(command, message):
  sections = {}
  for section, _, syntax, description, _ in client.commands:
    if section == "" or ((section == "RPG Commands") ^ (len(command) == 3)): continue
    if section not in sections:
      sections[section] = []
    sections[section].append(f"`{syntax}` - {description}")
  
  embed = discord.Embed(
    title = "Help - Commands",
    color = client.color
  )
  
  for section in sections:
    embed.add_field(name = section, value = "\n".join(sections[section]), inline = False)
  
  await dm(message.author, embed = embed)
  await send(message, "Sent the command list to your DMs!")

@client.command("General Commands", ["ping"], "ping", "check your ping")
async def command_ping(command, message):
  ping = int((time.time() - (message.created_at - datetime.datetime(1970, 1, 1)) / datetime.timedelta(seconds = 1)) * 1000)
  await send(message, f"Pong! ({ping} ms)", reaction = "🏓")

@client.command("Channel Type Commands", ["subscribe"], "subscribe", "announce updates to this channel")
async def command_subscribe(command, message):
  await mod_data("announcement_channels", lambda x: x | {message.channel.id}, default = set())
  await send(message, "Subscribed to status updates here!")

@client.command("Channel Type Commands", ["unsubscribe"], "unsubscribe", "stop announcing updates to this channel")
async def command_unsubscribe(command, message):
  await mod_data("announcement_channels", lambda x: x - {message.channel.id}, default = set())
  await send(message, "Unsubscribed from status updates here!")

@client.command("Channel Type Commands", ["watch", ("osu", "genshin")], "watch osu/genshin", "watch osu!/Genshin Impact updates here")
async def command_watch(command, message):
  await mod_data("watch_channels", command[2], lambda x: x | {message.channel.id}, default = set())
  await send(message, "Now watching " + {"osu": "osu!", "genshin": "Genshin Impact"}[command[2]] + " updates in this channel!")

@client.command("Channel Type Commands", ["unwatch", ("osu", "genshin")], "unwatch osu/genshin", "stop watching osu!/Genshin Impact updates here")
async def command_watch(command, message):
  await mod_data("watch_channels", command[2], lambda x: x - {message.channel.id}, default = set())
  await send(message, "No longer watching " + {"osu": "osu!", "genshin": "Genshin Impact"}[command[2]] + " updates in this channel!")

words = None
wordmap = {}

with open("data/words.txt") as f:
  words = [x for x in f.read().strip().splitlines() if 5 <= len(x)]
for word in words:
  key = "".join(sorted(word))
  if key not in wordmap:
    wordmap[key] = set()
  wordmap[key].add(word)

anagram_lock = asyncio.Lock()

def display(actual, scrambled, hint):
  if hint == 0: return scrambled
  cl = list(scrambled)
  start = actual[:hint if hint * 2 <= len(actual) else -hint]
  end = actual[-hint:]
  for c in start + end:
    cl.remove(c)
  return f"**{start}**{''.join(cl)}**{end}**"

async def anagram_function(message, answer = None, start = False, stop = False, hint = False, reorder = False):
  global words, wordmap
  
  async with anagram_lock:
    active = await has_data("anagram", message.channel.id, "puzzle")
    puzzle = await get_data("anagram", message.channel.id, "puzzle", default = "", set_if_missing = False)
    answers = wordmap.get("".join(sorted(puzzle)), set())
    current_hint = await get_data("anagram", message.channel.id, "hint", default = 0, set_if_missing = False)

    if reorder:
      if active:
        charlist = list(puzzle)
        random.shuffle(charlist)
        puzzle = "".join(charlist)
        await set_data("anagram", message.channel.id, "puzzle", puzzle)
        await send(message, f"Reordered: solve for '{display(sorted(answers)[0], puzzle, current_hint)}' ({len(puzzle)}).")
      else:
        await send(message, "There is no ongoing anagram puzzle in this channel!", reaction = "x")
    
    if hint:
      if active:
        if len(puzzle) - current_hint * 2 - 2 <= 1:
          stop = True
        else:
          await set_data("anagram", message.channel.id, "hint", current_hint + 1)
          await send(message, f"Hint: 2 more letters shown: solve for '{display(sorted(answers)[0], puzzle, current_hint + 1)}' ({len(puzzle)}).")
      else:
        await send(message, "There is no ongoing anagram puzzle in this channel!", reaction = "x")
    
    if stop:
      if active:
        if len(answers) == 1:
          await send(message, f"Anagram puzzle ended! The correct answer was '{list(answers)[0]}'.")
        else:
          await send(message, f"Anagram puzzle ended! The correct answers were {english_list(quote(answers))}.")
        await del_data("anagram", message.channel.id)
        active = False
      else:
        await send(message, "There is no ongoing anagram puzzle in this channel!", reaction = "x")

    if active and answer in answers:
      try:
        points = len(answer) - 2 * await get_data("anagram", message.channel.id, "hint")
        bonus = int(points / 2) * (time.time() - await get_data("anagram", message.channel.id, "timestamp", default = 0) <= 5)
        await mod_data("leaderboard", "anagram", message.author.id, lambda x: x + points + bonus, default = 0)
        await batch_set_data("anagram", message.channel.id, active = False, last = answers, lasttime = time.time())
        active = False
        bonus_display = f" **+{bonus}**" if bonus else ""
        alt_display = f" (Alternative answers: {english_list(quote(answers - {answer}))})" if len(answers) > 1 else ""
        await send(message, f"Congratulations to {message.author.mention} for winning the anagram puzzle! (+{points}{bonus_display}){alt_display}", allowed_mentions = discord.AllowedMentions.none())
        start = True
      except:
        print(traceback.format_exc())
    elif answer in await get_data("anagram", message.channel.id, "last", default = set()) and time.time() - await get_data("anagram", message.channel.id, "lasttime", default = 0) <= 1:
      await send(message, f"{message.author.mention} L", reaction = "x", allowed_mentions = discord.AllowedMentions.none())

    if start:
      if active:
        hint = await get_data("anagram", message.channel.id, "hint", default = 0)
        actual = sorted(answers)[0]
        await send(message, f"An anagram puzzle is already running! Solve for '{display(actual, puzzle, hint)}' ({len(puzzle)}).", reaction = "x")
      else:
        word = random.choice(words)
        charlist = list(word)
        random.shuffle(charlist)
        scrambled = "".join(charlist)
        await batch_set_data("anagram", message.channel.id, active = True, puzzle = scrambled, hint = 0, timestamp = time.time())
        await send(message, f"Anagram puzzle! Solve for '{scrambled}' ({len(word)}).")

@client.command("Anagram Commands", ["anagram"], "anagram start", "start an anagram puzzle")
async def command_anagram_start(command, message):
  await anagram_function(message, start = True)

@client.command("Anagram Commands", ["anagram", "restart"], "anagram restart", "restart the anagram puzzle")
async def command_anagram_restart(command, message):
  await anagram_function(message, stop = True, start = True)

@client.command("Anagram Commands", ["anagram", "stop"], "anagram stop", "stop the anagram puzzle")
async def command_anagram_stop(command, message):
  await anagram_function(message, stop = True)

@client.command("Anagram Commands", ["anagram", "shuffle"], "anagram shuffle", "alias for `anagram reorder`")
@client.command("Anagram Commands", ["anagram", "scramble"], "anagram scramble", "alias for `anagram reorder`")
@client.command("Anagram Commands", ["anagram", "reorder"], "anagram reorder", "reorder the anagram puzzle")
async def command_anagram_reorder(command, message):
  await anagram_function(message, reorder = True)

@client.command("Anagram Commands", ["anagram", "hint"], "anagram hint", "show another character in the anagram puzzle")
async def command_anagram_hint(command, message):
  await anagram_function(message, hint = True)

@client.command("Anagram Commands", ["anagram", "add", "?"], "anagram add <word>", "add a word to the anagram dictionary")
async def command_anagram_add(command, message):
  global words, wordmap
  word = command[3].strip().lower()
  if all(char in "abcdefghijklmnopqrstuvwxyz" for char in word):
    if word in words:
      await send(message, "This word is already in the dictionary!", reaction = "x")
    else:
      words.append(word)
      words.sort()
      with open("data/words.txt", "w") as f:
        f.write("\n".join(words))
      key = "".join(sorted(word))
      if key not in wordmap:
        wordmap[key] = set()
      wordmap[key].add(word)
      await send(message, f"Added '{word}' to the dictionary!")
  else:
    await send(message, "Words must only contain letters!", reaction = "x")

@client.command("Anagram Commands", ["anagram", "rm", "?"], "anagram rm <word>", "alias for `anagram remove`")
@client.command("Anagram Commands", ["anagram", "remove", "?"], "anagram remove <word>", "remove a word from the anagram dictionary")
async def command_anagram_remove(command, message):
  global words, wordmap
  word = command[3].strip().lower()
  if word in words:
    words.remove(word)
    with open("data/words.txt", "w") as f:
      f.write("\n".join(words))
    key = "".join(sorted(word))
    wordmap[key].discard(word)
    await send(message, f"Removed '{word}' from the dictionary!")
  else:
    await send(message, "This word is not in the dictionary!", reaction = "x")

@client.command("Anagram Commands", ["anagram", "lb"], "anagram lb", "alias for `anagram leaderboard`")
@client.command("Anagram Commands", ["anagram", "leaderboard"], "anagram leaderboard", "show the leaderboard for the anagram puzzle")
async def command_anagram_leaderboard(command, message):
  scores = []
  scoremap = await get_data("leaderboard", "anagram")
  for member in message.guild.members:
    score = scoremap.get(member.id, 0)
    if score:
      scores.append((score, member))
  scores.sort(reverse = True)
  await send(message, embed = discord.Embed(
    title = "Leaderboard - Anagram",
    description = "\n".join(f"{member.mention} - {score}" for score, member in scores)
  ))

@client.command("", lambda m: True, "", "")
async def command_anagram_answer(command, message):
  try:
    await anagram_function(message, answer = message.content.strip().strip("!@#$%^&*()[]{}/|\.,<>\"'").lower())
  except:
    pass

@client.command("User Commands", ["alias", "?", "?"], "alias <name> <user>", "alias a name to a user")
async def command_alias(command, message):
  member = await get_member(message.guild, command[3], message.author)
  await set_data("aliases", message.guild.id, command[2].lower(), member.id)
  await send(message, f"Aliased '{command[2].lower()}' to {member.mention}!", allowed_mentions = discord.AllowedMentions.none())

@client.command("User Commands", ["unalias", "?"], "unalias <name>", "remove a name's alias")
async def command_unalias(command, message):
  await set_data("aliases", message.guild.id, command[2].lower(), None)
  await send(message, f"Removed the alias for '{command[2].lower()}'!")

@client.command("User Commands", ["unbonk", "?", "..."], "unbonk <user>", "alias for `unignore`")
@client.command("User Commands", ["unignore", "?", "..."], "unignore <user>", "make the bot no longer ignore messages from a particular user (on a server)")
@client.command("User Commands", ["bonk", "?", "..."], "bonk <user>", "alias for `ignore`")
@client.command("User Commands", ["ignore", "?", "..."], "ignore <user>", "make the bot ignore all messages from a particular user (on a server)")
async def command_ignore(command, message):
  for uinfo in command[2:]:
    member = await get_member(message.guild, uinfo, message.author)
    if not command[1].startswith("un") and member == message.author:
      await send(message, f"You cannot {command[1]} yourself!", reaction = "x")
    else:
      await set_data("ignore", message.guild.id, member.id, not command[1].startswith("un"))
      await send(message, f"No longer ignoring {member.mention}!" if command[1].startswith("un") else f"{'Bonk! ' * (command[1] == 'bonk')}Now ignoring {member.mention}!", allowed_mentions = discord.AllowedMentions.none())

@client.command("User Commands", ["unshut", "?", "..."], "unbonk <user>", "alias for `unsilence`")
@client.command("User Commands", ["unsilence", "?", "..."], "unignore <user>", "make the bot delete messages from a particular user (on a server)")
@client.command("User Commands", ["shut", "?", "..."], "bonk <user>", "alias for `silence`")
@client.command("User Commands", ["silence", "?", "..."], "ignore <user>", "make the bot delete messages from a particular user (on a server)")
async def command_silence(command, message):
  for uinfo in command[2:]:
    member = await get_member(message.guild, uinfo, message.author)
    if not command[1].startswith("un") and member == message.author:
      await send(message, f"You cannot {command[1]} yourself!", reaction = "x")
    else:
      await set_data("silence", message.guild.id, member.id, not command[1].startswith("un"))
      await send(message, f"No longer silencing {member.mention}!" if command[1].startswith("un") else f"{'https://i.redd.it/l5jmlb1ltqj51.jpg' * (command[1] == 'shut')}Now silencing {member.mention}!", allowed_mentions = discord.AllowedMentions.none())

# @client.command("Role Commands", ["gib", "?", "..."], "gib <name> [roles...]", "alias for `role give`")
# @client.command("Role Commands", ["role", "give", "?", "..."], "role give <name> [roles...]", "give a list of roles to a user")
# async def command_role_give(command, message):
#   user, *names = command[2 if command[1] == "gib" else 3:]
#   member = await get_member(message.guild, user, message.author)
#   roles = [get_role(message.guild, string) for string in names]
#   if any(role.id == 741731868692709416 for role in roles) and member.id != 251082987360223233:
#     await send(message, f"<@&741731868692709416> is exclusive to <@!251082987360223233>!", allowed_mentions = discord.AllowedMentions.none())
#   else:
#     await member.add_roles(*roles)
#     await send(message, f"Granted {english_list(quote(role.mention for role in roles))} to {member.mention}!", allowed_mentions = discord.AllowedMentions(roles = False))

# @client.command("Role Commands", ["gibnt", "?", "..."], "gibnt <name> [roles...]", "alias for `role remove`")
# @client.command("Role Commands", ["role", "remove", "?", "..."], "role remove <name> [roles...]", "remove a list of roles from a user")
# async def command_role_remove(command, message):
#   user, *names = command[2 if command[1] == "gibnt" else 3:]
#   member = await get_member(message.guild, user, message.author)
#   roles = [get_role(message.guild, string) for string in names]
#   await member.remove_roles(*roles)
#   await send(message, f"Removed {english_list(quote(role.mention for role in roles))} from {member.mention}!", allowed_mentions = discord.AllowedMentions(roles = False))

@client.command("", ["role", "colour", "?"], "", "")
@client.command("", ["role", "color", "?"], "", "")
@client.command("Role Commands", ["role", "colour", "?", "?"], "role colour <role> [colour = 0]", "alias for `role color`")
@client.command("Role Commands", ["role", "color", "?", "?"], "role color <role> [color = 0]", "recolor a role, or remove its color")
async def command_role_color(command, message):
  role = get_role(message.guild, command[3])
  await role.edit(color = get_color(command[4] if len(command) > 4 else "0"))
  await send(message, f"Recolored '{role.mention}'!", allowed_mentions = discord.AllowedMentions.none())

@client.command("Role Commands", ["role", "rename", "?", "?"], "role rename <role> <name>", "rename a role")
async def command_role_rename(command, message):
  role = get_role(message.guild, command[3])
  name = role.name
  await role.edit(name = command[4])
  await send(message, f"Renamed '{name}' to '{command[4]}'!")

services = {
  "lol": "lol",
  "league": "lol",
  "dmoj": "dmoj",
  "cf": "cf",
  "codeforces": "cf",
  "osu": "osu",
  "ow": "ow",
  "overwatch": "ow"
}

service_list = tuple(services)

@client.command("", [service_list, "link", "?"], "", "")
@client.command("External User Commands", [service_list, "link", "?", "?"], "<lol/league | cf/codeforces | dmoj | osu | ow/overwatch> link [user = me] <account>", "link a user to an external account")
async def command_link(command, message):
  service = services[command[1]]
  member = await get_member(message.guild, command[3] if len(command) == 5 else "me", message.author)
  await set_data("external", service, member.id, command[-1])
  await send(message, f"Linked {member.mention} to {command[-1]}!", allowed_mentions = discord.AllowedMentions.none())

@client.command("", [service_list, "unlink"], "", "")
@client.command("External User Commands", [service_list, "unlink", "?"], "<lol/league | cf/codeforces | dmoj | osu | ow/overwatch> unlink [user = me]", "unlink a user from a service")
async def command_link(command, message):
  service = services[command[1]]
  member = await get_member(message.guild, command[3] if len(command) == 4 else "me", message.author)
  await del_data("external", service, member.id)
  await send(message, f"Unlinked {member.mention}!", allowed_mentions = discord.AllowedMentions.none())

async def get_ext_user(key, error, command, message):
  if len(command) == 3:
    if await has_data("external", key, message.author.id):
      return await get_data("external", key, message.author.id)
    else:
      raise BotError(f"You are not linked; please specify {error} or link yourself first!")
  else:
    try:
      member = await get_member(message.guild, command[3], message.author)
      if await has_data("external", key, member.id):
        return await get_data("external", key, member.id)
    except:
      pass
  return command[3]

@client.command("", [("cf", "codeforces"), ("details", "rank", "rating")], "", "")
@client.command("External User Commands", [("cf", "codeforces"), ("details", "rank", "rating"), "?"], "cf/codeforces <details | rank/rating> [user = me]", "report a codeforces user's public details or just rank+rating")
async def command_cf_details(command, message):
  cf = await get_ext_user("cf", "a codeforces user", command, message)
  rv = requests.get("https://codeforces.com/api/user.info?handles=" + cf).json()
  if rv["status"] == "OK":
    cfdata = rv["result"][0]
    if command[2] == "rank" or command[2] == "rating":
      await send(message, f"{cf} is rank {cfdata['rank']} [{cfdata['rating']}] (max {cfdata['maxRank']} [{cfdata['maxRating']}])!")
    else:
      embed = discord.Embed(title = cf, color = client.color, url = "https://codeforces.com/profile/" + cf).set_thumbnail(url = "http:" + cfdata["avatar"])
      for key, name in [
        ("email", "Email Address"),
        ("firstName", "First Name"),
        ("lastName", "Last Name"),
        ("organization", "Organization"),
        ("contribution", "Contribution"),
        ("friendOfCount", "Friend Of #")
      ]:
        if cfdata.get(key):
          embed.add_field(name = name, value = str(cfdata[key]))
      if cfdata.get("country") or cfdata.get("city"):
        city = f"{cfdata['city']}, " if cfdata.get("city") else ""
        embed.add_field(name = "Location", value = f"{city}{cfdata['country']}")
      embed.add_field(name = "Current Rank", value = f"{cfdata['rank']} [{cfdata['rating']}]")
      embed.add_field(name = "Maximum Rank", value = f"{cfdata['maxRank']} [{cfdata['maxRating']}]")
      embed.add_field(name = "Registered Since", value = datetime.datetime.fromtimestamp(cfdata["registrationTimeSeconds"]).strftime("%B %d, %Y at %H:%M:%S"))
      embed.add_field(name = "Last Seen Online", value = datetime.datetime.fromtimestamp(cfdata["lastOnlineTimeSeconds"]).strftime("%B %d, %Y at %H:%M:%S"))
      await send(message, embed = embed)
  else:
    await send(message, f"'{cf}' is not a codeforces user!", reaction = "x")

def dmoj_api(URL):
  rv = requests.get(URL)
  if rv.status_code != 200:
    raise BotError(f"'{URL}' returned status {rv.status_code} (not 200)!")
  data = rv.json()
  if "error" in data:
    raise BotError("Error fetching from DMOJ API; likely item does not exist!")
  if "data" not in data:
    raise BotError("Data not found; check the URL!")
  return data["data"]

@client.command("", ["dmoj", ("details", "rank", "rating")], "", "")
@client.command("External User Commands", ["dmoj", ("details", "rank", "rating"), "?"], "dmoj <details | rank/rating> [user = me]", "report a DMOJ user's public details or just rank+rating")
async def command_dmoj_details(command, message):
  dm = await get_ext_user("dmoj", "a DMOJ user", command, message)
  dmdata = dmoj_api("https://dmoj.ca/api/v2/user/" + dm)["object"]
  rating = dmdata["rating"]
  if rating < 1000:
    rank = "Newbie"
  elif rating < 1200:
    rank = "Amateur"
  elif rating < 1500:
    rank = "Expert"
  elif rating < 1800:
    rank = "Candidate Master"
  elif rating < 2200:
    rank = "Master"
  elif rating < 3000:
    rank = "Grandmaster"
  else:
    rank = "Target"
  if dmdata["rank"] == "admin":
    rank += " (Admin)"
  if command[2] == "rank" or command[2] == "rating":
    await send(message, f"{dmdata['username']} is rank {rank} [{rating}]!")
  elif command[2] == "details":
    await send(message, embed = discord.Embed(
      title = dmdata["username"],
      color = 0x3333AA,
      url = "https://dmoj.ca/user/" + dmdata["username"]
    ).add_field(
      name = "Points",
      value = "%.2f" % dmdata["points"]
    ).add_field(
      name = "Solved Problems",
      value = str(dmdata["problem_count"])
    ).add_field(
      name = "Contests",
      value = str(len(dmdata["contests"]))
    ).add_field(
      name = "Organizations",
      value = ", ".join(org["short_name"] for org in dmoj_api("https://dmoj.ca/api/v2/organizations")["objects"] if org["id"] in dmdata["organizations"])
    ).add_field(
      name = "Rank",
      value = rank
    ).add_field(
      name = "Rating",
      value = str(rating)
    ))

@client.command("", ["osu", ("details", "summary")], "", "")
@client.command("External User Commands", ["osu", ("details", "summary"), "?"], "osu <details | summary> [player = me]", "report an osu player's public details or summary")
async def command_osu_details(command, message):
  osu = await get_ext_user("osu", "an osu! player", command, message)
  rv = requests.get(f"https://osu.ppy.sh/api/get_user?k={config['api-keys']['osu']}&u={osu}")
  if rv.status_code == 200:
    data = rv.json()
    if data == []:
      await send(message, "Could not find an osu! player by that username/ID!", reaction = "x")
    else:
      user = data[0]
      if command[2] == "summary":
        await send(message, embed = discord.Embed(title = f"osu! player details: {user['username']}", description = f"Level {user['level']}\nPP: {user['pp_raw']}\nRank: #{user['pp_rank']} (#{user['pp_country_rank']})\nAccuracy: {user['accuracy']}", color = client.color).set_thumbnail(url = f"http://s.ppy.sh/a/{user['user_id']}"))
      else:
        seconds = int(user["total_seconds_played"])
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        await send(message, embed = discord.Embed(
          title = f"osu! player summary: {user['username']} #{user['user_id']}",
          description = f"User since {user['join_date']}",
          url = f"https://osu.ppy.sh/users/{user['user_id']}",
          color = client.color
        ).add_field(
          name = "Level",
          value = user["level"]
        ).add_field(
          name = "Accuracy",
          value = user["accuracy"]
        ).add_field(
          name = "Performance Points",
          value = user["pp_raw"]
        ).add_field(
          name = "Rank",
          value = f"#{user['pp_rank']} (#{user['pp_country_rank']} in {pycountry.countries.get(alpha_2 = user['country']).name})"
        ).add_field(
          name = "Score Counts",
          value = " ".join(f"{user['count' + x]} {emoji('osu_' + x)}" for x in ["300", "100", "50"]),
          inline = False
        ).add_field(
          name = "Rating Counts",
          value = " ".join(f"{user['count_rank_' + x.lower()]} {emoji('osu_' + x)}" for x in ["SSH", "SS", "SH", "S", "A"]),
          inline = False
        ).add_field(
          name = "Best Score",
          value = user['ranked_score']
        ).add_field(
          name = "Total Score",
          value = user['total_score']
        ).add_field(
          name = "Time Played",
          value = f"{hours}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"
        ).set_thumbnail(
          url = f"http://s.ppy.sh/a/{user['user_id']}"
        ))
  else:
    await send(message, f"Failed to fetch from osu! API: status code {rv.status_code}!", reaction = "x")

def display_ow_rank(rating):
  try:
    rank = int(rating)
    if rank < 1500:
      e = "ow_bronze"
    elif rank < 2000:
      e = "ow_silver"
    elif rank < 2500:
      e = "ow_gold"
    elif rank < 3000:
      e = "ow_platinum"
    elif rank < 3500:
      e = "ow_diamond"
    elif rank < 4000:
      e = "ow_master"
    else:
      e = "ow_grandmaster"
    return f"{rating} {emoji(e)}"
  except:
    return rating

@client.command("", [("ow", "overwatch"), "summary"], "", "")
@client.command("External User Commands", [("ow", "overwatch"), "summary", "?"], "ow/overwatch summary <player = me>", "report an overwatch player's summary")
async def command_ow_summary(command, message):
  ow = await get_ext_user("ow", "a Blizzard battletag", command, message)
  try:
    r = requests.get(f"https://ow-api.com/v1/stats/pc/us/{ow}/profile")
    if r.status_code != 200:
      raise RuntimeError("Status Code not 200")
    data = r.json()
    try:
      await send(message, embed = discord.Embed(
        title = f"Overwatch player summary: {data['name']}",
        description = "",
        color = client.color
      ).add_field(
        name = "Level",
        value = str(data["level"] + 100 * data["prestige"])
      ).add_field(
        name = "Rating",
        value = display_ow_rank(data["rating"])
      ).add_field(
        name = "Games Won",
        value = str(data["gamesWon"])
      ).add_field(
        name = "Competitive Winrate",
        value = "%.2f%%" % (data["competitiveStats"]["games"]["won"] / data["competitiveStats"]["games"]["played"] * 100) if "games" in data["competitiveStats"] else "N/A"
      ).set_thumbnail(
        url = data["icon"]
      ))
    except:
      print(traceback.format_exc())
      await send(message, "Failed to generate embed!", reaction = "x")
  except:
    await send(message, f"Failed to fetch user data for `{ow}` from Overwatch API; check the spelling of this battletag (please format as `name-number`)!", reaction = "x")

@client.command("", [("lol", "league"), ("report", "current", "report-player", "current-player")], "", "")
@client.command("League of Legends Commands", [("lol", "league"), ("report", "current", "report-player", "current-player"), "?"], "lol/league <report | current>[-player] [player = me]", "create a game report for the player")
async def command_lol_report(command, message):
  sm = await get_ext_user("lol", "a League of Legends summoner", command, message)
  try:
    summoner = watcher.summoner.by_name(lol_region, sm)
    if command[2] == "report" or command[2] == "report-player":
      try:
        game = watcher.match.matchlist_by_account(lol_region, summoner["accountId"], end_index = 1)["matches"][0]
        try:
          if command[2] == "report":
            await send(message, embed = await lol_game_embed(message.guild, game["gameId"], sm, False), reaction = "check")
          elif command[2] == "report-player":
            await send(message, embed = await lol_player_embed(message.guild, game["gameId"], sm, False), reaction = "check")
        except:
          print(traceback.format_exc())
          await send(message, "Failed to create embed!", reaction = "x")
      except Exception as e:
        await send(message, f"Could not find a game for {lol_region.upper()}/{sm}! The summoner may not have played a proper game recently enough.", reaction = "x")
    else:
      try:
        game = watcher.spectator.by_summoner(lol_region, summoner["id"])
        try:
          if command[2] == "current":
            await send(message, embed = await lol_current_embed(message.guild, game, sm))
          elif command[2] == "current-player":
            await send(message, embed = await lol_current_player_embed(message.guild, game, [sm]))
        except:
          print(traceback.format_exc())
          await send(message, "Failed to create embed!", reaction = "x")
      except Exception as e:
        await send(message, f"Could not find current game for {lol_region.upper()}/{sm}! The summoner may not be in game.", reaction = "x")
  except:
    await send(message, f"Could not find summoner {lol_region.upper()}/{sm}! Please check your spelling.", reaction = "x")

@client.command("League of Legends Commands", [("lol", "league"), "rotation"], "lol/league rotation", "check the current free champion rotation")
async def command_lol_rotation(command, message):
  champions = [champs[cid] for cid in watcher.champion.rotations(lol_region)["freeChampionIds"]]
  champions.sort()
  await send(message, f"This week's free rotation is: {english_list(champions)}.")

@client.command("League of Legends Commands", [("lol", "league"), "ranges", "..."], "lol/league ranges <champion> [champion...]", "compare ability ranges for champions")
async def command_lol_ranges(command, message):
  champs = set()
  for champ in command[3:]:
    champ = champ.lower()
    if champ not in cmap:
      await send(message, f"{champ} is not a recognized champion name or ID!", reaction = "x")
      break
    champs.add(cmap[champ])
  else:
    items = []
    for champ in champs:
      data = requests.get(f"http://ddragon.leagueoflegends.com/cdn/{lol_version}/data/en_US/champion/{champ}.json").json()
      items.append((data["data"][champ]["stats"]["attackrange"], data["data"][champ]["name"], "Basic Attack"))
      for i, spell in enumerate(data["data"][champ]["spells"]):
        ident = data["data"][champ]["name"] + " " + ("QWER"[i] if 0 <= i < 4 else "?")
        if len(set(spell["range"])) == 1:
          items.append((spell["range"][0], ident, spell["name"]))
        else:
          clusters = {}
          for i, r in enumerate(spell["range"]):
            if r not in clusters:
              clusters[r] = []
            clusters[r].append(i + 1)
          for key in clusters:
            items.append((key, ident, spell["name"] + " Rank " + "/".join(map(str, clusters[key]))))
    items.sort()
    stacked = []
    for item in items:
      if stacked == [] or item[0] != stacked[-1][0]:
        stacked.append([item[0], []])
      stacked[-1][1].append((item[1], item[2]))
    info = "**Range Analysis**\n"
    for rng, stack in stacked:
      stack = ", ".join(f"{ident} ({name})" for ident, name in stack)
      info += f"\n__{rng}__: {stack}"
    await send(message, info, reaction = "check")

@client.command("League of Legends Commands", [("lol", "league"), "item", "?", "..."], "lol item <name>", "get details about an item")
async def command_lol_item(command, message):
  item = find_item("".join(command[3:]).lower())
  await send(message, embed = discord.Embed(
    title = f"League of Legends Item: {item['name']} (#{item['id']})",
    description = re.sub("(\\() (.)|(.) (\\))", "\\1\\2\\3\\4", re.sub(" +", " ", re.sub("<[^>]+?>", "", re.sub("<br>|<li>", "\n", item["description"])))),
    color = client.color,
    url = f"https://leagueoflegends.fandom.com/wiki/{item['name'].replace(' ', '_')}"
  ).add_field(
    name = "Build Path",
    value = build_path(item["id"]) + ("\n\nBuilds into: " + english_list(lolitems[key]["name"] for key in item.get("into")) if item.get("into") else "")
  ).add_field(
    name = "Tags",
    value = "\n".join("- " + {
      "CriticalStrike": "Critical Strike",
      "NonbootsMovement": "Movement Speed",
      "SpellDamage": "Ability Power",
      "MagicPenetration": "Magic Penetration",
      "ArmorPenetration": "Armor Penetration",
      "SpellBlock": "Magic Resistance",
      "Slow": "Movement Reduction",
      "Jungle": "Jungling",
      "Health": "Health",
      "Lane": "Laning",
      "Aura": "Aura",
      "HealthRegen": "Health Regeneration",
      "SpellVamp": "Spell Vamp",
      "GoldPer": "Gold Income",
      "Mana": "Mana",
      "Vision": "Vision",
      "LifeSteal": "Physical Vamp",
      "Consumable": "Consumable",
      "Armor": "Armor",
      "Stealth": "Stealth",
      "ManaRegen": "Mana Regeneration",
      "OnHit": "On-Hit",
      "Active": "Active",
      "CooldownReduction": "Cooldown Reduction",
      "Trinket": "Trinket",
      "AttackSpeed": "Attack Speed",
      "Boots": "Boots",
      "AbilityHaste": "Ability Haste",
      "Tenacity": "Tenacity",
      "Damage": "Attack Damage"
    }[tag] for tag in item["tags"])
  ).set_thumbnail(
    url = f"http://ddragon.leagueoflegends.com/cdn/{lol_version}/img/item/{item['id']}.png"
  ))

stats_length = 24

async def stats(channel, vis = None):
  counts = {}
  async for message in channel.history(limit = None):
    if not vis or message.author.id in vis:
      uinfo = f"{truncate(message.author.name, stats_length - 5)}#{message.author.discriminator}"
      counts[uinfo] = counts.get(uinfo, 0) + 1
  return sorted(counts.items(), key = lambda a: (-a[1], a[0]))

def truncate(string, length):
  if len(string) > length:
    return string[:length - 1] + "…"
  return string

@client.command("Server Statistics Commands", [("channel", "server"), "stats"], "<channel | server> stats", "output the number of messages sent in each channel by each user")
async def command_channel_stats(command, message):
  v = set(m.id for m in message.channel.members)
  async with message.channel.typing():
    if command[1] == "channel":
      s = await stats(message.channel, v)
      total = sum(b for _, b in s)
      mc = len(str(max(b for _, b in s)))
      l = max(len(a) for a, _ in s)
      await send(message, embed = discord.Embed(
        title = f"Channel Stats for #{message.channel.name}",
        description = "```\n" + "\n".join(f"{uinfo.ljust(l)}  {str(count).ljust(mc)} ({count / total * 100:.2f}%)" for uinfo, count in s) + "\n```",
        color = client.color
      ))
    else:
      vis = set(message.channel.members)
      counts = {}
      ccount = {}
      cname = {}
      total = 0
      failed = 0
      for channel in message.guild.channels:
        try:
          if isinstance(channel, discord.TextChannel):
            if set(channel.members) >= vis:
              cname[channel.id] = channel.name
              for uinfo, count in await stats(channel, v):
                counts[uinfo] = counts.get(uinfo, 0) + count
                ccount[channel.id] = ccount.get(channel.id, 0) + count
                total += count
        except:
          failed += 1
      mc = len(str(max(max(counts.values()), max(ccount.values()))))
      ul = max(map(len, counts))
      cl = max(map(len, cname.values()))
      l = min(max(ul, cl), stats_length)
      counts = sorted(counts.items(), key = lambda a: (-a[1], a[0]))
      ccount = sorted(ccount.items(), key = lambda a: (-a[1], a[0]))
      await send(message, embed = discord.Embed(
        title = f"Server Stats for {message.guild.name}",
        description = "```\n" + "\n".join(f"{uinfo.ljust(l)}  {str(count).ljust(mc)} ({count / total * 100:.2f}%)" for uinfo, count in counts) +
                      "\n\n" + "\n".join(f"#{truncate(cname[cid].ljust(l - 1), stats_length - 1)}  {str(count).ljust(mc)} ({count / total:.2f}%)" for cid, count in ccount) + "\n```",
        color = client.color
      ))
      if failed:
        await send(message, f"Failed to index the results from {failed} channel{'s' * (failed != 1)}; likely this bot does not have permission to access them.")

@client.command("Miscellaneous Commands", ["blame"], "blame", "blame a random person in this channel (cannot blame any bots)")
async def command_blame(command, message):
  members = []
  for member in message.channel.members:
    if not member.bot:
      members.append(member)
  await send(message, f"It was {random.choice(members).mention}'s fault!", allowed_mentions = discord.AllowedMentions.none())

@client.command("Miscellaneous Commands", ["spoiler", "image"], "spoiler image", "accept an image in a DM to spoiler (for mobile users)")
async def command_spoiler_image(command, message):
  try:
    await dm(message.author, f"The next image(s) you DM to me will be sent to {message.guild.name}#{message.channel.name} as a spoiler.")
    await message.delete()
    await set_data("dm_spoiler", message.author.id, message.channel.id)
  except:
    await send(message, "You need to allow me to DM you to use this feature!", reaction = "x")

@client.command("Miscellaneous Commands", ["color", "image"], "color image", "auto-color the next image you send in this channel with DeepAI")
async def command_spoiler_image(command, message):
  await send(message, f"The next image you send in this channel will be automatically colored with the power of Artificial Intelligence.")
  await set_data("img_color", message.author.id, message.channel.id, 0)

async def nhentai(nhid, force = False):
  if force or not await has_data("nhentai", nhid):
    response = requests.get(f"https://nhentai.net/g/{nhid}")
    if response.status_code == 404:
      raise BotError("404 Not Found!")
    elif response.status_code == 200:
      t = response.text
      urls = {x.replace("t.", "i.", 1).replace("t.", ".") for x in re.findall("https://t\\.nhentai\\.net/galleries/\\d+/\\d+t\\.\\w+", t)}
      urls = sorted(urls, key = lambda s: [int(x) for x in re.findall("\\d+", s)])
      title = re.findall("<span class=\"pretty\">\\s*(.+?)\\s*</span>", t)[0]
      subtitle = re.findall("<span class=\"after\">\\s*(.+?)\\s*</span>", t)[0]
      sauce = int(re.findall("\\d+", urls[0])[0])
      await set_data("nhentai", nhid, (title, subtitle, sauce, urls))
      return (title, subtitle, sauce, urls)
    else:
      raise BotError(f"Unknown error: {response.status_code}")
  else:
    return await get_data("nhentai", nhid)

@client.command("Genshin Commands", ["genshin", "info", "..."], "genshin info <item>", "get info on an item (must enter the internal ID; ask a developer if unsure but it's not too counterintuitive)")
async def command_genshin_info(command, message):
  item = " ".join(command[3:]).lower()
  await client.genshin_info(item, message.channel)
  await message.add_reaction("✅")

async def resin_set(user, amt):
  await set_data("genshin", "resin_info", user.id, time.time() - 8 * 60 * amt)

async def resin_rmd(user):
  return await get_data("genshin", "resin_reminder", user.id, default = -1)

async def resin_amount(uid):
  if await has_data("genshin", "resin_info", uid):
    return min(160, (time.time() - await get_data("genshin", "resin_info", uid)) / 8 / 60)
  else:
    return -1

def hm(s):
  h, m = divmod(int(s // 60), 60)
  return str(h) + "h" + str(m).zfill(2) if h else str(m) + "m"

@client.command("Genshin Commands", ["genshin", "resin", "set", "?"], "genshin resin set <amount>", "tell me how much resin you currently have")
async def command_genshin_resin_set(command, message):
  amt = int(command[4])
  await resin_set(message.author, amt)
  cur = await resin_rmd(message.author)
  msg = await send(message, "Set your resin!" + ("" if cur == -1 else f" Your existing reminder, set for {cur} resin, will occur in {hm(8 * 60 * (cur - amt))}."))
  if message.guild:
    await message.delete(delay = 5)
    await msg.delete(delay = 5)

@client.command("Genshin Commands", ["genshin", "resin", "now"], "genshin resin now", "check how much resin you currently have")
async def command_genshin_resin_now(command, message):
  amt = await resin_amount(message.author.id)
  cur = await resin_rmd(message.author)
  if amt == -1:
    await send(message, "You haven't told me how much resin you have yet!", reaction = "x")
  else:
    await send(message, f"You currently have {int(amt)} resin!" + ("" if cur == -1 else f" Your reminder, set for {cur} resin, will occur in {hm(8 * 60 * (cur - amt))}."))

@client.command("Genshin Commands", ["genshin", "resin", "reminder"], "genshin resin reminder [[amount] <desired = 160>] / stop", "set / stop a reminder for when you reach a specific amount of resin; your current amount is optional if you've already set your resin amount")
@client.command("", ["genshin", "resin", "reminder", "?"], "", "")
@client.command("", ["genshin", "resin", "reminder", "?", "?"], "", "")
async def command_genshin_resin_reminder(command, message):
  if len(command) == 5 and command[4] == "stop":
    msg = await send(message, "I will no longer remind you about your resin!")
    await del_data("genshin", "resin_reminder", message.author.id)
  else:  
    if len(command) <= 5:
      if not await has_data("genshin", "resin_info", message.author.id):
        raise BotError("You need to tell me how much resin you have with `genshin resin set` or specify the amount you currently have!")
      des = int(command[4]) if len(command) == 5 else 160
      amt = await resin_amount(message.author.id)
    else:
      amt = int(command[4])
      await resin_set(message.author, amt)
      des = int(command[5])
    if des > 160:
      raise BotError("You cannot have more than 160 resin without using Fragile Resin to exceed that cap manually!")
    if des <= amt:
      raise BotError("You already have that much resin!")
    cur = await resin_rmd(message.author)
    if cur == -1:
      msg = await send(message, f"I will remind you when you reach {des} resin (in {hm(8 * 60 * (des - amt))})!")
    else:
      msg = await send(message, f"You previously had a reminder for when you reached {cur} resin; I will instead remind you when you reach {des} (in {hm(8 * 60 * (des - amt))})!")
    await set_data("genshin", "resin_reminder", message.author.id, des)
  if message.guild:
    await message.delete(delay = 5)
    await msg.delete(delay = 5)

@client.command("", [("nhentai", "fnhentai"), "?"], "", "")
async def command_nhentai(command, message):
  nhid = int(command[2])
  title, subtitle, sauce, urls = await nhentai(nhid, command[1] == "fnhentai")
  reply = await send(message, embed = discord.Embed(title = title + " " + subtitle, url = f"https://nhentai.net/g/{nhid}", description = f"Page 1 / {len(urls)}").set_image(url = urls[0]))
  await reply.add_reaction("⬅️")
  await reply.add_reaction("➡️")
  await set_data("nhentai_embed", reply.id, (nhid, 0))

import httpx
import img2pdf, os
from PIL import Image
from PyPDF3 import PdfFileMerger
from io import BytesIO

async def get_async(url):
  async with httpx.AsyncClient() as client:
    return await client.get(url)

@client.command("", ["nhdownload", "?"], "", "")
async def command_nhdownload(command, message):
  async with message.channel.typing():
    nhid = int(command[2])
    title, subtitle, sauce, urls = await nhentai(nhid, True)
    try:
      os.mkdir(f"/tmp/{nhid}")
    except:
      pass
    merger = PdfFileMerger()
    responses = await asyncio.gather(*map(get_async, urls))
    for page, r in enumerate(responses):
      pdf_path = f"/tmp/{nhid}/{page}.pdf"
      pdf_bytes = img2pdf.convert(r.content)
      with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
      merger.append(pdf_path)
    final_path = f"/tmp/{nhid}/final.pdf"
    merger.write(final_path)
    merger.close()
    try:
      with open(final_path, "rb") as f:
        await send(message, file = discord.File(fp = f, filename = f"[{nhid}] {title}.pdf"))
    except:
      await send(message, f"The file is too large to upload; you can access it here: https://dev.hyper-neutrino.xyz/nh/{nhid}")

@client.command("", lambda m: True, "", "")
async def command_image_spoiler_reply(command, message):
  if type(message.channel) == discord.DMChannel:
    if len(message.attachments) > 0:
      if await has_data("dm_spoiler", message.author.id):
        await client.get_channel(await get_data("dm_spoiler", message.author.id)).send(files = [(await attachment.to_file(spoiler = True)) for attachment in message.attachments])
        await del_data("dm_spoiler", message.author.id)

@client.command("", lambda m: True, "", "")
async def command_image_spoiler_reply(command, message):
  if len(message.attachments) > 0:
    if await has_data("img_color", message.author.id, message.channel.id):
      r = requests.post("https://api.deepai.org/api/colorizer", data = {"image": message.attachments[0].url}, headers = {"api-key": "551549c3-8d2c-426b-ae9f-9211b13e6f14"})
      await send(message, r.json()["output_url"])
      await del_data("img_color", message.author.id, message.channel.id)

@client.command("", ["echo", "..."], "echo <message>", "echo the message")
async def command_echo(command, message):
  await send(message, message.content[message.content.find("echo") + 4:])

@client.command("", ["say", "..."], "say <message>", "echo, then immediately delete the command")
async def command_say(command, message):
  await send(message, message.content[message.content.find("say") + 3:])
  await message.delete()

@client.command("", ["eval", "?", "..."], "eval <expr>", "evaluate a Python expression in a command function's scope")
async def command_eval(command, message):
  if message.author.id not in config["sudo"]:
    await send(message, "You must be a sudo user to do that!", reaction = "x")
  else:
    try:
      code = message.content[message.content.find("eval") + 4:].strip()
      if code.startswith("```python"):
        code = code[9:]
      elif code.startswith("```py"):
        code = code[5:]
      code = code.strip("`")
      await send(message, str(eval(code))[:2000])
    except:
      await send(message, "Error evaluating expression!", reaction = "x")

@client.command("", ["exec", "?", "..."], "exec <code>", "execute Python code in a command function's scope (print is replaced with message output)")
async def command_exec(command, message):
  if message.author.id not in config["sudo"]:
    await send(message, "You must be a sudo user to do that!", reaction = "x")
  else:
    try:
      code = message.content[message.content.find("exec") + 4:].strip()
      if code.startswith("```python"):
        code = code[9:]
      elif code.startswith("```py"):
        code = code[5:]
      code = code.strip("`")
      output = []
      def print(*items, end = "\n", sep = " "):
        output.extend(list(sep.join(map(str, items)) + end))
      exec(code)
      await send(message, "```python\n" + "".join(output[:1980]) + "\n```")
    except:
      await send(message, "Error executing expression!", reaction = "x")

@client.command("", ["adjust", "ehecd", "?"], "adjust ehecd <x>", "adjust the cooldown of ehe te nandayo")
async def command_exec(command, message):
  if message.author.id not in config["sudo"]:
    await send(message, "You must be a sudo user to do that!", reaction = "x")
  else:
    try:
      await set_data("ehecd", int(command[3]))
      await send(message, f"Cooldown of 'ehe te nandayo' is now {command[3]} second{'s' * (command[3] != '1')}!")
    except:
      await send(message, "Error; make sure you entered an integer!", reaction = "x")

@client.command("", ["data", "..."], "data", "fetch data from the bot")
async def command_data(command, message):
  if message.author.id not in config["sudo"]:
    await send(message, "You must be a sudo user to do that!")
  else:
    await send(message, "```python\n" + str(await get_data(*map(eval, command[2:]), default = None, set_if_missing = False))[:1980] + "\n```")

@client.command("", ["identify", "?"], "identify <user>", "identify a user")
async def command_identify(command, message):
  member = await get_member(message.guild, command[2], message.author)
  await send(message, f"Identified {member.name}#{member.discriminator}, a.k.a {member.display_name}, I.D. {member.id} ({member.mention})", allowed_mentions = discord.AllowedMentions.none())

@client.command("", ["emoji", "?", "-"], "", "")
@client.command("", ["emoji", "?"], "emoji <lookup> [-]", "post an emoji by lookup ID")
async def command_emoji(command, message):
  try:
    await send(message, str(emoji(command[2])))
    if len(command) == 4:
      await message.delete()
  except:
    await send(message, "That resulted in an error.", reaction = "x")
    raise

@client.command("", [("summary", "summarize"), "?"], "", "")
@client.command("", [("summary", "summarize"), "?", "?"], "", "")
@client.command("", [("summary", "summarize"), "?", "?", "?"], "", "")
async def command_summarize(command, message):
  url = command[2]
  if url[0] == "<" and url[-1] == ">":
    url = url[1:-1]
  await message.edit(suppress = True)
  rurl = f"https://api.smmry.com/?SM_API_KEY={config['api-keys']['sm']}"
  if len(command) >= 4:
    rurl += "&SM_LENGTH=" + command[3]
  if len(command) >= 5:
    rurl += "&SM_KEYWORD_COUNT=" + command[4]
  rurl += "&SM_URL=" + url
  r = requests.get(rurl)
  data = r.json()
  if "sm_api_error" in data:
    error = data["sm_api_error"]
    if error == 0:
      await send(message, "Internal server problem with the SMMRY API; this is not your fault. Try again later.", reaction = "x")
    elif error == 1:
      await send(message, "Parameters are invalid. Check that you entered a real URL; otherwise, contact a developer.", reaction = "x")
    elif error == 2:
      await send(message, "This request has intentionally been restricted. Perhaps you have expended the API key's limit (100 per day).", reaction = "x")
    elif error == 3:
      await send(message, "Summarization error. This website might not be summarizable.")
  else:
    await send(message, (f"**{data['sm_api_title'].strip() or '(no title)'}**\n\n{data['sm_api_content'].strip() or '(no content)'}")[:2000])
    if "sm_api_keyword_array" in data:
      await message.channel.send(f"**Keywords**: {', '.join(data['sm_api_keyword_array'])}")

@client.command("", ["tsr", "?"], "", "")
async def command_toggle_suppress_reacts(command, message):
  member = await get_member(message.guild, command[2], message.author)
  await mod_data("tsr", lambda x: x ^ {member.id}, default = set())
  await message.add_reaction("✅")

@client.command("", ["react", "..."], "", "")
async def command_react(command, message):
  if not message.reference or not message.reference.resolved:
    raise BotError("You need to refer to a message via reply!")
  fails = []
  for x in command[2:]:
    try:
      await message.reference.resolved.add_reaction(emoji(x))
    except:
      fails.append(x)
  if fails:
    await send(message, "The following emojis do not exist / could not have been added: " + ", ".join(fails))
  else:
    await message.delete()

# @client.command("", re.compile(r"\b[hH]?[eE][hH][eE]\b").search, "", "")
async def command_ehe_te_nandayo(command, message):
  if message.author != client.user and time.time() - await get_data("ehe", message.author.id, default = 0) > (await get_data("ehecd", default = 30)):
    await send(message, "**ehe te nandayo!?**", reaction = "?")
    await set_data("ehe", message.author.id, time.time())

# @client.command("", re.compile(r"\[\w+\]").search, "", "")
async def command_emoji_react(command, message):
  for c in re.findall(r"\[(\w+)\]", message.content):
    try:
      await message.add_reaction(emoji(c))
    except:
      pass

# @client.command("", re.compile(r"\b[Aa][Oo][Cc]\b").search, "", "")
async def command_aoc(command, message):
  await message.channel.send("Alexandria Ocasio-Cortez")

# @client.command("", ["toggle69"], "", "")
async def command_toggle69(command, message):
  await set_data("disable_69", not await get_data("disable_69", default = False))
  await message.add_reaction("✅")

# @client.command("", re.compile(r"\b69\b").search, "", "")
async def command_69(command, message):
  if await get_data("disable_69", default = False):
    return
  await message.reply("nice", mention_author = False)