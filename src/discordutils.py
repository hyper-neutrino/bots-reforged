import discord, re, string

from datamanager import get_data
from errors import BotError

async def get_member(guild, string, caller = None):
  if isinstance(string, int):
    for member in guild.members:
      if member.id == string:
        return member
  match = None
  for member in guild.members:
    if member.display_name == string or member.name == string:
      if match is not None:
        raise BotError("Found multiple users with that nickname/username; please narrow your search with a discriminator or by tagging the user.")
      match = member
  if match is not None:
    return match
  if re.match(r"^[^#]+#\d{4}$", string):
    username, discriminator = string.split("#")
    for member in guild.members:
      if member.name == username and member.discriminator == discriminator:
        return member
  elif re.match(r"<@!\d+>", string):
    uid = int(string[3:-1])
    for member in guild.members:
      if member.id == uid:
        return member
  elif re.match(r"<@&\d+>", string):
    rid = int(string[3:-1])
    found = None
    for member in guild.members:
      if rid in [role.id for role in member.roles]:
        if found:
          raise BotError("Cannot identify a user by role if the role has multiple users!")
        found = member
    if found:
      return found
    else:
      raise BotError("Cannot identify a user by a role if the role has no users!")
  elif string.lower() == "me" or string.lower() == "myself":
    if caller is None:
      raise BotError("Could not use `me` as a user identifier since no caller was passed!")
    return caller
  alias = await get_data("aliases", guild.id, string.lower())
  if alias is not None:
    return await guild.fetch_member(await get_data("aliases", guild.id, string.lower()))
  raise BotError("Found no users with that identity; please check your spelling.")

def get_role(guild, string):
  match = None
  for role in guild.roles:
    if role.name == string:
      if match:
        raise BotError(f"Found multiple roles called '{string}'")
      match = role
  if match is not None:
    return match
  elif re.match(r"<@&\d+>", string):
    rid = string[3:-1]
    for role in guild.roles:
      if str(role.id) == rid:
        return role
  raise BotError(f"Found no roles called '{string}'.")

def get_channel(guild, string):
  match = None
  for channel in guild.channels:
    if channel.name == string:
      if match:
        raise BotError(f"Found multiple channels called '{string}'")
      match = role
  if match is not None:
    return match
  elif re.match(r"<#\d+>", string):
    cid = string[2:-1]
    for channel in guild.channels:
      if str(channel.id) == cid:
        return channel
  raise BotError(f"Found no channel called '{string}'.")

def get_color(string):
  if string == "":
    return discord.Color(0)
  elif string.startswith("0x"):
    try:
      return discord.Color(int(string[2:], 16))
    except:
      pass
  elif string.isdigit():
    try:
      return discord.Color(int(string))
    except:
      pass
  elif string in ["teal", "dark_teal", "green", "dark_green", "blue", "dark_blue", "purple", "dark_purple", "magenta", "dark_magenta", "gold", "dark_gold", "orange", "dark_orange", "red", "dark_red", "lighter_grey", "lighter_gray", "dark_grey", "dark_gray", "light_grey", "light_gray", "darker_grey", "darker_gray", "blurple", "greyple"]:
    return getattr(discord.Color, string)()
  raise BotError("Invalid color format; 0x<hexcode>, integer, or a Discord template color.")