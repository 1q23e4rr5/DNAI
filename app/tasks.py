from apscheduler.schedulers.background import BackgroundScheduler
from app import db
from app.models import RegistrationRequest
from datetime import datetime, timedelta


def expire_old_requests():
    """انقضای درخواست‌های 24 ساعته"""
    with db.app.app_context():
        cutoff = datetime.utcnow() - timedelta(hours=24)
        old_requests = RegistrationRequest.query.filter(
            RegistrationRequest.status == 'pending',
            RegistrationRequest.created_at < cutoff
        ).all()
        for req in old_requests:
            req.status = 'expired'
        db.session.commit()


def start_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(expire_old_requests, 'interval', hours=1)
    scheduler.start()
    import atexit
    atexit.register(lambda: scheduler.shutdown())