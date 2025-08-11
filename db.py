# db.py

from database.models import SessionLocal, Account, Group, MessageLog
from sqlalchemy.exc import IntegrityError
from datetime import datetime

# ---- АККАУНТЫ ----
def add_account(tg_id, phone, name, token, session_path, role='user'):
    session = SessionLocal()
    try:
        acc = Account(tg_id=tg_id, phone=phone, name=name, token=token, session_path=session_path, role=role)
        session.add(acc)
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False
    finally:
        session.close()

def get_account_by_tg_id(tg_id):
    session = SessionLocal()
    acc = session.query(Account).filter(Account.tg_id == tg_id).first()
    session.close()
    return acc

def get_accounts():
    session = SessionLocal()
    res = session.query(Account).all()
    session.close()
    return res

# ---- ГРУППЫ ----
def add_group(group_id, title, segment=None):
    session = SessionLocal()
    try:
        grp = Group(group_id=group_id, title=title, segment=segment or '')
        session.add(grp)
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False
    finally:
        session.close()

def get_groups():
    session = SessionLocal()
    res = session.query(Group).all()
    session.close()
    return res

def get_group_by_id(group_id):
    session = SessionLocal()
    grp = session.query(Group).filter(Group.group_id == group_id).first()
    session.close()
    return grp

# ---- ЛОГИ ----
def log_message(account_id, group_id, text, status):
    session = SessionLocal()
    log = MessageLog(account_id=account_id, group_id=group_id, text=text, status=status, timestamp=datetime.utcnow())
    session.add(log)
    session.commit()
    session.close()

def get_logs(limit=30):
    session = SessionLocal()
    logs = session.query(MessageLog).order_by(MessageLog.timestamp.desc()).limit(limit).all()
    session.close()
    return logs
