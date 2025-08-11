# models.py

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from config import SYNC_DATABASE_URL

engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Account(Base):
    __tablename__ = 'accounts'
    id          = Column(Integer, primary_key=True)
    tg_id       = Column(String, nullable=True, unique=True)
    phone       = Column(String)
    name        = Column(String)
    token       = Column(String)
    session_path= Column(String)
    role        = Column(String, default='user')  # user/operator/admin
    api_id      = Column(String)  # API ID для Telegram
    api_hash    = Column(String)  # API Hash для Telegram
    is_active   = Column(Boolean, default=True)  # Активен ли аккаунт

class Group(Base):
    __tablename__ = 'groups'
    id          = Column(Integer, primary_key=True)
    account_id  = Column(Integer, ForeignKey('accounts.id'))
    tg_id       = Column(String, nullable=False)  # Telegram ID группы
    name        = Column(String)  # Название группы
    type        = Column(String)  # 'group' или 'channel'
    segment     = Column(String, default='')  # Сегмент для рассылки

class MessageLog(Base):
    __tablename__ = 'message_logs'
    id          = Column(Integer, primary_key=True)
    account_id  = Column(Integer, ForeignKey('accounts.id'))
    group_id    = Column(String)
    text        = Column(Text)
    status      = Column(String)
    timestamp   = Column(DateTime, default=datetime.utcnow)

class Mailing(Base):
    __tablename__ = 'mailings'
    id          = Column(Integer, primary_key=True)
    account_id  = Column(Integer, ForeignKey('accounts.id'))
    group_id    = Column(Integer, ForeignKey('groups.id'))  # Добавлено поле для связи с группой
    text        = Column(Text)
    photo_path  = Column(String)
    groups      = Column(Text)  # JSON строка с ID групп (для массовых рассылок)
    status      = Column(String, default='pending')  # pending, running, stopped, completed
    is_active   = Column(Boolean, default=True)  # Активна ли рассылка
    created_at  = Column(DateTime, default=datetime.utcnow)
    started_at  = Column(DateTime)
    completed_at = Column(DateTime)
    total_groups = Column(Integer, default=0)
    sent_count  = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    min_interval = Column(Integer, default=1)  # Минимальный интервал в минутах
    max_interval = Column(Integer, default=5)  # Максимальный интервал в минутах

class MailingHistory(Base):
    __tablename__ = 'mailing_history'
    id          = Column(Integer, primary_key=True)
    mailing_id  = Column(Integer, ForeignKey('mailings.id'))
    group_id    = Column(String)
    group_title = Column(String)
    status      = Column(String)  # sent, error, skipped
    error_message = Column(Text)
    sent_at     = Column(DateTime, default=datetime.utcnow)

class NightMode(Base):
    __tablename__ = 'night_mode'
    id          = Column(Integer, primary_key=True)
    enabled     = Column(Boolean, default=False)  # Активен ли ночной режим
    start_hour  = Column(Integer, default=21)
    end_hour    = Column(Integer, default=5)
    updated_at  = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
