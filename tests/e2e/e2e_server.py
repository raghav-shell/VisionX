"""Disposable local application fixture for Playwright; never used in production."""
from pathlib import Path
import tempfile

import uvicorn

from visionsentinel.api.app import create_app
from visionsentinel.api.settings import Settings
from visionsentinel.contracts import Role
from visionsentinel.core.workspace import Workspace
from visionsentinel.governance.identity import create_user

root = Path(tempfile.mkdtemp(prefix="visionsentinel-e2e-"))
workspace = Workspace(root).ensure()
app = create_app(Settings(allowed_hosts=["127.0.0.1", "localhost"], extra_origins=["http://127.0.0.1:4173"],
                          secure_cookies=False, demo_mode=False), workspace)
create_user(app.state.vs.db, "analyst", "analystpassword", Role.ANALYST, "E2E Analyst")
create_user(app.state.vs.db, "approver", "approverpassword", Role.APPROVER, "E2E Approver")
uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
