
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from attr import dataclass
import asyncpg

from mautrix.types import RoomID, UserID
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class User:
    db: ClassVar[Database] = fake_db

    mxid: UserID
    courpk: int | None
    notice_room: RoomID | None

    async def insert(self) -> None:
        q = 'INSERT INTO "user" (mxid, courpk, state, notice_room) VALUES ($1, $2, $3, $4)'
        await self.db.execute(
            q, self.mxid, self.courpk, self.state.json() if self.state else None, self.notice_room
        )

    async def update(self) -> None:
        q = 'UPDATE "user" SET courpk=$2, state=$3, notice_room=$4 WHERE mxid=$1'
        await self.db.execute(
            q, self.mxid, self.courpk, self.state.json() if self.state else None, self.notice_room
        )

    # @classmethod
    # def _from_row(cls, row: asyncpg.Record) -> User:
    #     data = {**row}
    #     state_str = data.pop("state")
    #     return cls(state=AndroidState.parse_json(state_str) if state_str else None, **data)

    @classmethod
    async def get_by_mxid(cls, mxid: UserID) -> User | None:
        q = 'SELECT mxid, courpk, state, notice_room FROM "user" WHERE mxid=$1'
        row = await cls.db.fetchrow(q, mxid)
        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def get_by_courpk(cls, courpk: int) -> User | None:
        q = 'SELECT mxid, courpk, state, notice_room FROM "user" WHERE courpk=$1'
        row = await cls.db.fetchrow(q, courpk)
        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def all_logged_in(cls) -> list[User]:
        q = (
            "SELECT mxid, courpk, state, notice_room "
            'FROM "user" WHERE courpk IS NOT NULL AND state IS NOT NULL'
        )
        rows = await cls.db.fetch(q)
        return [cls._from_row(row) for row in rows]
