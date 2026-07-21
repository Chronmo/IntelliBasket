"""Database engine and session construction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all IntelliBasket serving tables."""


def buildEngine(databaseUrl: str, **engineOptions: object) -> Engine:
    """Create a SQLAlchemy engine using explicit connection health checks."""
    return create_engine(databaseUrl, pool_pre_ping=True, **engineOptions)


def buildSessionFactory(engine: Engine) -> sessionmaker[Session]:
    """Create a non-expiring session factory suitable for API responses."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initializeDatabase(engine: Engine) -> None:
    """Create serving tables that do not exist."""
    from intellibasket.serving import models  # noqa: F401

    Base.metadata.create_all(engine)


@contextmanager
def sessionScope(sessionFactory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session and handle commit or rollback consistently."""
    databaseSession = sessionFactory()
    try:
        yield databaseSession
        databaseSession.commit()
    except Exception:
        databaseSession.rollback()
        raise
    finally:
        databaseSession.close()
