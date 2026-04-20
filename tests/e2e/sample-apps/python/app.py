import os

import instrument  # noqa: F401  -- must import before Flask

from opentelemetry.instrumentation.flask import FlaskInstrumentor
from flask import Flask, jsonify

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)


@app.route("/hello")
def hello():
    return jsonify(ok=True)


@app.route("/health")
def health():
    return jsonify(ok=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
