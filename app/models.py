import enum
import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# db.Model is Flask-SQLAlchemy's base class; it provides .query on all subclasses.
# Mapped[] / mapped_column() typed API works with db.Model in FSQLAlchemy 3.x.
db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PhaseEnum(str, enum.Enum):
    GROUP = "group"
    R32 = "r32"
    R16 = "r16"
    QF = "qf"
    SF = "sf"
    THIRD = "third_place"
    FINAL = "final"

    @property
    def is_knockout(self) -> bool:
        return self != PhaseEnum.GROUP

    @property
    def label(self) -> str:
        labels = {
            PhaseEnum.GROUP: "Group Stage",
            PhaseEnum.R32: "Round of 32",
            PhaseEnum.R16: "Round of 16",
            PhaseEnum.QF: "Quarter-finals",
            PhaseEnum.SF: "Semi-finals",
            PhaseEnum.THIRD: "3rd Place",
            PhaseEnum.FINAL: "Final",
        }
        return labels[self]


class ResultSourceEnum(str, enum.Enum):
    MANUAL = "manual"
    API = "api"
    API_CORRECTED = "api_corrected"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Team(db.Model):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country_code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    group_letter: Mapped[str | None] = mapped_column(String(1))
    flag_url: Mapped[str | None] = mapped_column(String(255))

    home_matches: Mapped[list["Match"]] = relationship(
        "Match", foreign_keys="Match.home_team_id", back_populates="home_team"
    )
    away_matches: Mapped[list["Match"]] = relationship(
        "Match", foreign_keys="Match.away_team_id", back_populates="away_team"
    )
    champion_predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", foreign_keys="Prediction.champion_team_id", back_populates="champion_team"
    )

    def __repr__(self) -> str:
        return f"<Team {self.country_code} {self.name}>"


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="user", foreign_keys="Prediction.user_id"
    )

    # Flask-Login interface
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_active(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Match(db.Model):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    phase: Mapped[PhaseEnum] = mapped_column(SAEnum(PhaseEnum), nullable=False)
    group_letter: Mapped[str | None] = mapped_column(String(1))
    match_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    venue: Mapped[str | None] = mapped_column(String(200))
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    result_source: Mapped[ResultSourceEnum | None] = mapped_column(SAEnum(ResultSourceEnum))

    home_team: Mapped["Team"] = relationship(
        "Team", foreign_keys=[home_team_id], back_populates="home_matches"
    )
    away_team: Mapped["Team"] = relationship(
        "Team", foreign_keys=[away_team_id], back_populates="away_matches"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="match", foreign_keys="Prediction.match_id"
    )

    @property
    def has_result(self) -> bool:
        return self.home_score is not None and self.away_score is not None

    @property
    def result_label(self) -> str | None:
        if not self.has_result:
            return None
        if self.home_score > self.away_score:
            return "home"
        if self.away_score > self.home_score:
            return "away"
        return "draw"

    def __repr__(self) -> str:
        return f"<Match {self.id} {self.phase}>"


class Prediction(db.Model):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_user_match"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    match_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("matches.id"))
    home_score: Mapped[int] = mapped_column(Integer, nullable=False)
    away_score: Mapped[int] = mapped_column(Integer, nullable=False)
    champion_team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"))
    points_awarded: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="predictions", foreign_keys=[user_id]
    )
    match: Mapped["Match | None"] = relationship(
        "Match", back_populates="predictions", foreign_keys=[match_id]
    )
    champion_team: Mapped["Team | None"] = relationship(
        "Team", foreign_keys=[champion_team_id], back_populates="champion_predictions"
    )

    def __repr__(self) -> str:
        return f"<Prediction user={self.user_id} match={self.match_id}>"


class AppSettings(db.Model):
    """Single-row table for admin-editable runtime settings."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(100), default="wc2026", nullable=False)
    lock_minutes_before: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
