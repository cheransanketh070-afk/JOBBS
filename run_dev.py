"""Local development runner (debug mode, HTTP allowed on localhost)."""
import os
os.environ.setdefault("FORCE_HTTPS", "false")

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
