import asyncio
from typing import Optional, Type
from mautrix.util.program import Program
from mautrix.appservice import AppService, ASStateStore
from mautrix.errors import MExclusive, MUnknownToken
import sys
from mautrix.api import HTTPAPI
# from mautrix.util.bridge_state import BridgeState, BridgeStateEvent
from mautrix.bridge.config import BaseBridgeConfig
from mautrix.bridge.matrix import BaseMatrixHandler

class Courier(Program):
    az: AppService
    matrix_class: Type[BaseMatrixHandler]
    matrix: BaseMatrixHandler
    periodic_reconnect_task: Optional[asyncio.Task]
    state_store: ASStateStore
    config_class: Type[BaseBridgeConfig]
    config: BaseBridgeConfig
    # manhole: Optional[br.manhole.ManholeState]

    def __init__(
        self,
        module: str = None,
        name: str = None,
        description: str = None,
        command: str = None,
        version: str = None,
        config_class: Type[BaseBridgeConfig] = None,
        matrix_class: Type[BaseMatrixHandler] = None,
        state_store_class: Type[ASStateStore] = None,
    ) -> None:
        super().__init__(module, name, description, command, version, config_class)
        if matrix_class:
            self.matrix_class = matrix_class
        if state_store_class:
            self.state_store_class = state_store_class
        self.manhole = None

    def prepare_arg_parser(self) -> None:
        super().prepare_arg_parser()
        self.parser.add_argument(
            "-g",
            "--generate-registration",
            action="store_true",
            help="generate registration and quit",
        )
        self.parser.add_argument(
            "-r",
            "--registration",
            type=str,
            default="registration.yaml",
            metavar="<path>",
            help="the path to save the generated registration to (not needed "
            "for running the bridge)",
        )

    def preinit(self) -> None:
        super().preinit()
        if self.args.generate_registration:
            self.generate_registration()
            sys.exit(0)

    def prepare(self) -> None:
        super().prepare()
        # self.prepare_db()
        self.prepare_appservice()
        # self.prepare_bridge()

    def prepare_config(self) -> None:
        self.config = self.config_class(
            self.args.config, self.args.registration, self.args.base_config
        )
        if self.args.generate_registration:
            self.config._check_tokens = False
        self.load_and_update_config()

    def generate_registration(self) -> None:
        self.config.generate_registration()
        self.config.save()
        print(f"Registration generated and saved to {self.config.registration_path}")

    def prepare_appservice(self) -> None:
        # self.make_state_store()
        mb = 1024 ** 2
        default_http_retry_count = self.config.get("homeserver.http_retry_count", None)
        if self.name not in HTTPAPI.default_ua:
            HTTPAPI.default_ua = f"{self.name}/{self.version} {HTTPAPI.default_ua}"
        self.az = AppService(
            server=self.config["homeserver.address"],
            domain=self.config["homeserver.domain"],
            verify_ssl=self.config["homeserver.verify_ssl"],
            connection_limit=self.config["homeserver.connection_limit"],
            id=self.config["appservice.id"],
            as_token=self.config["appservice.as_token"],
            hs_token=self.config["appservice.hs_token"],
            tls_cert=self.config.get("appservice.tls_cert", None),
            tls_key=self.config.get("appservice.tls_key", None),
            bot_localpart=self.config["appservice.bot_username"],
            ephemeral_events=self.config["appservice.ephemeral_events"],
            default_ua=HTTPAPI.default_ua,
            default_http_retry_count=default_http_retry_count,
            log="courier.as",
            loop=self.loop,
            # state_store=self.state_store,
            # real_user_content_key=self.real_user_content_key,
            aiohttp_params={"client_max_size": self.config["appservice.max_body_size"] * mb},
        )

    async def start(self) -> None:
        self.log.debug("Starting appservice...")
        await self.az.start(self.config["appservice.hostname"], self.config["appservice.port"])
        try:
            await self.matrix.wait_for_connection(self)
        except MUnknownToken:
            self.log.critical(
                "The as_token was not accepted. Is the registration file installed "
                "in your homeserver correctly?"
            )
            sys.exit(16)
        except MExclusive:
            self.log.critical(
                "The as_token was accepted, but the /register request was not. "
                "Are the homeserver domain and username template in the config "
                "correct, and do they match the values in the registration?"
            )
            sys.exit(16)

        self.add_startup_actions(self.matrix.init_as_bot(self))
        await super().start()
        self.az.ready = True

        # status_endpoint = self.config["homeserver.status_endpoint"]
        # if status_endpoint and await self.count_logged_in_users() == 0:
        #     state = BridgeState(state_event=BridgeStateEvent.UNCONFIGURED).fill()
        #     await state.send(status_endpoint, self.az.as_token, self.log)

    async def stop(self) -> None:
        # if self.manhole:
        #     self.manhole.close()
        #     self.manhole = None
        await self.az.stop()
        await super().stop()
        if self.matrix.e2ee:
            await self.matrix.e2ee.stop()