
import asyncio
import logging
from courier_program.courier import Courier
from courier_program.config import Config
from courier_program.matrix import MatrixHandler
from courier_program.puppet import Puppet
from courier_program.user import User
from aiohttp import web

class CourierCO(Courier):
    name = "courier-program"
    module = "courier_program"
    command = "python -m courier_program"
    description = "An appservice for the create users for WhatsApp login"
    version = "0.1"
    config_class = Config
    matrix_class = MatrixHandler

    config = Config
    matrix = MatrixHandler
    app = web.Application
    periodic_reconnect_task: asyncio.Task = None

    def preinit(self) -> None:
        self.periodic_reconnect_task = None
        super().preinit()

    # def prepare_db(self) -> None:
    #     super().prepare_db()
    #     init_db(self.db)

    async def start(self) -> None:
        # self.add_startup_actions(User.init_cls(self))
        # self.add_startup_actions(Puppet.init_cls(self))
        # Portal.init_cls(self)
        if self.config["bridge.resend_bridge_info"]:
            self.add_startup_actions(self.resend_bridge_info())
        await super().start()
        self.periodic_reconnect_task = asyncio.create_task(self._try_periodic_reconnect_loop())

    def prepare_stop(self) -> None:
        self.periodic_reconnect_task.cancel()
        # self.add_shutdown_actions(user.stop_listen() for user in User.by_courpk.values())
        self.log.debug("Stopping puppet syncers")
        for puppet in Puppet.by_custom_mxid.values():
            puppet.stop()

    async def _try_periodic_reconnect_loop(self) -> None:
        try:
            await self._periodic_reconnect_loop()
        except Exception:
            self.log.exception("Fatal error in periodic reconnect loop")

    async def _periodic_reconnect_loop(self) -> None:
        log = logging.getLogger("mau.periodic_reconnect")
        always_reconnect = self.config["bridge.periodic_reconnect.always"]
        interval = self.config["bridge.periodic_reconnect.interval"]
        if interval <= 0:
            log.debug("Periodic reconnection is not enabled")
            return
        resync = bool(self.config["bridge.periodic_reconnect.resync"])
        if interval < 600:
            log.warning("Periodic reconnect interval is quite low (%d)", interval)
        log.debug("Starting periodic reconnect loop")
        while True:
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                log.debug("Periodic reconnect loop stopped")
                return
            log.info("Executing periodic reconnections")
            for user in User.by_courpk.values():
                if not user.is_connected and not always_reconnect:
                    log.debug("Not reconnecting %s: not connected", user.mxid)
                    continue
                log.debug("Executing periodic reconnect for %s", user.mxid)
                try:
                    await user.refresh(resync=resync)
                except asyncio.CancelledError:
                    log.debug("Periodic reconnect loop stopped")
                    return
                except Exception:
                    log.exception("Error while reconnecting %s", user.mxid)
CourierCO().run()

