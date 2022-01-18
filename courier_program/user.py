# mautrix-instagram - A Matrix-Instagram puppeting bridge.
# Copyright (C) 2022 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterable, Awaitable, cast, AsyncGenerator
import asyncio
import logging
import time

from mautrix.appservice import AppService
from mautrix.bridge import BaseUser, async_getter_lock
from courier_program.db.user import User as DBUser
from courier_program.puppet import Puppet
from mautrix.util.logging import TraceLogger
from mautrix.types import EventID, MessageType, RoomID, TextMessageEventContent, UserID

from courier_program.config import Config

if TYPE_CHECKING:
    from .__main__ import CourierCO


class User(DBUser, BaseUser):
    ig_base_log: TraceLogger = logging.getLogger("mau.courier")
    by_mxid: dict[UserID, User] = {}
    by_courpk: dict[int, User] = {}
    config: Config
    az: AppService
    loop: asyncio.AbstractEventLoop

    async def get_puppet(self) -> Puppet | None:
        if not self.courpk:
            return None
        return await Puppet.get_by_pk(self.courpk)

    def _add_to_cache(self) -> None:
        self.by_mxid[self.mxid] = self
        if self.courpk:
            self.by_courpk[self.courpk] = self
    @classmethod
    def init_cls(cls, bridge: "CourierCO") -> AsyncIterable[Awaitable[None]]:
        cls.bridge = bridge
        cls.config = bridge.config
        cls.az = bridge.az
        cls.loop = bridge.loop


    @classmethod
    @async_getter_lock
    async def get_by_mxid(cls, mxid: UserID, *, create: bool = True) -> User | None:
        # Never allow ghosts to be users
        if Puppet.get_id_from_mxid(mxid):
            return None
        try:
            return cls.by_mxid[mxid]
        except KeyError:
            pass

        user = cast(cls, await super().get_by_mxid(mxid))
        if user is not None:
            user._add_to_cache()
            return user

        if create:
            user = cls(mxid)
            await user.insert()
            user._add_to_cache()
            return user

        return None

    @classmethod
    @async_getter_lock
    async def get_by_courpk(cls, courpk: int) -> User | None:
        try:
            return cls.by_courpk[courpk]
        except KeyError:
            pass

        user = cast(cls, await super().get_by_courpk(courpk))
        if user is not None:
            user._add_to_cache()
            return user

        return None

    @classmethod
    async def all_logged_in(cls) -> AsyncGenerator[User, None]:
        users = await super().all_logged_in()
        user: cls
        for index, user in enumerate(users):
            try:
                yield cls.by_mxid[user.mxid]
            except KeyError:
                user._add_to_cache()
                yield user


