from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Account(Base):
    """Модель аккаунта"""
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True)
    phone = Column(String(20), unique=True, nullable=False)
    name = Column(String(100))
    api_id = Column(Integer, nullable=False)
    api_hash = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    groups = relationship("Group", back_populates="account")
    mailings = relationship("Mailing", back_populates="account")

class Group(Base):
    """Модель группы"""
    __tablename__ = 'groups'
    
    id = Column(Integer, primary_key=True)
    group_id = Column(String(50), nullable=False)  # Telegram group ID
    title = Column(String(200), nullable=False)
    username = Column(String(100))
    member_count = Column(Integer, default=0)
    group_type = Column(String(50))  # supergroup, group
    is_private = Column(Boolean, default=False)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    
    # Связи
    account = relationship("Account", back_populates="groups")
    mailings = relationship("Mailing", back_populates="group")

class Mailing(Base):
    """Модель рассылки"""
    __tablename__ = 'mailings'
    
    id = Column(Integer, primary_key=True)
    text = Column(Text)
    photo_path = Column(String(500))
    mailing_type = Column(String(50))  # text, photo, photo_with_text
    interval_type = Column(String(50))  # fixed, random
    min_interval = Column(Integer)  # минуты
    max_interval = Column(Integer)  # минуты
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    stopped_at = Column(DateTime)
    
    # Связи
    account_id = Column(Integer, ForeignKey('accounts.id'))
    group_id = Column(Integer, ForeignKey('groups.id'))
    account = relationship("Account", back_populates="mailings")
    group = relationship("Group", back_populates="mailings")

class MailingHistory(Base):
    """Модель истории рассылок"""
    __tablename__ = 'mailing_history'
    
    id = Column(Integer, primary_key=True)
    mailing_id = Column(Integer, ForeignKey('mailings.id'))
    account_id = Column(Integer, ForeignKey('accounts.id'))
    group_id = Column(Integer, ForeignKey('groups.id'))
    text = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    interval_used = Column(Float)  # фактический интервал в минутах

class NightMode(Base):
    """Модель ночного режима"""
    __tablename__ = 'night_mode'
    
    id = Column(Integer, primary_key=True)
    is_enabled = Column(Boolean, default=False)
    start_hour = Column(Integer, default=21)
    end_hour = Column(Integer, default=5)
    multiplier = Column(Float, default=2.0) 