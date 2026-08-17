from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(40),
        unique=True,
        nullable=False,
        index=True,
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = db.Column(
        db.String(512),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    aquariums = db.relationship(
        "Aquarium",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(
            self.password_hash,
            password,
        )


class Aquarium(db.Model):
    __tablename__ = "aquariums"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    title = db.Column(
        db.String(160),
        nullable=False,
    )

    subtitle = db.Column(
        db.String(255),
        nullable=True,
    )

    length_cm = db.Column(
        db.Float,
        nullable=True,
    )

    width_cm = db.Column(
        db.Float,
        nullable=True,
    )

    height_cm = db.Column(
        db.Float,
        nullable=True,
    )

    gross_volume_liters = db.Column(
        db.Float,
        nullable=True,
    )

    style = db.Column(
        db.String(100),
        nullable=True,
    )

    livestock_summary = db.Column(
        db.String(500),
        nullable=True,
    )

    fit_score = db.Column(
        db.Integer,
        nullable=True,
    )

    plan_json = db.Column(
        db.Text,
        nullable=True,
    )

    # AI planları için fotoğraf kullanmıyoruz.
    # Bu alan ileride fiziksel/gerçek tank özelliği gelirse değerlendirilebilir.
    cover_image = db.Column(
        db.String(500),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner = db.relationship(
        "User",
        back_populates="aquariums",
    )

    chat_messages = db.relationship(
        "AquariumChatMessage",
        back_populates="aquarium",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="AquariumChatMessage.created_at",
    )

    revisions = db.relationship(
        "AquariumPlanRevision",
        back_populates="aquarium",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="AquariumPlanRevision.created_at.desc()",
    )


class AquariumChatMessage(db.Model):
    __tablename__ = "aquarium_chat_messages"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    aquarium_id = db.Column(
        db.Integer,
        db.ForeignKey("aquariums.id"),
        nullable=False,
        index=True,
    )

    role = db.Column(
        db.String(20),
        nullable=False,
    )

    content = db.Column(
        db.Text,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    aquarium = db.relationship(
        "Aquarium",
        back_populates="chat_messages",
    )


class AquariumPlanRevision(db.Model):
    __tablename__ = "aquarium_plan_revisions"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    aquarium_id = db.Column(
        db.Integer,
        db.ForeignKey("aquariums.id"),
        nullable=False,
        index=True,
    )

    instruction = db.Column(
        db.Text,
        nullable=False,
    )

    previous_plan_json = db.Column(
        db.Text,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    aquarium = db.relationship(
        "Aquarium",
        back_populates="revisions",
    )


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(
            User,
            int(user_id),
        )
    except (TypeError, ValueError):
        return None
