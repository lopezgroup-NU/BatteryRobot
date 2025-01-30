from flask import Flask, render_template, request
from utils import DB
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home_page():
    if request.method:
        pass
    return render_template("home.html")

if __name__ == '__main__':  
   app.run()