from app import create_app, socketio, db
from app.models import User
import os

def create_default_admin():
    print("=" * 50)
    print("🔧 ساخت ادمین پیشفرض...")
    print("=" * 50)
    
    app = create_app()
    with app.app_context():
        db.create_all()
        
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                account_type='hpro',
                is_active=True,
                is_admin=True,
                allowed_entries=0
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ ادمین ساخته شد: admin / admin123")
        else:
            admin.is_admin = True
            admin.set_password('admin123')
            db.session.commit()
            print("✅ ادمین به‌روزرسانی شد: admin / admin123")
        
        print("=" * 50)
        print("👑 ادمین: admin / admin123")
        print("=" * 50)

# ایجاد ادمین در زمان راه‌اندازی
create_default_admin()

# ایجاد نمونه برنامه
app = create_app()

if __name__ == '__main__':
    # دریافت پورت از محیط (برای Render)
    port = int(os.environ.get('PORT', 10000))
    
    # اجرا با SocketIO
    socketio.run(
        app, 
        debug=False,  # در تولید False باشد
        host='0.0.0.0', 
        port=port,
        allow_unsafe_werkzeug=True  # برای رفع خطای Werkzeug
    )
