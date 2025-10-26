import os
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# LOKAL TEST ÜÇÜN ƏLAVƏ EDİLDİ: .env faylını oxuyur
try:
    from dotenv import load_dotenv 
    load_dotenv() 
except ImportError:
    print("Xəbərdarlıq: 'python-dotenv' quraşdırılmayıb. Mühit dəyişənləri birbaşa sistemdən oxunacaq.")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ========================
# KONFİQURASİYA (ENV VARIABLES MƏLUMATLARI OXUNUR)
# ========================
USERNAME = os.environ.get("BEU_USERNAME")
PASSWORD = os.environ.get("BEU_PASSWORD")
EMAIL_FROM = os.environ.get("GMAIL_USER")
EMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_TO_STRING = os.environ.get("RECIPIENTS", "")
EMAIL_TO_LIST = [addr.strip() for addr in EMAIL_TO_STRING.split(',') if addr.strip()]

LOGIN_URL = "https://my.beu.edu.az/?mod=login"
GRADES_URL = "https://my.beu.edu.az/?mod=grades"

STORED_FILE = "grades.json" 

# YALNIZ TƏLƏB OLUNAN SDF1, SDF2, SEM, TSI Sütunları İzlənilir
# İndekslər sizin HTML kodunuza əsaslanır: (0-dan başlayır)
TRACKED_COLUMNS = {
    "SDF1": 7,  # Semestr daxili fəaliyyət 1
    "SDF2": 8,  # Semestr daxili fəaliyyət 2
    "SEM": 9,   # Seminar (Məşğələ) balı
    "TSI": 10   # Tələbənin Sərbəst İşi balı
}

# ========================
# EMAIL FUNKSİYASI
# ========================
def send_email(subject, body):
    if not EMAIL_TO_LIST:
        print("❌ E-mail göndərilmədi: Alıcı siyahısı boşdur.")
        return
        
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = ", ".join(EMAIL_TO_LIST)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        # SMTP Serveri ilə əlaqə qurulur
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO_LIST, msg.as_string()) 
            print(f"📧 E-mail {len(EMAIL_TO_LIST)} alıcıya uğurla göndərildi!")
    except Exception as e:
        print("❌ E-mail göndərilə bilmədi. Gmail App Şifrəsini və ya icazələri yoxlayın:", e)

# ========================
# Qiymətləri çəkmək
# ========================
def fetch_grades():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox") 
    
    # ChromeDriver-i başlatmaq üçün kod (Lokal və Serverə uyğun)
    chrome_binary_path = "/usr/bin/chromium" 
    
    # Əgər chrome bu yolda tapılsa, onu ikilik fayl kimi təyin edirik.
    # Bu, Selenium Manager-ə sürücünü tapmaqda kömək edir.
    if os.path.exists(chrome_binary_path):
        options.binary_location = chrome_binary_path

    try:
        # Service funksiyasını driversiz çağırırıq ki, Selenium Manager 
        # özü sürücünü tapsın (yeni Selenium-un default davranışı)
        driver = webdriver.Chrome(options=options)
        
    except Exception as e:
        # Əgər hələ də xəta verirsə, bu, Chrome'un ümumiyyətlə 
        # quraşdırılmaması deməkdir.
        raise Exception(f"❌ ChromeDriver-i başlada bilmədi: {e}. Zəhmət olmasa, 'railway.toml' faylını yoxlayın.")

    driver.get(LOGIN_URL)
    
    # LOGIN
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)

    # GRADES SƏHİFƏSİNƏ KEÇİŞ
    driver.get(GRADES_URL)

    # Cədvəlin yüklənməsini gözləyirik 
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.box"))
        )
        print("✅ Hesaba uğurla giriş edildi")
    except:
        driver.quit()
        raise Exception("❌ Qiymət cədvəli tapılmadı. Giriş uğursuz ola bilər.")

    # Table HTML-ni çəkirik
    table_html = driver.execute_script("return document.querySelector('table.table.box').outerHTML;")
    driver.quit()

    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")[1:]  # Başlıq sətrini atırıq
    grades = []

    # Bütün izlənilən sütunları çəkmək üçün minimum sütun sayını müəyyən edirik
    required_cols = max(TRACKED_COLUMNS.values()) + 1
    
    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        
        # 'Cəmi akts' sətrini və ya yarımçıq sətirləri keçirik
        if len(cols) < required_cols or "Cəmi akts" in cols[0]:
            continue
            
        grade_data = {}
        grade_data["ders_kodu"] = cols[0]
        grade_data["ders_adi"] = cols[4]
        
        # Yalnız tələb olunan 4 sütun əlavə edilir
        for col_name, index in TRACKED_COLUMNS.items():
            key = col_name.lower() 
            grade_data[key] = cols[index] or None # Boş dəyərləri 'None' kimi saxlayır
            
        grades.append(grade_data)
        
    return grades

# ========================
# Fayldan oxu / yaz
# ========================
def load_previous_grades():
    if not os.path.exists(STORED_FILE):
        return []
    try:
        with open(STORED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Köhnə fayl zədələnib. Boş siyahı ilə davam edilir.")
        return []

def save_grades(grades):
    with open(STORED_FILE, "w", encoding="utf-8") as f:
        # ensure_ascii=False ilə Azərbaycan hərflərini (ə, ö, ü) düzgün saxlayır
        json.dump(grades, f, ensure_ascii=False, indent=2)

# ========================
# Müqayisə və xəbər
# ========================
def compare_and_notify(old, new):
    changes_detected = False
    old_dict = {item['ders_kodu']: item for item in old} 
    
    for n in new:
        o = old_dict.get(n['ders_kodu'])
        if not o:
            continue
            
        body_msg = ""
        
        # Yalnız 4 sütunda (SDF1, SDF2, SEM, TSI) dəyişiklik yoxlanılır
        for col_name in TRACKED_COLUMNS.keys():
            key = col_name.lower()
            
            old_value = o.get(key)
            new_value = n.get(key)
            
            # None dəyərləri "" olaraq qəbul edirik ki, müqayisə düzgün işləsin
            old_val_clean = old_value if old_value else ""
            new_val_clean = new_value if new_value else ""

            # Qiymət dəyişdikdə
            if old_val_clean != new_val_clean:
                changes_detected = True
                
                body_msg += f"Dəyişiklik aşkar edildi: **{col_name}**\n"
                body_msg += f"Dərs: {n['ders_adi']} ({n['ders_kodu']})\n"
                #body_msg += f"Köhnə Qiymət: {old_val_clean or 'Yoxdur/Boş'}\n"
                #body_msg += f"Yeni Qiymət: {new_val_clean or 'Yoxdur/Boş'}\n\n"
        
        if body_msg:
            subject = f"📢 YENİ DƏYİŞİKLİK: {n['ders_adi']}"
            send_email(subject, body_msg)

    if not changes_detected:
        print("🔄 Dəyişiklik yoxdur.")

# ========================
# MAIN LOOP
# ========================
if __name__ == "__main__":
    
    # Müvəqqəti yoxlama kodu
    print("Dəyişənlərin vəziyyəti:")
    print(f"BEU_USERNAME: {USERNAME}")
    print(f"BEU_PASSWORD: {'*' * len(PASSWORD) if PASSWORD else None}") # Şifrəni göstərmirik
    print(f"GMAIL_USER: {EMAIL_FROM}")
    print(f"GMAIL_APP_PASSWORD: {'*' * len(EMAIL_PASS) if EMAIL_PASS else None}")
    print(f"RECIPIENTS: {EMAIL_TO_STRING}") 
    print("-" * 30)


    # Bütün vacib dəyişənlərin təyin edilib-edilməməsini yoxlayır
    if not (USERNAME and PASSWORD and EMAIL_FROM and EMAIL_PASS and EMAIL_TO_LIST):
        print("FATAL XƏTA: Zəhmət olmasa bütün mühit dəyişənlərini təyin edin və ya `.env` faylını düzgün qurun.")
        exit(1)

    while True: 
        start_time = time.time()
        
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🔑 Qiymətlər yoxlanılır...")
            current = fetch_grades()
            previous = load_previous_grades()
            
            if not previous:
                print("ℹ️ İlk yoxlama icra edildi. Qiymətlər fayla saxlanılır.")
            else:
                compare_and_notify(previous, current)
            
            save_grades(current)
            
        except Exception as e:
            # Xəta çıxarsa, e-mail göndərməyə çalışır (əgər e-mail dəyişənləri varsa)
            print(f"❌ Əsas dövrdə xəta baş verdi: {e}")
            if EMAIL_FROM and EMAIL_PASS and EMAIL_TO_LIST:
                 send_email("KRİTİK XƏTA: Qiymət İzləyicisi", f"Qiymət çəkilməsi zamanı xəta: {e}")
            
        # 1 dəqiqədən bir işləməsi üçün vaxt tənzimlənir
        elapsed_time = time.time() - start_time
        sleep_duration = max(0, 60 - elapsed_time)
        
        print(f"⏸️ {int(sleep_duration)} saniyə gözlənilir...")
        time.sleep(sleep_duration)