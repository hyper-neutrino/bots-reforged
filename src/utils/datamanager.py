import json, os, pickle, sys, traceback

from filelock import Filelock as Lock

from .errors import DataError
from .logging import log

lock = Lock("data/data.pickle.lock")

current_data = None
config = None

async def get_data(default, *query, set_if_missing = True):
  if current_data is None:
    raise DataError("Data has not yet been loaded; cannot make queries! Please try again soon.")
  item = current_data
  if len(query) == 0:
    return item
  for q in query[:-1]:
    if q not in item:
      if set_if_missing:
        item[q] = {}
      else:
        return default
    item = item[q]
  if query[-1] not in item and set_if_missing:
    item[query[-1]] = default
  return item.get(query[-1], default)

async def set_data(value, *query):
  if current_data is None:
    raise DataError("Data has not yet been loaded; cannot make queries! Please try again soon.")
  if len(query) == 0:
    raise DataError("Cannot set data with no query given!")
  item = current_data
  for q in query[:-1]:
    if q not in item:
      item[q] = {}
    item = item[q]
  item[query[-1]] = value

async def load_data():
  global current_data
  with lock:
    with open("data/data.pickle", "rb") as f:
      current_data = pickle.load(f)
  print("Successfully loaded data from data/data.pickle!")

async def save_data():
  if current_data is None:
    raise DataError("Cannot save data; it has not yet been loaded! Please try again soon.")
  with lock:
    with open("data/data.pickle", "wb") as f:
      pickle.dump(current_data, f)
  print("Successfully saved data to data/data.pickle!")

def save_config():
  with open("data/config.json", "w") as f:
    json.dump(config, f)