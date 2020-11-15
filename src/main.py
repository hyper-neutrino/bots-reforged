from commands import *

async def direct():
  await ainput()
  gid = 739585686377857097
  cid = {739585686377857097: 739585828791124051, 699314655973212242: 741144497588535378}
  while True:
    command = (await ainput(">>> ")).strip()
    if command.startswith("gg "):
      g = command[3:].strip()
      if g.isdigit():
        g = int(g)
        if client.get_guild(g):
          gid = g
        else:
          print("Guild does not exist / I am not in this guild!")
      else:
        for guild in client.guilds:
          if guild.name == g:
            gid = guild.id
            break
        else:
          print("Guild does not exist / I am not in this guild!")
    elif command.startswith("gc "):
      c = command[3:].strip()
      if c.isdigit():
        c = int(c)
        if client.get_guild(gid).get_channel(c):
          cid[gid] = c
        else:
          print("Channel does not exist / I am not in this channel!")
      else:
        for channel in client.get_guild(gid).channels:
          if channel.name == c:
            cid[gid] = channel.id
            break
        else:
          print("Channel does not exist / I am not in this channel!")
    elif command.startswith("send "):
      if gid not in cid:
        print("You have not set the channel for this server!")
      else:
        m = command[5:].strip()
        while True:
          try:
            await client.get_guild(gid).get_channel(cid[gid]).send(m)
            break
          except:
            print("Sending failed, for some reason. Try again.")

async def osu_watch():
  return
  asyncio.sleep(10)
  while True:
    for channel in await get_data("watch_channels", "osu", default = set()):
      for member in channel.members:
        if await has_data("external", "osu", member):
          await channel.send("Tracking osu! player " + member.display_name + " in this channel.")
    asyncio.sleep(10)

loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(
  client.start(config["discord-token"]),
  direct(),
  osu_watch()
))