import numpy as np
import os
import cv2
import joblib
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
import random

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'digit_model.pkl')
SCALER_PATH = os.path.join(os.path.dirname(__file__), 'scaler.pkl')


def create_and_train_model():
    print("📊 آموزش مدل تشخیص عدد...")
    
    # ============================================================
    # بارگذاری دیتاست digits (اعداد 0-9)
    # ============================================================
    digits = load_digits()
    X = digits.images  # تصاویر 8x8
    y = digits.target  # برچسب‌ها 0-9
    
    print(f"✅ تعداد نمونه‌ها: {len(X)}")
    print(f"✅ ابعاد هر تصویر: {X[0].shape}")
    print(f"✅ تعداد کلاس‌ها: {len(np.unique(y))}")
    
    # ============================================================
    # پیش‌پردازش داده
    # ============================================================
    n_samples = len(X)
    X_flat = X.reshape(n_samples, -1)  # تبدیل به بردار 64 عنصری
    
    # نرمال‌سازی
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_flat)
    
    # تقسیم به آموزش و تست
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42
    )
    
    print(f"✅ داده‌های آموزش: {len(X_train)}")
    print(f"✅ داده‌های تست: {len(X_test)}")
    
    # ============================================================
    # ساخت مدل
    # ============================================================
    model = MLPClassifier(
        hidden_layer_sizes=(128, 64),
        activation='relu',
        solver='adam',
        max_iter=200,  # افزایش تعداد تکرارها
        random_state=42,
        verbose=True
    )
    
    # آموزش
    model.fit(X_train, y_train)
    
    # ارزیابی
    accuracy = model.score(X_test, y_test)
    print(f"✅ دقت مدل: {accuracy:.2%}")
    
    # ذخیره مدل
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"💾 مدل ذخیره شد: {MODEL_PATH}")
    
    return model, scaler


def load_or_create_model():
    if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
        print("📂 بارگذاری مدل موجود...")
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        
        # تست سریع مدل
        test_model(model, scaler)
        
        return model, scaler
    else:
        print("⚠️ مدل یافت نشد. ایجاد مدل جدید...")
        return create_and_train_model()


def test_model(model, scaler):
    """تست مدل با چند نمونه تصادفی"""
    print("🧪 تست مدل...")
    digits = load_digits()
    X = digits.images
    y = digits.target
    
    indices = np.random.choice(len(X), 5, replace=False)
    for idx in indices:
        img_flat = X[idx].reshape(1, -1)
        img_scaled = scaler.transform(img_flat)
        pred = model.predict(img_scaled)
        probs = model.predict_proba(img_scaled)
        confidence = np.max(probs[0]) * 100
        print(f"   عدد واقعی: {y[idx]} → پیش‌بینی: {pred[0]} (دقت: {confidence:.1f}%)")


model, scaler = load_or_create_model()


def preprocess_image(img):
    """پیش‌پردازش تصویر برای مدل"""
    try:
        # تبدیل به خاکستری
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # بهبود کیفیت
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.equalizeHist(gray)
        
        # آستانه‌گیری معکوس (عدد سفید روی پس‌زمینه سیاه)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        
        # پیدا کردن کانتور عدد
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # بزرگترین کانتور
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            
            # اگر مساحت کافی است
            if area > 100:
                x, y, w, h = cv2.boundingRect(largest)
                
                # اضافه کردن حاشیه
                margin = 4
                x = max(0, x - margin)
                y = max(0, y - margin)
                w = min(thresh.shape[1] - x, w + 2 * margin)
                h = min(thresh.shape[0] - y, h + 2 * margin)
                
                # برش عدد
                roi = thresh[y:y+h, x:x+w]
                
                # تغییر اندازه به 8x8 (برای مدل digits)
                roi = cv2.resize(roi, (8, 8), interpolation=cv2.INTER_AREA)
                
                # نرمال‌سازی
                roi = roi.astype('float32')
                roi = roi.reshape(1, -1)
                
                return roi
        
        # اگر کانتوری پیدا نشد
        resized = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        resized = resized.astype('float32')
        resized = resized.reshape(1, -1)
        return resized
        
    except Exception as e:
        print(f"⚠️ خطا در پیش‌پردازش: {e}")
        return np.zeros((1, 64), dtype='float32')


def predict_digit(img):
    """تشخیص عدد از تصویر"""
    try:
        # پیش‌پردازش
        processed = preprocess_image(img)
        
        # نرمال‌سازی با scaler
        processed_scaled = scaler.transform(processed)
        
        # پیش‌بینی
        prediction = model.predict(processed_scaled)
        predicted_number = int(prediction[0])
        
        # احتمال (برای دقت)
        probabilities = model.predict_proba(processed_scaled)
        confidence = float(np.max(probabilities[0]) * 100)
        confidence = min(confidence, 99.9)
        
        # اگر اطمینان خیلی کم است
        if confidence < 30:
            return None, 0
        
        print(f"✅ عدد تشخیص داده شده: {predicted_number} (دقت: {confidence:.1f}%)")
        return predicted_number, confidence
        
    except Exception as e:
        print(f"⚠️ خطا در تشخیص: {e}")
        return None, 0


# ============================================================
# تابع برای تست دستی
# ============================================================
if __name__ == "__main__":
    print("🧪 تست مدل با داده‌های test...")
    digits = load_digits()
    X = digits.images
    y = digits.target
    
    # تست روی 10 نمونه تصادفی
    indices = np.random.choice(len(X), 10, replace=False)
    correct = 0
    for idx in indices:
        img = X[idx]
        # تبدیل به تصویر رنگی برای شبیه‌سازی
        img_rgb = cv2.cvtColor((img * 16).astype('uint8'), cv2.COLOR_GRAY2BGR)
        pred, conf = predict_digit(img_rgb)
        actual = y[idx]
        if pred == actual:
            correct += 1
        print(f"   واقعی: {actual} → پیش‌بینی: {pred} (دقت: {conf:.1f}%)")
    
    print(f"✅ دقت کلی: {correct/10 * 100:.1f}%")