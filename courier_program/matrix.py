from typing import TYPE_CHECKING
from mautrix.bridge import BaseMatrixHandler
if TYPE_CHECKING:
    from .__main__ import CourierCO

class MatrixHandler(BaseMatrixHandler):
    def __init__(self, bridge: "CourierCO") -> None:
        prefix, suffix = bridge.config["bridge.username_template"].format(userid=":").split(":")
        homeserver = bridge.config["homeserver.domain"]
        self.user_id_prefix = f"@{prefix}"
        self.user_id_suffix = f"{suffix}:{homeserver}"

        super().__init__(bridge=bridge)