import os
import sys
import asyncio
import logging
import re
import uuid
import smtplib
import requests
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from markupsafe import escape
from flask_socketio import SocketIO
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.channels import JoinChannelRequest
from threading import Thread
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_monitor.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE_NUMBER')
SESSION_FILE = 'telegram_session'

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*")

client = None
connected = False
monitoring_active = False
client_thread = None

alerts = []
max_alerts = 100

EMAIL_ENABLED = os.getenv('EMAIL_NOTIFICATIONS', 'false').lower() == 'true'
EMAIL_SERVER = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', '')
EMAIL_TO = os.getenv('EMAIL_TO', '').split(',')

LANGUAGE_CODES = {
    'af': 'Afrikaans',
    'ar': 'Arabic',
    'bg': 'Bulgarian',
    'ca': 'Catalan',
    'cs': 'Czech',
    'da': 'Danish',
    'de': 'German',
    'el': 'Greek',
    'en': 'English',
    'es': 'Spanish',
    'et': 'Estonian',
    'fi': 'Finnish',
    'fr': 'French',
    'he': 'Hebrew',
    'hi': 'Hindi',
    'hr': 'Croatian',
    'hu': 'Hungarian',
    'id': 'Indonesian',
    'it': 'Italian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'lt': 'Lithuanian',
    'lv': 'Latvian',
    'ms': 'Malay',
    'nl': 'Dutch',
    'no': 'Norwegian',
    'pl': 'Polish',
    'pt': 'Portuguese',
    'ro': 'Romanian',
    'ru': 'Russian',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'sq': 'Albanian',
    'sv': 'Swedish',
    'th': 'Thai',
    'tr': 'Turkish',
    'uk': 'Ukrainian',
    'vi': 'Vietnamese',
    'zh': 'Chinese'
}

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

users = {
    1: User(1, 'admin', generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123')))
}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return users.get(int(user_id))

def generate_alert_id():
    return str(uuid.uuid4())

def read_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            lines = []
            for line in file:
                if line.strip() and not line.strip().startswith('#'):
                    lines.extend(line.strip().split())
        return lines
    except Exception as e:
        logger.error(f"Dosya okuma hatası ({filename}): {e}")
        return []

def read_keywords_file():
    try:
        with open('keyword.txt', 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Keywords file read error: {e}")
        return ""

def read_joined_channels():
    try:
        with open('joined_channels.txt', 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        with open('joined_channels.txt', 'w', encoding='utf-8') as file:
            pass
        return []
    except Exception as e:
        logger.error(f"Katılınan kanallar dosyası okuma hatası: {e}")
        return []

def write_joined_channel(channel_url):
    try:
        with open('joined_channels.txt', 'a', encoding='utf-8') as file:
            file.write(f"{channel_url}\n")
        return True
    except Exception as e:
        logger.error(f"Katılınan kanallar dosyası yazma hatası: {e}")
        return False
    
def clean_content(content):
    lines = content.split('\n')
    cleaned_lines = []
    current_category = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('##'):
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            cleaned_lines.append(line)
            current_category = line
        elif line.startswith('#'):
            cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def write_keywords_file(content):
    try:
        cleaned_content = clean_content(content)
        with open('keyword.txt', 'w', encoding='utf-8') as file:
            file.write(cleaned_content)
        return True
    except Exception as e:
        logger.error(f"Keywords file write error: {e}")
        return False

def read_channels_file():
    try:
        with open('channels.txt', 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Channels file read error: {e}")
        return ""

def write_channels_file(content):
    try:
        cleaned_content = clean_content(content)
        with open('channels.txt', 'w', encoding='utf-8') as file:
            file.write(cleaned_content)
        return True
    except Exception as e:
        logger.error(f"Channels file write error: {e}")
        return False

def parse_keywords_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        keywords_dict = {}
        current_category = "GENEL"
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('##'):
                current_category = line[2:].strip()
                if current_category not in keywords_dict:
                    keywords_dict[current_category] = []
            elif not line.startswith('#'):
                if current_category not in keywords_dict:
                    keywords_dict[current_category] = []
                keywords_dict[current_category].append(line.lower())
        
        return keywords_dict
    except Exception as e:
        logger.error(f"Anahtar kelime dosyası parse hatası: {e}")
        return {"GENEL": []}

def check_message_for_keywords(message_text, keywords_dict):
    if not message_text:
        return []
    
    message_text = message_text.lower()
    matched_categories = []
    
    for category, keywords in keywords_dict.items():
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, message_text):
                if category not in matched_categories:
                    matched_categories.append(category)
                break
    
    return matched_categories

def send_email_notification(alert_data):
    if not EMAIL_ENABLED or not EMAIL_USERNAME or not EMAIL_PASSWORD or not EMAIL_TO:
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = ', '.join(EMAIL_TO)
        msg['Subject'] = f"Telegram Uyarısı: {alert_data['chat']}"
        
        html = f"""
        <html>
        <body>
            <h2>Telegram Uyarısı</h2>
            <p><strong>Tarih:</strong> {alert_data['timestamp']}</p>
            <p><strong>Kanal:</strong> {escape(alert_data['chat'])}</p>
            <p><strong>Gönderen:</strong> {escape(alert_data['sender'])}</p>
            <p><strong>Kategoriler:</strong> {', '.join(alert_data['categories'])}</p>
            <hr>
            <p><strong>Mesaj:</strong></p>
            <p>{escape(alert_data['message']).replace('\n', '<br>')}</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(EMAIL_SERVER, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email notification sent for alert from {alert_data['chat']}")
        return True
    
    except Exception as e:
        logger.error(f"Email notification error: {e}")
        return False

async def setup_client():
    global client, connected
    
    if not API_ID or not API_HASH:
        logger.error("API_ID ve API_HASH tanımlanmamış. .env dosyasını kontrol edin.")
        return False
    
    try:
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            if not PHONE:
                logger.error("Telefon numarası tanımlanmamış. .env dosyasını kontrol edin.")
                return False
            
            await client.send_code_request(PHONE)
            code = input("Telegram'dan gelen kodu girin: ")
            
            try:
                await client.sign_in(PHONE, code)
            except SessionPasswordNeededError:
                password = input("İki faktörlü doğrulama şifrenizi girin: ")
                await client.sign_in(password=password)
        
        connected = True
        logger.info("Telegram istemcisi başarıyla bağlandı")
        return True
    
    except Exception as e:
        logger.error(f"Telegram istemcisi kurulum hatası: {e}")
        return False

async def join_channels(channel_urls):
    global client
    
    if not client or not connected:
        logger.error("Telegram istemcisi bağlı değil")
        return False
    
    successful_joins = 0
    failed_joins = 0
    already_joined = 0
    
    joined_channels = read_joined_channels()
    
    for url in channel_urls:
        if url in joined_channels:
            logger.info(f"Kanal zaten katılmış: {url}")
            already_joined += 1
            continue
        
        try:
            channel_entity = await client.get_entity(url)
            await client(JoinChannelRequest(channel_entity))
            logger.info(f"Kanala katıldı: {url}")
            successful_joins += 1
            
            write_joined_channel(url)
            
            await asyncio.sleep(2)
        
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError: {wait_time} saniye bekleniyor. Kanal: {url}")
            await asyncio.sleep(wait_time)
            try:
                channel_entity = await client.get_entity(url)
                await client(JoinChannelRequest(channel_entity))
                logger.info(f"Kanala katıldı (yeniden deneme sonrası): {url}")
                successful_joins += 1
                
                write_joined_channel(url)
            except Exception as e2:
                logger.error(f"Kanal katılım hatası (yeniden deneme sonrası): {url} - {e2}")
                failed_joins += 1
        
        except Exception as e:
            logger.error(f"Kanal katılım hatası: {url} - {e}")
            failed_joins += 1
    
    logger.info(f"Kanal katılımları tamamlandı. Başarılı: {successful_joins}, Başarısız: {failed_joins}, Zaten Katılmış: {already_joined}")
    return True

async def start_monitoring(keywords_dict):
    global client, connected, monitoring_active
    
    if not client or not connected:
        logger.error("Telegram istemcisi bağlı değil")
        return False
    
    monitoring_active = True
    
    @client.on(events.NewMessage)
    async def handle_new_message(event):
        if not monitoring_active:
            return
        
        try:
            message_text = event.message.message
            
            matched_categories = check_message_for_keywords(message_text, keywords_dict)
            
            if matched_categories:
                try:
                    sender = await event.get_sender()
                    sender_name = getattr(sender, 'title', None) or getattr(sender, 'username', None) or getattr(sender, 'first_name', '')
                    
                    if hasattr(sender, 'last_name') and sender.last_name:
                        sender_name += f" {sender.last_name}"
                    
                    chat = await event.get_chat()
                    chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or sender_name
                except:
                    sender_name = "Bilinmeyen"
                    chat_title = "Bilinmeyen Kanal"
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                alert_data = {
                    'id': generate_alert_id(),
                    'timestamp': timestamp,
                    'sender': sender_name,
                    'chat': chat_title,
                    'message': message_text,
                    'categories': matched_categories,
                    'read': False,
                    'important': False,
                    'notes': ''
                }
                
                high_priority_categories = os.getenv('HIGH_PRIORITY_CATEGORIES', '').split(',')
                should_send_email = False

                if EMAIL_ENABLED and high_priority_categories:
                    for category in matched_categories:
                        if category in high_priority_categories:
                            should_send_email = True
                            break

                if should_send_email:
                    send_email_notification(alert_data)
                
                alerts.append(alert_data)
                if len(alerts) > max_alerts:
                    alerts.pop(0)
                
                socketio.emit('new_alert', alert_data)
                
                logger.info(f"Alert: {chat_title} - {matched_categories}")
        
        except Exception as e:
            logger.error(f"Mesaj işleme hatası: {e}")
    
    logger.info("Mesaj izleme başladı")
    return True

async def stop_monitoring():
    global monitoring_active
    monitoring_active = False
    logger.info("Mesaj izleme durduruldu")
    return True

def start_client_and_monitor():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    channel_urls = read_file('channels.txt')
    keywords_dict = parse_keywords_file('keyword.txt')
    
    loop.run_until_complete(setup_client())
    
    if connected:
        loop.run_until_complete(join_channels(channel_urls))
        loop.run_until_complete(start_monitoring(keywords_dict))
        loop.run_forever()

@app.route('/')
@login_required
def index():
    return render_template('index.html', 
                          connected=connected, 
                          monitoring_active=monitoring_active)

@app.route('/alerts')
@login_required
def get_alerts():
    return jsonify(alerts)

@app.route('/start', methods=['POST'])
@login_required
def start():
    global client_thread, monitoring_active
    
    if client_thread is None or not client_thread.is_alive():
        client_thread = Thread(target=start_client_and_monitor)
        client_thread.daemon = True
        client_thread.start()
        flash('Telegram izleme başlatıldı', 'success')
    elif not monitoring_active:
        loop = asyncio.new_event_loop()
        keywords_dict = parse_keywords_file('keyword.txt')
        loop.run_until_complete(start_monitoring(keywords_dict))
        flash('Telegram izleme yeniden başlatıldı', 'success')
    else:
        flash('Telegram izleme zaten çalışıyor', 'info')
    
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
@login_required
def stop():
    global monitoring_active
    
    if monitoring_active:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(stop_monitoring())
        flash('Telegram izleme durduruldu', 'warning')
    else:
        flash('Telegram izleme zaten durdurulmuş', 'info')
    
    return redirect(url_for('index'))

@app.route('/clear', methods=['POST'])
@login_required
def clear_alerts():
    global alerts
    alerts = []
    flash('Tüm uyarılar temizlendi', 'info')
    return redirect(url_for('index'))

@app.route('/keywords', methods=['GET', 'POST'])
@login_required
def manage_keywords():
    if request.method == 'POST':
        if 'content' in request.form:
            success = write_keywords_file(request.form['content'])
            if success:
                flash('Anahtar kelimeler başarıyla güncellendi', 'success')
            else:
                flash('Anahtar kelimeler güncellenirken hata oluştu', 'danger')
        return redirect(url_for('manage_keywords'))
    
    keywords_dict = parse_keywords_file('keyword.txt')
    keywords_content = read_keywords_file()
    return render_template('keywords.html', keywords=keywords_dict, keywords_content=keywords_content,
                          connected=connected, monitoring_active=monitoring_active,
                          active_page='keywords')

@app.route('/channels', methods=['GET', 'POST'])
@login_required
def manage_channels():
    if request.method == 'POST':
        if 'content' in request.form:
            success = write_channels_file(request.form['content'])
            if success:
                flash('Kanallar başarıyla güncellendi', 'success')
            else:
                flash('Kanallar güncellenirken hata oluştu', 'danger')
        return redirect(url_for('manage_channels'))
    
    channels = read_file('channels.txt')
    channels_content = read_channels_file()
    return render_template('channels.html', channels=channels, channels_content=channels_content,
                          connected=connected, monitoring_active=monitoring_active,
                          active_page='channels')

@app.route('/reload', methods=['POST'])
@login_required
def reload_config():
    global monitoring_active
    
    if monitoring_active:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(stop_monitoring())
    
    keywords_dict = parse_keywords_file('keyword.txt')
    channel_urls = read_file('channels.txt')
    
    loop = asyncio.new_event_loop()
    loop.run_until_complete(start_monitoring(keywords_dict))
    
    flash('Yapılandırma yeniden yüklendi', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', 
                          connected=connected, 
                          monitoring_active=monitoring_active,
                          active_page='dashboard')

@app.route('/email-config', methods=['GET', 'POST'])
@login_required
def email_config():
    if request.method == 'POST':
        enabled = request.form.get('email_enabled') == 'on'
        
        env_path = '.env'
        env_lines = []
        
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_lines = f.readlines()
        
        notification_line_found = False
        for i, line in enumerate(env_lines):
            if line.startswith('EMAIL_NOTIFICATIONS='):
                env_lines[i] = f"EMAIL_NOTIFICATIONS={'true' if enabled else 'false'}\n"
                notification_line_found = True
                break
        
        if not notification_line_found:
            env_lines.append(f"EMAIL_NOTIFICATIONS={'true' if enabled else 'false'}\n")
        
        with open(env_path, 'w') as f:
            f.writelines(env_lines)
        
        global EMAIL_ENABLED
        EMAIL_ENABLED = enabled
        
        if enabled:
            server = request.form.get('email_server')
            port = request.form.get('email_port')
            username = request.form.get('email_username')
            password = request.form.get('email_password')
            sender = request.form.get('email_from')
            recipients = request.form.get('email_to')
            categories = request.form.get('high_priority_categories')
            
            for i, line in enumerate(env_lines):
                if line.startswith('EMAIL_SERVER='):
                    env_lines[i] = f"EMAIL_SERVER={server}\n"
                elif line.startswith('EMAIL_PORT='):
                    env_lines[i] = f"EMAIL_PORT={port}\n"
                elif line.startswith('EMAIL_USERNAME='):
                    env_lines[i] = f"EMAIL_USERNAME={username}\n"
                elif line.startswith('EMAIL_PASSWORD=') and password:
                    env_lines[i] = f"EMAIL_PASSWORD={password}\n"
                elif line.startswith('EMAIL_FROM='):
                    env_lines[i] = f"EMAIL_FROM={sender}\n"
                elif line.startswith('EMAIL_TO='):
                    env_lines[i] = f"EMAIL_TO={recipients}\n"
                elif line.startswith('HIGH_PRIORITY_CATEGORIES='):
                    env_lines[i] = f"HIGH_PRIORITY_CATEGORIES={categories}\n"
            
            env_vars = {line.split('=')[0] for line in env_lines if '=' in line}
            if 'EMAIL_SERVER' not in env_vars:
                env_lines.append(f"EMAIL_SERVER={server}\n")
            if 'EMAIL_PORT' not in env_vars:
                env_lines.append(f"EMAIL_PORT={port}\n")
            if 'EMAIL_USERNAME' not in env_vars:
                env_lines.append(f"EMAIL_USERNAME={username}\n")
            if 'EMAIL_PASSWORD' not in env_vars and password:
                env_lines.append(f"EMAIL_PASSWORD={password}\n")
            if 'EMAIL_FROM' not in env_vars:
                env_lines.append(f"EMAIL_FROM={sender}\n")
            if 'EMAIL_TO' not in env_vars:
                env_lines.append(f"EMAIL_TO={recipients}\n")
            if 'HIGH_PRIORITY_CATEGORIES' not in env_vars:
                env_lines.append(f"HIGH_PRIORITY_CATEGORIES={categories}\n")
            
            with open(env_path, 'w') as f:
                f.writelines(env_lines)
            
            global EMAIL_SERVER, EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO
            EMAIL_SERVER = server
            EMAIL_PORT = int(port)
            EMAIL_USERNAME = username
            if password:
                EMAIL_PASSWORD = password
            EMAIL_FROM = sender
            EMAIL_TO = recipients.split(',')
            
            flash('E-posta bildirimleri yapılandırması güncellendi', 'success')
        else:
            flash('E-posta bildirimleri devre dışı bırakıldı', 'info')
        
        return redirect(url_for('email_config'))
    
    high_priority_categories = os.getenv('HIGH_PRIORITY_CATEGORIES', '')
    
    return render_template('email-config.html', 
                          connected=connected, 
                          monitoring_active=monitoring_active,
                          email_enabled=EMAIL_ENABLED,
                          email_server=EMAIL_SERVER,
                          email_port=EMAIL_PORT,
                          email_username=EMAIL_USERNAME,
                          email_from=EMAIL_FROM,
                          email_to=','.join(EMAIL_TO),
                          high_priority_categories=high_priority_categories,
                          active_page='email')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = next((user for user in users.values() if user.username == username), None)
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            error = 'Geçersiz kullanıcı adı veya şifre'
    
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/alerts/<alert_id>/read', methods=['POST'])
@login_required
def mark_alert_read(alert_id):
    global alerts
    
    for alert in alerts:
        if alert.get('id') == alert_id:
            alert['read'] = request.json.get('read', True)
            break
    
    return jsonify({'success': True})

@app.route('/api/alerts/<alert_id>/important', methods=['POST'])
@login_required
def mark_alert_important(alert_id):
    global alerts
    
    for alert in alerts:
        if alert.get('id') == alert_id:
            alert['important'] = request.json.get('important', True)
            break
    
    return jsonify({'success': True})

@app.route('/api/alerts/<alert_id>/notes', methods=['POST'])
@login_required
def update_alert_notes(alert_id):
    global alerts
    
    for alert in alerts:
        if alert.get('id') == alert_id:
            alert['notes'] = request.json.get('notes', '')
            break
    
    return jsonify({'success': True})

@app.route('/api/alerts/<alert_id>/delete', methods=['POST'])
@login_required
def delete_alert(alert_id):
    global alerts
    
    alerts = [alert for alert in alerts if alert.get('id') != alert_id]
    
    return jsonify({'success': True})

@app.route('/api/translate', methods=['POST'])
@login_required
def translate_text_mymemory():
    try:
        data = request.get_json()
        
        if not data or 'text' not in data or 'targetLang' not in data:
            return jsonify({'error': 'Eksik parametreler'}), 400
        
        text = data['text']
        target_lang = data['targetLang'].lower()
        source_lang = data.get('sourceLang', 'auto').lower()
        
        if not text.strip():
            return jsonify({'error': 'Çevrilecek metin boş olamaz'}), 400
            
        if len(text) > 5000:
            app.logger.warning(f"Çok uzun metin çevriliyor: {len(text)} karakter")
            
        if source_lang == 'auto':
            source_lang = ''  
            langpair = f"|{target_lang}"
        else:
            langpair = f"{source_lang}|{target_lang}"
            
        api_url = "https://api.mymemory.translated.net/get"
        
        # API parametreleri
        params = {
            "q": text,
            "langpair": langpair,
            # "de": "your@email.com"  # İsteğe bağlı: Günlük limit artırmak için mail eklenebilir
        }
        
        email = data.get('email')
        if email:
            params["de"] = email
            
        mt = data.get('mt')
        if mt:
            params["mt"] = '1' if mt else '0'
            
        app.logger.info(f"MyMemory API isteği: {len(text)} karakter, {langpair}")
        response = requests.get(api_url, params=params, timeout=10)
        
        if response.status_code != 200:
            app.logger.error(f"MyMemory API HTTP hatası: {response.status_code}")
            return jsonify({'error': f'API hatası: {response.status_code}'}), 500
            
        response_data = response.json()
        
        if 'responseData' in response_data and 'translatedText' in response_data['responseData']:
            translated_text = response_data['responseData']['translatedText']
            match_quality = response_data['responseData'].get('match', 0)
            
            if match_quality < 0.5:
                app.logger.warning(f"Düşük eşleşme kalitesi: {match_quality}")
                
            quota_info = None
            if 'quotaFinished' in response_data and response_data['quotaFinished']:
                app.logger.warning("MyMemory API günlük kota aşıldı")
                quota_info = "Günlük kota aşıldı. E-posta ekleyerek limiti artırabilirsiniz."
                
            warnings = []
            if 'responseDetails' in response_data and response_data['responseDetails'] != '':
                if 'QUERY LIMIT' in response_data['responseDetails']:
                    warnings.append("Sorgu limiti uyarısı: " + response_data['responseDetails'])
                elif 'NO MATCH FOUND' in response_data['responseDetails']:
                    warnings.append("Eşleşme bulunamadı: " + response_data['responseDetails'])
                    
            result = {
                'success': True,
                'originalText': text,
                'translatedText': translated_text,
                'targetLang': target_lang,
                'match': match_quality
            }
            
            if source_lang:
                result['sourceLang'] = source_lang
            if quota_info:
                result['quotaInfo'] = quota_info
            if warnings:
                result['warnings'] = warnings
                
            return jsonify(result)
        else:
            app.logger.error(f"API yanıtı beklenen formatta değil: {response_data}")
            
            error_msg = "Çeviri yapılamadı: API yanıtı geçersiz format"
            if 'responseDetails' in response_data and response_data['responseDetails']:
                error_msg = f"Çeviri hatası: {response_data['responseDetails']}"
                
            return jsonify({'error': error_msg}), 500
    
    except requests.exceptions.Timeout:
        app.logger.error("MyMemory API zaman aşımı")
        return jsonify({'error': 'Çeviri API zaman aşımına uğradı'}), 504
    except requests.exceptions.RequestException as req_err:
        app.logger.error(f"MyMemory API bağlantı hatası: {str(req_err)}")
        return jsonify({'error': 'Çeviri API\'sine bağlanılamadı'}), 503
    except Exception as e:
        app.logger.error(f"Beklenmeyen hata: {str(e)}")
        return jsonify({'error': f'Beklenmeyen bir hata oluştu: {str(e)}'}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)