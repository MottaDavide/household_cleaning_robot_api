# core/repository.py
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.core.models import MapMeta, SessionRow, TileRow

class MapRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_current(self) -> dict[tuple[int, int], dict] | None:
        meta = await self._db.get(MapMeta, 1)
        if meta is None:
            return None
        rows = (await self._db.execute(select(TileRow))).scalars().all()
        return {(t.x, t.y): {"walkable": t.walkable, "dirty": t.dirty} for t in rows}

    async def get_dimensions(self) -> dict:
        meta = await self._db.get(MapMeta, 1)
        return {"rows": meta.rows, "cols": meta.cols} if meta else {"rows": 0, "cols": 0}

    async def replace(self, tiles: dict[tuple[int, int], dict], rows: int, cols: int) -> None:
        # "sovrascrivere i valori": transazione singola, atomica tra i pod
        await self._db.execute(delete(TileRow))
        await self._db.merge(MapMeta(id=1, rows=rows, cols=cols))
        self._db.add_all(
            TileRow(x=x, y=y, walkable=t["walkable"], dirty=t["dirty"])
            for (x, y), t in tiles.items()
        )
        await self._db.commit()

    async def mark_clean(self, pos: tuple[int, int]) -> None:
        # SELECT ... FOR UPDATE: altri pod che leggono/scrivono la stessa tile aspettano
        tile = await self._db.get(TileRow, pos, with_for_update=True)
        tile.dirty = False
        await self._db.commit()


class HistoryRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def add(self, report: dict) -> None:
        self._db.add(SessionRow(**report))
        await self._db.commit()

    async def list_all(self) -> list[dict]:
        rows = (await self._db.execute(select(SessionRow).order_by(SessionRow.started_at))).scalars().all()
        return [r.__dict__ for r in rows]