import datetime

def log(message, logtype = "INFO"):
  logtype = logtype.strip()
  date_string = datetime.datetime.now().isoformat()
  output = f"[{logtype.upper()} / {date_string}] {message}"
  with open(f"logs/all.log", "a") as f:
    f.write(output)
  with open(f"logs/{logtype.lower()}", "a") as f:
    f.write(output)