"""数据库事务单元。"""

from __future__ import annotations

from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.db.session import get_session


class UnitOfWork(AbstractContextManager["UnitOfWork"]):
    """封装 SQLAlchemy Session 的事务生命周期。"""

    def __enter__(self) -> "UnitOfWork":
        self._ctx = get_session()
        self._session: Session = self._ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self._ctx.__exit__(exc_type, exc, tb)

    @property
    def session(self) -> Session:
        return self._session


__all__ = ["UnitOfWork"]
