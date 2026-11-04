from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    family_memberships = relationship("FamilyMember", back_populates="user", cascade="all, delete-orphan")

class Family(Base):
    __tablename__ = "families"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    members = relationship("FamilyMember", back_populates="family", cascade="all, delete-orphan")
    invites = relationship("FamilyInvite", back_populates="family", cascade="all, delete-orphan")
    deliveries = relationship("QuestionDelivery", back_populates="family", cascade="all, delete-orphan")

class FamilyMember(Base):
    __tablename__ = "family_members"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    family = relationship("Family", back_populates="members")
    user = relationship("User", back_populates="family_memberships")

class FamilyInvite(Base):
    __tablename__ = "family_invites"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(32), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    family = relationship("Family", back_populates="invites")

class QuestionDelivery(Base):
    __tablename__ = "question_deliveries"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    emotion = Column(String(30), nullable=False)
    mode = Column(String(30), default="stealth", nullable=False)
    target_question = Column(Text, nullable=False)
    questions_bundle = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    family = relationship("Family", back_populates="deliveries")
    answer = relationship("Answer", back_populates="delivery", uselist=False, cascade="all, delete-orphan")

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    delivery_id = Column(Integer, ForeignKey("question_deliveries.id", ondelete="CASCADE"), unique=True, nullable=False)
    respondent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    raw_answer = Column(Text, nullable=False)
    polished_answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivery = relationship("QuestionDelivery", back_populates="answer")
    reactions = relationship("Reaction", back_populates="answer", cascade="all, delete-orphan")

class Reaction(Base):
    __tablename__ = "reactions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    answer_id = Column(Integer, ForeignKey("answers.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reaction_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    answer = relationship("Answer", back_populates="reactions")
