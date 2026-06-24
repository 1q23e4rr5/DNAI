import numpy as np
import cv2
import joblib
import os
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score
import warnings

# مسیر ذخیره مدل
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'digit_model.pkl')
SCALER_PATH = os.path.join(os.path.dirname(__file__), 'scaler.pkl')

def create_and_train_model():
    """آموزش مدل جدید از صفر"""
    print("🔄 آموزش مدل جدید از صفر...")
    
    # داده‌های digits
    digits = load_digits()
    X, y = digits.data, digits.target
    
    # نرمال‌سازی
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # تقسیم داده
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42
    )
    
    # مدل SVM
    model = SVC(kernel='rbf', gamma='scale', probability=True, random_state=42)
    model.fit(X_train, y_train)
    
    # ارزیابی
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"✅ دقت مدل جدید: {acc * 100:.2f}%")
    
    return model, scaler

def load_or_create_model():
    """بارگذاری مدل، در صورت خطا ساختن مدل جدید"""
    try:
        # تلاش برای بارگذاری
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                model = joblib.load(MODEL_PATH)
                scaler = joblib.load(SCALER_PATH)
            print("✅ مدل موجود بارگذاری شد.")
            return model, scaler
        else:
            raise FileNotFoundError("فایل مدل وجود ندارد")
            
    except (FileNotFoundError, ValueError, Exception) as e:
        print(f"⚠️ خطا در بارگذاری مدل: {e}")
        print("🔄 ساخت مدل جدید...")
        
        # ساخت مدل جدید
        model, scaler = create_and_train_model()
        
        # ذخیره مدل جدید
        joblib.dump(model, MODEL_PATH)
        joblib.dump(scaler, SCALER_PATH)
        print("💾 مدل جدید ذخیره شد.")
        
        return model, scaler

def predict_digit(image_array):
    """
    ورودی: آرایه تصویر (28x28 یا 8x8)
    خروجی: عدد پیش‌بینی شده و احتمال
    """
    try:
        # بارگذاری مدل
        model, scaler = load_or_create_model()
        
        # پیش‌پردازش تصویر
        if image_array.shape != (8, 8):
            # تغییر اندازه به 8x8 و تبدیل به grayscale
            img = cv2.resize(image_array, (8, 8), interpolation=cv2.INTER_AREA)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            img = img.astype(np.float32) / 16.0  # نرمال‌سازی مشابه digits
        else:
            img = image_array.astype(np.float32) / 16.0
        
        # تبدیل به بردار 1D
        img_flat = img.flatten().reshape(1, -1)
        
        # نرمال‌سازی با scaler
        img_scaled = scaler.transform(img_flat)
        
        # پیش‌بینی
        prediction = model.predict(img_scaled)[0]
        proba = model.predict_proba(img_scaled)[0]
        confidence = proba[prediction] * 100
        
        return int(prediction), float(confidence)
        
    except Exception as e:
        print(f"❌ خطا در تشخیص: {e}")
        raise
