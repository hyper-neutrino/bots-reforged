class BotError(RuntimeError):
  def __init__(self, message = "An unexpected error occurred with the bot!"):
    self.message = message

class DataError(RuntimeError):
  def __init__(self, message = "An unexpected error occurred when accessing/saving data!"):
    self.message = message