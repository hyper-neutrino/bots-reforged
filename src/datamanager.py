import copy, json, os, pickle, sys, time, traceback

from filelock import FileLock as Lock

from errors import DataError
from logs import log

lock = Lock("data/data.pickle.lock")

current_data = None
config = None

with open("data/config.json", "r") as f:
  config = json.load(f)

async def get_data(*query, default = None, set_if_missing = False):
  if current_data is None:
    load_data()
  item = current_data
  if len(query) == 0:
    return item
  for q in query[:-1]:
    if item.get(q) is None:
      if set_if_missing:
        item[q] = {}
      else:
        return default
    item = item[q]
  if query[-1] not in item and set_if_missing:
    item[query[-1]] = default
  return item.get(query[-1], default)

async def has_data(*query):
  return query[-1] in await get_data(*query[:-1], default = {}, set_if_missing = False)

async def set_data(*query):
  global current_data
  backup = copy.deepcopy(current_data)
  if len(query) < 2:
    raise RuntimeError("Malformed set-data query; not enough arguments provided.")
  *query, value = query
  item = current_data
  for q in query[:-1]:
    if q not in item:
      item[q] = {}
    item = item[q]
  item[query[-1]] = value
  try:
    save_data()
  except:
    print("\033[37;41mCritical error saving data; reverting to avoid data loss!\033[0m")
    print(traceback.format_exc())
    current_data = backup
    save_data()
  return value

async def del_data(*query):
  if len(query) == 0:
    raise RuntimeError("Cannot delete the entire data object!")
  *query, key = query
  obj = await get_data(*query)
  if key in obj:
    del obj[key]
  return await set_data(*query, obj)

async def mod_data(*query, default = None):
  if len(query) == 0:
    raise RuntimeError("Malformed mod-data query; not enough arguments provided.")
  return await set_data(*query[:-1], query[-1](await get_data(*query[:-1], default = default)))

async def batch_set_data(*query, **kwargs):
  if len(query) == 0:
    raise RuntimeError("Malformed batch-set-data query; not enough arguments provided.")
  return await set_data(*query, {**(await get_data(*query, default = {})), **kwargs})

def load_data():
  global current_data
  with lock:
    with open("data/data.pickle", "rb") as f:
      current_data = pickle.load(f)
  print("Successfully loaded data from data/data.pickle!")

def save_data():
  if current_data is None:
    raise DataError("Cannot save data; it has not yet been loaded! Please try again soon.")
  with lock:
    current_data["timestamp"] = time.time()
    with open("data/data.pickle", "wb") as f:
      pickle.dump(current_data, f)

def save_config():
  with open("data/config.json", "w") as f:
    json.dump(config, f)