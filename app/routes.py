from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt, socketio
from app.models import User, RegistrationRequest, ReferralCode, DetectionHistory, SupportMessage, Announcement
from app.ml.model import predict_digit
from openai import OpenAI
import base64
import numpy as np
import cv2
from datetime import datetime, timedelta
from flask_socketio import emit, join_room, leave_room
import uuid
import os
import re
import random
import requests
import json

bp = Blueprint('main', __name__)


# ============================================================
# ========== تنظیمات GapGPT (اولویت اول) ==========
# ============================================================

GAPGPT_API_KEY = "sk-1YvH8QE5sTBq7nKer6dKzYHCHiLBMlQmirM0jq6hYH4f5HaH"
GAPGPT_BASE_URL = "https://api.gapgpt.app/v1"

try:
    gapgpt_client = OpenAI(
        base_url=GAPGPT_BASE_URL,
        api_key=GAPGPT_API_KEY,
        timeout=30
    )
    print("✅ GapGPT client initialized")
except Exception as e:
    print(f"⚠️ GapGPT error: {e}")
    gapgpt_client = None


def call_gapgpt_api(messages, max_tokens=300, temperature=0.7):
    if not gapgpt_client:
        return None, "GapGPT not available"
    try:
        response = gapgpt_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content.strip(), None
    except Exception as e:
        return None, str(e)


AKI_API_KEY = "04c69e62-c9ef-491e-a152-5a5c24bc9751"
AKI_API_URL = "https://aki.io/v1/chat/completions"


def call_aki_api(messages, max_tokens=300, temperature=0.7):
    try:
        headers = {
            'Authorization': f'Bearer {AKI_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'gpt-3.5-turbo',
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature
        }
        response = requests.post(AKI_API_URL, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        result = response.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content'].strip(), None
        return None, 'Invalid response'
    except Exception as e:
        return None, str(e)


def get_ai_response(message):
    """دریافت پاسخ از هوش مصنوعی با پرامپت کامل"""
    
    system_prompt = """
شما یک دستیار هوشمند، حرفه‌ای و دقیق برای سایت "تشخیص عدد" هستید.

=== هویت شما ===
نام شما: DN Assistant
پلتفرم: DN (Digital Number)
نقش شما: راهنمای کامل کاربران در تمام بخش‌های سایت

=== قوانین طلایی پاسخگویی ===

1️⃣ ادب و احترام
- همیشه با لحنی محترمانه، دوستانه و حرفه‌ای پاسخ دهید.
- از کلمات تشکرآمیز مانند "متشکرم"، "خوشحالم که کمک کردم" استفاده کنید.

2️⃣ مختصر و مفید
- پاسخ‌ها را تا حد امکان مختصر و دقیق بنویسید (حداکثر ۳-۴ خط).
- از پاراگراف‌بندی و خطوط جداگانه برای وضوح استفاده کنید.
- از ایموجی‌های مناسب برای جذابیت استفاده کنید.

3️⃣ فقط موضوعات مرتبط
- فقط به سوالات مرتبط با سایت "تشخیص عدد" پاسخ دهید.
- اگر سوال خارج از حیطه است، مودبانه توضیح دهید.

=== موضوعات مجاز برای پاسخگویی ===

📌 تشخیص عدد: نحوه تشخیص با ماوس، آپلود عکس، تنظیمات قلم، درصد دقت، تاریخچه

📌 انواع اکانت:
- Noob (رایگان): ۵ بار ورود، ۳۰ دقیقه زمان، امکانات پایه
- Rich (ویژه): ورود نامحدود، آپلود عکس، چت با هوش مصنوعی
- HPRO (اشرافی): تمام امکانات Rich + کیفیت بالا + تم اشرافی

📌 ثبت‌نام و ورود: نحوه ثبت‌نام، ورود، کدهای معرف

📌 پشتیبانی: نحوه ارسال پیام، زمان پاسخگویی

=== پاسخ‌های نمونه ===

سوال درباره تشخیص عدد:
"📝 برای تشخیص عدد، روی صفحه سفید (Canvas) عدد را با ماوس بنویسید و روی دکمه 🤖 تشخیص کلیک کنید. همچنین می‌توانید از بخش آپلود عکس استفاده کنید."

سوال درباره انواع اکانت:
"👑 سایت ما سه نوع اکانت دارد:
🟢 Noob: رایگان - ۵ بار ورود
🟡 Rich: ویژه - ورود نامحدود + چت با AI
🔴 HPRO: اشرافی - بهترین امکانات"

سوال خارج از حیطه:
"🙏 متشکرم از سوال شما. من فقط درباره سایت تشخیص عدد اطلاعات دارم. لطفاً سوال خود را در مورد این سایت مطرح کنید."

=== قوانین نهایی ===
1. همیشه با احترام و ادب پاسخ دهید.
2. پاسخ‌ها را مختصر و مفید بنویسید.
3. فقط به سوالات مرتبط با سایت پاسخ دهید.
4. از ایموجی‌های مناسب استفاده کنید.
"""

    # GapGPT
    reply, error = call_gapgpt_api([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ])
    if reply:
        return reply
    
    # AKI.IO (Fallback)
    reply, error = call_aki_api([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ])
    if reply:
        return reply
    
    return "❌ سرویس هوش مصنوعی در دسترس نیست. لطفاً بعداً تلاش کنید."


def detect_number_with_ai(image_data):
    # GapGPT
    messages = [
        {"role": "system", "content": "شما یک سیستم تشخیص عدد هستید. فقط عدد را برگردان."},
        {"role": "user", "content": [
            {"type": "text", "text": "عدد داخل تصویر را تشخیص بده:"},
            {"type": "image_url", "image_url": {"url": image_data}}
        ]}
    ]
    reply, error = call_gapgpt_api(messages, max_tokens=50, temperature=0.1)
    if reply:
        numbers = re.findall(r'\d+', reply)
        if numbers:
            return int(numbers[0]), 92.0, 'gapgpt'
    
    # AKI.IO
    reply, error = call_aki_api(messages, max_tokens=50, temperature=0.1)
    if reply:
        numbers = re.findall(r'\d+', reply)
        if numbers:
            return int(numbers[0]), 85.0, 'aki'
    
    return None, 0, None


def enhance_canvas_image(image_data, quality='normal'):
    try:
        header, encoded = image_data.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            return image_data
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        height, width = gray.shape
        if quality == 'super':
            scale = 4
        elif quality == 'enhanced':
            scale = 2
        else:
            scale = 1
        
        if scale > 1:
            new_width = width * scale
            new_height = height * scale
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        gray = cv2.equalizeHist(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        
        img_enhanced = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        _, buffer = cv2.imencode('.png', img_enhanced)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
        
    except Exception as e:
        print(f"⚠️ Error enhancing image: {e}")
        return image_data


# ============================================================
# ========== مسیرهای اصلی ==========
# ============================================================

@bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('main.panel'))
    return redirect(url_for('main.login'))


# ============================================================
# ========== ✅ ورود و خروج ==========
# ============================================================

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('main.panel'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            if user.is_blocked:
                flash('حساب کاربری شما مسدود شده است.', 'danger')
                return render_template('login.html')
            
            if user.is_noob():
                if user.entry_count >= user.allowed_entries:
                    flash('تعداد دفعات ورود مجاز شما به پایان رسیده است.', 'danger')
                    return render_template('login.html')
                user.session_start = datetime.utcnow()
                db.session.commit()
            
            login_user(user)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            emit('user_online', {'username': user.username, 'type': user.account_type}, room='admin_room', namespace='/')
            flash(f'خوش آمدید {user.username}!', 'success')
            
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('main.panel'))

        flash('نام کاربری یا رمز عبور اشتباه است.', 'danger')

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    user = current_user
    if user.is_noob() and user.session_start:
        user.entry_count += 1
        user.session_start = None
        db.session.commit()
    logout_user()
    flash('با موفقیت خارج شدید.', 'info')
    return redirect(url_for('main.login'))


@bp.route('/register-request', methods=['GET', 'POST'])
def register_request():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        account_type = request.form.get('account_type')
        referral = request.form.get('referral_code')

        if User.query.filter_by(username=username).first():
            flash('این نام کاربری قبلاً ثبت شده است.', 'danger')
            return redirect(url_for('main.register_request'))

        if referral:
            ref = ReferralCode.query.filter_by(code=referral).first()
            if ref and ref.is_golden and ref.is_active:
                user = User(username=username, account_type='hpro', is_active=True)
                user.set_password(password)
                db.session.add(user)
                ref.used_count += 1
                db.session.commit()
                flash('اکانت HPRO شما با موفقیت ساخته شد!', 'success')
                return redirect(url_for('main.login'))

        req = RegistrationRequest(
            username=username,
            password=password,
            account_type=account_type,
            referral_code=referral,
            status='pending'
        )
        db.session.add(req)
        db.session.commit()
        
        emit('new_registration_request', {'username': username}, room='admin_room', namespace='/')
        flash('درخواست شما ثبت شد و منتظر تایید ادمین است.', 'info')
        return redirect(url_for('main.login'))

    return render_template('register_request.html')


@bp.route('/panel')
@login_required
def panel():
    user = current_user

    if user.is_admin:
        flash('شما ادمین هستید. لطفاً از پنل ادمین استفاده کنید.', 'warning')
        return redirect(url_for('admin.dashboard'))

    if not user.is_active:
        logout_user()
        flash('حساب کاربری شما غیرفعال شده است.', 'danger')
        return redirect(url_for('main.login'))

    if user.is_blocked:
        logout_user()
        flash('حساب کاربری شما مسدود شده است.', 'danger')
        return redirect(url_for('main.login'))

    if user.is_noob() and user.session_start:
        elapsed = (datetime.utcnow() - user.session_start).total_seconds()
        if elapsed > 1800:
            user.entry_count += 1
            user.session_start = None
            db.session.commit()
            logout_user()
            flash('زمان جلسه شما به پایان رسید.', 'danger')
            return redirect(url_for('main.login'))

    history = DetectionHistory.query.filter_by(user_id=user.id).order_by(
        DetectionHistory.created_at.desc()
    ).limit(10).all()

    announcements = Announcement.query.filter(
        (Announcement.target_all == True) | (Announcement.target_username == user.username)
    ).filter(Announcement.expires_at > datetime.utcnow()).all()

    remaining_time = 0
    if user.is_noob() and user.session_start:
        elapsed = (datetime.utcnow() - user.session_start).total_seconds()
        remaining_time = max(0, 1800 - elapsed)

    return render_template('user_panel.html',
                           user=user,
                           history=history,
                           announcements=announcements,
                           remaining_time=int(remaining_time))


# ============================================================
# ========== تشخیص عدد ==========
# ============================================================

@bp.route('/detect-canvas', methods=['POST'])
@login_required
def detect_canvas():
    user = current_user
    if user.is_admin:
        return jsonify({'error': 'ادمین نمی‌تواند تشخیص دهد'}), 403

    data = request.get_json()
    image_data = data.get('image')
    if not image_data:
        return jsonify({'error': 'تصویر ارسال نشد'}), 400

    try:
        quality = 'normal'
        if user.is_hpro():
            quality = 'super'
        elif user.is_rich():
            quality = 'enhanced'
        
        enhanced_image = enhance_canvas_image(image_data, quality)
        
        number, confidence, model_used = detect_number_with_ai(enhanced_image)
        
        if number is None:
            header, encoded = image_data.split(',', 1)
            img_bytes = base64.b64decode(encoded)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            number, confidence = predict_digit(img)
            model_used = 'local'
        
        if number is None:
            return jsonify({'error': 'عددی تشخیص داده نشد. لطفاً عدد را واضح‌تر بنویسید.'}), 400
        
        filename = f"{uuid.uuid4()}.png"
        path = os.path.join('static/uploads', filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        header, encoded = image_data.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        cv2.imwrite(path, img)

        history = DetectionHistory(
            user_id=user.id,
            image_path=path,
            detected_number=number,
            confidence=confidence,
            method='canvas',
            model_used=model_used
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({
            'number': number,
            'confidence': confidence,
            'model': model_used
        })
        
    except Exception as e:
        print(f"Error in detect_canvas: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/detect-upload', methods=['POST'])
@login_required
def detect_upload():
    user = current_user
    if user.is_admin:
        return jsonify({'error': 'ادمین نمی‌تواند تشخیص دهد'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'فایلی انتخاب نشده'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'فایل معتبر نیست'}), 400

    try:
        file_bytes = file.read()
        image_base64 = base64.b64encode(file_bytes).decode('utf-8')
        image_data = f"data:image/jpeg;base64,{image_base64}"
        
        number, confidence, model_used = detect_number_with_ai(image_data)
        
        if number is None:
            np_arr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            number, confidence = predict_digit(img)
            model_used = 'local'
        
        if number is None:
            return jsonify({'error': 'عددی تشخیص داده نشد. لطفاً عکس دیگری امتحان کنید.'}), 400
        
        filename = f"{uuid.uuid4()}.jpg"
        path = os.path.join('static/uploads', filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        np_arr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        cv2.imwrite(path, img)

        history = DetectionHistory(
            user_id=user.id,
            image_path=path,
            detected_number=number,
            confidence=confidence,
            method='upload',
            model_used=model_used
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({
            'number': number,
            'confidence': confidence,
            'model': model_used
        })
        
    except Exception as e:
        print(f"Error in detect_upload: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/ai-chat', methods=['POST'])
@login_required
def ai_chat():
    user = current_user
    if user.is_admin:
        return jsonify({'error': 'ادمین نمی‌تواند از هوش مصنوعی استفاده کند'}), 403

    if not user.can_use_ai():
        return jsonify({'error': 'این قابلیت فقط برای اکانت‌های Rich و HPRO در دسترس است.'}), 403

    data = request.get_json()
    msg = data.get('message')
    if not msg:
        return jsonify({'error': 'پیام خالی است'}), 400

    reply = get_ai_response(msg)
    return jsonify({'reply': reply})


@bp.route('/support-send', methods=['POST'])
@login_required
def support_send():
    user = current_user
    if user.is_admin:
        return jsonify({'error': 'ادمین نمی‌تواند پیام ارسال کند'}), 403

    if user.is_noob():
        fake_responses = [
            'پیام شما به پشتیبانی ارسال شد. به زودی پاسخ داده می‌شود.',
            'درخواست شما ثبت شد. کارشناسان ما در اسرع وقت پاسخ می‌دهند.'
        ]
        return jsonify({'reply': random.choice(fake_responses)})

    data = request.get_json()
    msg = data.get('message')
    if not msg:
        return jsonify({'error': 'پیام خالی است'}), 400

    support_msg = SupportMessage(
        sender_id=user.id,
        message=msg,
        is_from_user=True,
        is_read=False
    )
    db.session.add(support_msg)
    db.session.commit()

    emit('new_support_message', {
        'user': user.username,
        'message': msg,
        'msg_id': support_msg.id
    }, room='admin_room', namespace='/')

    return jsonify({'success': True})


@bp.route('/support-get-replies')
@login_required
def support_get_replies():
    user = current_user
    if user.is_admin:
        return jsonify({'replies': []})

    if user.is_noob():
        return jsonify({'replies': [
            {'message': 'پشتیبانی: درخواست شما ثبت شد.', 'is_from_user': False}
        ]})

    msgs = SupportMessage.query.filter(
        (SupportMessage.sender_id == user.id) | (SupportMessage.receiver_id == user.id)
    ).order_by(SupportMessage.created_at).all()

    replies = []
    for m in msgs:
        replies.append({
            'message': m.message,
            'is_from_user': m.is_from_user,
            'created_at': m.created_at.isoformat()
        })

    unread = SupportMessage.query.filter_by(sender_id=user.id, is_read=False).all()
    for m in unread:
        m.is_read = True
    db.session.commit()

    return jsonify({'replies': replies})


# ============================================================
# ========== SocketIO ==========
# ============================================================

@socketio.on('connect', namespace='/')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        if not current_user.is_admin:
            emit('user_online', {
                'username': current_user.username,
                'type': current_user.account_type
            }, room='admin_room')


@socketio.on('disconnect', namespace='/')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')
        if not current_user.is_admin:
            emit('user_offline', {
                'username': current_user.username
            }, room='admin_room')