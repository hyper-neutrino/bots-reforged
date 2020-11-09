from flask import Flask, render_template, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def serve_root():
  return render_template("index.html")

@app.route("/character", methods = ["GET", "POST"])
def serve_character():
  if request.method == "GET":
    return render_template("character.html")
  else:
    return str(request.form)

if __name__ == "__main__":
  app.run(host = "0.0.0.0", port = 5757, debug = True)