"""Entry point for running the PM server: python -m EvoScientist.pm._run_server"""

import uvicorn

from .api.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")
