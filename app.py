from flask import Flask, render_template, jsonify
from energydata import get_energy_data

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/energy")
def energy():
    data = get_energy_data()
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)