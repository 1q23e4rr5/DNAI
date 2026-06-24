from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user, login_user, logout_user
from app import db, bcrypt, socketio
from app.models import User, ReferralCode, RegistrationRequest, DetectionHistory, SupportMessage, Announcement, AdminActionLog
from datetime import datetime, timedelta
from functools import wraps

admin_bp = Blueprint('admin', __name__)


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('لطفاً وارد شوید.', 'warning')
            return redirect(url_for('admin.admin_login'))
        
        if not current_user.is_admin:
            flash('⚠️ دسترسی غیرمجاز! این بخش فقط برای ادمین است.', 'danger')
            return redirect(url_for('main.panel'))
        
        return func(*args, **kwargs)
    return decorated_view


# ============================================================
# ========== ورود و خروج ادمین ==========
# ============================================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('main.panel'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.is_admin and user.check_password(password):
            login_user(user)
            flash('به پنل ادمین خوش آمدید!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('اطلاعات ورود ادمین صحیح نیست.', 'danger')

    return render_template('admin_login.html')


@admin_bp.route('/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin.admin_login'))


# ============================================================
# ========== داشبورد ==========
# ============================================================

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_requests = RegistrationRequest.query.filter_by(status='pending').count()
    total_messages = SupportMessage.query.filter_by(is_read=False).count()
    blocked_users = User.query.filter_by(is_blocked=True).count()
    logs = AdminActionLog.query.order_by(AdminActionLog.created_at.desc()).limit(10).all()
    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           total_requests=total_requests,
                           total_messages=total_messages,
                           blocked_users=blocked_users,
                           logs=logs)


# ============================================================
# ========== مدیریت کاربران ==========
# ============================================================

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        account_type = request.form.get('account_type')
        allowed_entries = request.form.get('allowed_entries', 0)

        if User.query.filter_by(username=username).first():
            flash('نام کاربری تکراری است.', 'danger')
            return redirect(url_for('admin.create_user'))

        user = User(username=username, account_type=account_type, is_active=True, is_admin=False)
        user.set_password(password)
        if account_type == 'noob':
            user.allowed_entries = int(allowed_entries)
        db.session.add(user)
        db.session.commit()

        log = AdminActionLog(admin_id=current_user.id, action='create_user', details=f'کاربر {username} ساخته شد.')
        db.session.add(log)
        db.session.commit()
        flash('کاربر ساخته شد.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin_create_user.html')


@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_hpro():
        flash('کاربر HPRO قابل ویرایش نیست.', 'danger')
        return redirect(url_for('admin.users'))

    if request.method == 'POST':
        account_type = request.form.get('account_type')
        allowed_entries = request.form.get('allowed_entries')
        user.account_type = account_type
        if account_type == 'noob':
            user.allowed_entries = int(allowed_entries)
        else:
            user.allowed_entries = 0
        db.session.commit()

        log = AdminActionLog(admin_id=current_user.id, action='edit_user', details=f'کاربر {user.username} ویرایش شد.')
        db.session.add(log)
        db.session.commit()
        flash('ویرایش انجام شد.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin_edit_user.html', user=user)


@admin_bp.route('/users/block/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def block_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_hpro():
        flash('کاربر HPRO قابل مسدودسازی نیست.', 'danger')
        return redirect(url_for('admin.users'))

    user.is_blocked = True
    db.session.commit()
    socketio.emit('force_logout', {'message': 'حساب شما توسط ادمین مسدود شد.'}, room=f'user_{user.id}')
    log = AdminActionLog(admin_id=current_user.id, action='block_user', details=f'کاربر {user.username} مسدود شد.')
    db.session.add(log)
    db.session.commit()
    flash('کاربر مسدود شد.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/unblock/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def unblock_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_blocked = False
    db.session.commit()
    log = AdminActionLog(admin_id=current_user.id, action='unblock_user', details=f'کاربر {user.username} رفع انسداد شد.')
    db.session.add(log)
    db.session.commit()
    flash('رفع انسداد کاربر انجام شد.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.is_hpro():
        flash('⭐ کاربر HPRO قابل حذف نیست!', 'danger')
        return redirect(url_for('admin.users'))
    
    username = user.username
    socketio.emit('force_logout', {'message': 'حساب شما توسط ادمین حذف شد.'}, room=f'user_{user.id}')
    
    DetectionHistory.query.filter_by(user_id=user.id).delete()
    SupportMessage.query.filter_by(sender_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    
    log = AdminActionLog(admin_id=current_user.id, action='delete_user', details=f'کاربر {username} حذف شد.')
    db.session.add(log)
    db.session.commit()
    
    flash(f'✅ کاربر {username} با موفقیت حذف شد.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/blocked-users')
@login_required
@admin_required
def blocked_users():
    blocked = User.query.filter_by(is_blocked=True).all()
    return render_template('admin_blocked_users.html', users=blocked)


# ============================================================
# ========== مدیریت درخواست‌ها ==========
# ============================================================

@admin_bp.route('/requests')
@login_required
@admin_required
def requests():
    pending = RegistrationRequest.query.filter_by(status='pending').order_by(
        RegistrationRequest.referral_code.isnot(None).desc(),
        RegistrationRequest.created_at
    ).all()
    return render_template('admin_requests.html', requests=pending)


@admin_bp.route('/requests/approve/<int:req_id>', methods=['POST'])
@login_required
@admin_required
def approve_request(req_id):
    req = RegistrationRequest.query.get_or_404(req_id)
    if req.status != 'pending':
        flash('درخواست قبلاً بررسی شده.', 'warning')
        return redirect(url_for('admin.requests'))

    user = User(
        username=req.username,
        account_type=req.account_type,
        is_active=True,
        is_admin=False
    )
    user.set_password(req.password)
    if req.account_type == 'noob':
        user.allowed_entries = 5
    db.session.add(user)
    db.session.commit()
    
    if req.referral_code:
        ref = ReferralCode.query.filter_by(code=req.referral_code).first()
        if ref:
            ref.used_count += 1
    
    req.status = 'approved'
    req.reviewed_at = datetime.utcnow()
    db.session.commit()

    log = AdminActionLog(admin_id=current_user.id, action='approve_request', details=f'درخواست {req.username} تایید شد.')
    db.session.add(log)
    db.session.commit()
    flash('درخواست تایید شد.', 'success')
    return redirect(url_for('admin.requests'))


@admin_bp.route('/requests/reject/<int:req_id>', methods=['POST'])
@login_required
@admin_required
def reject_request(req_id):
    req = RegistrationRequest.query.get_or_404(req_id)
    if req.status != 'pending':
        flash('درخواست قبلاً بررسی شده.', 'warning')
        return redirect(url_for('admin.requests'))

    req.status = 'rejected'
    req.reviewed_at = datetime.utcnow()
    db.session.commit()

    log = AdminActionLog(admin_id=current_user.id, action='reject_request', details=f'درخواست {req.username} رد شد.')
    db.session.add(log)
    db.session.commit()
    flash('درخواست رد شد.', 'success')
    return redirect(url_for('admin.requests'))


@admin_bp.route('/requests/edit/<int:req_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_request(req_id):
    req = RegistrationRequest.query.get_or_404(req_id)
    if req.status != 'pending':
        flash('درخواست قبلاً بررسی شده.', 'warning')
        return redirect(url_for('admin.requests'))

    if request.method == 'POST':
        username = request.form.get('username')
        account_type = request.form.get('account_type')

        req.username = username
        req.account_type = account_type
        req.reviewed_at = datetime.utcnow()
        db.session.commit()

        flash('درخواست ویرایش شد.', 'success')
        return redirect(url_for('admin.requests'))

    return render_template('admin_edit_request.html', req=req)


# ============================================================
# ========== مدیریت کدهای معرف ==========
# ============================================================

@admin_bp.route('/referral-codes', methods=['GET', 'POST'])
@login_required
@admin_required
def referral_codes():
    if request.method == 'POST':
        code = request.form.get('code')
        is_golden = request.form.get('is_golden') == 'on'
        
        if ReferralCode.query.filter_by(code=code).first():
            flash('کد تکراری است.', 'danger')
        else:
            ref = ReferralCode(code=code, is_golden=is_golden, created_by_admin_id=current_user.id)
            db.session.add(ref)
            db.session.commit()
            flash('کد معرف اضافه شد.', 'success')
    
    codes = ReferralCode.query.all()
    return render_template('admin_referral_codes.html', codes=codes)


@admin_bp.route('/referral-codes/delete/<int:code_id>', methods=['POST'])
@login_required
@admin_required
def delete_referral_code(code_id):
    code = ReferralCode.query.get_or_404(code_id)
    code_name = code.code
    db.session.delete(code)
    db.session.commit()
    
    log = AdminActionLog(admin_id=current_user.id, action='delete_referral_code', details=f'کد {code_name} حذف شد.')
    db.session.add(log)
    db.session.commit()
    
    flash(f'✅ کد {code_name} با موفقیت حذف شد.', 'success')
    return redirect(url_for('admin.referral_codes'))


# ============================================================
# ========== مدیریت پیام‌های پشتیبانی ==========
# ============================================================

@admin_bp.route('/support-messages')
@login_required
@admin_required
def support_messages():
    messages = SupportMessage.query.filter(
        SupportMessage.is_from_user == True,
        SupportMessage.sender_id.in_(
            db.session.query(User.id).filter(User.account_type.in_(['rich', 'hpro']))
        )
    ).order_by(SupportMessage.created_at).all()
    return render_template('admin_support.html', messages=messages)


@admin_bp.route('/support-reply/<int:msg_id>', methods=['POST'])
@login_required
@admin_required
def support_reply(msg_id):
    original = SupportMessage.query.get_or_404(msg_id)
    reply_text = request.form.get('reply')
    if not reply_text:
        flash('متن پاسخ خالی است.', 'danger')
        return redirect(url_for('admin.support_messages'))

    reply = SupportMessage(
        sender_id=None,
        receiver_id=original.sender_id,
        message=reply_text,
        is_from_user=False,
        response_to=original.id
    )
    db.session.add(reply)
    db.session.commit()
    socketio.emit('new_support_reply', {'message': reply_text}, room=f'user_{original.sender_id}')
    flash('پاسخ ارسال شد.', 'success')
    return redirect(url_for('admin.support_messages'))


# ============================================================
# ========== مدیریت اعلان‌ها ==========
# ============================================================

@admin_bp.route('/announcements', methods=['GET', 'POST'])
@login_required
@admin_required
def announcements():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        target_all = request.form.get('target_all') == 'on'
        target_username = request.form.get('target_username')
        expires_at = request.form.get('expires_at')

        if expires_at:
            expires_at = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M')
        else:
            expires_at = datetime.utcnow() + timedelta(days=7)

        if not target_all and target_username:
            user = User.query.filter_by(username=target_username).first()
            if not user:
                flash('کاربری با این نام کاربری وجود ندارد.', 'danger')
                return redirect(url_for('admin.announcements'))

        ann = Announcement(
            admin_id=current_user.id,
            title=title,
            content=content,
            target_all=target_all,
            target_username=target_username if not target_all else None,
            expires_at=expires_at
        )
        db.session.add(ann)
        db.session.commit()

        if target_all:
            socketio.emit('new_announcement', {'title': title, 'content': content}, room='user_room')
        else:
            user = User.query.filter_by(username=target_username).first()
            if user:
                socketio.emit('new_announcement', {'title': title, 'content': content}, room=f'user_{user.id}')
        flash('اعلان ارسال شد.', 'success')
        return redirect(url_for('admin.announcements'))

    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    now = datetime.utcnow()
    return render_template('admin_announcements.html', announcements=announcements, now=now)


# ============================================================
# ========== لاگ‌های سیستم ==========
# ============================================================

@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    logs = AdminActionLog.query.order_by(AdminActionLog.created_at.desc()).limit(50).all()
    return render_template('admin_logs.html', logs=logs)