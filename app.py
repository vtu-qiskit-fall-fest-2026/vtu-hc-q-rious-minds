from pathlib import Path

from flask import Flask, jsonify, render_template, send_from_directory, url_for

from energy_data import get_energy_data
from generate_video import generate_video
from quantum_optimizer import run_qaoa_optimization

ROOT = Path(__file__).resolve().parent
VIDEO_DIR = ROOT / "static" / "generated"
app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/energy")
def energy():
    return jsonify(get_energy_data())


@app.route("/api/optimize", methods=["POST"])
def optimize_energy():
    """Run the small Qiskit QAOA scheduling experiment."""
    try:
        result = run_qaoa_optimization(get_energy_data())
        return jsonify(result)
    except Exception as exc:
        app.logger.exception("CarbonWise QAOA optimization failed")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/generate-video", methods=["POST"])
def create_video():
    """Generate the self-contained cartoon explainer plus animated charts."""
    try:
        video_path = Path(generate_video()).resolve()
        return jsonify({
            "success": True,
            "video_url": url_for("serve_video", filename=video_path.name),
        })
    except Exception as exc:
        app.logger.exception("CarbonWise video generation failed")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/generated/<path:filename>")
def serve_video(filename):
    response = send_from_directory(
        VIDEO_DIR,
        filename,
        mimetype="video/mp4",
        as_attachment=False,
        conditional=True,
    )
    response.headers["Cache-Control"] = "no-cache"
    return response


if __name__ == "__main__":
    app.run(debug=True)
