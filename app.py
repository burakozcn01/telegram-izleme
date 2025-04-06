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
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func
from bs4 import BeautifulSoup

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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///telegram_monitor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

client = None
connected = False
monitoring_active = False
client_thread = None

max_alerts = 100

EMAIL_ENABLED = os.getenv('EMAIL_NOTIFICATIONS', 'false').lower() == 'true'
EMAIL_SERVER = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', '')
EMAIL_TO = os.getenv('EMAIL_TO', '').split(',')

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class Alert(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    timestamp = db.Column(db.String(30), nullable=False)
    sender = db.Column(db.String(100), nullable=False)
    chat = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    categories = db.Column(db.JSON, nullable=False)
    filtered = db.Column(db.Boolean, default=True) 
    read = db.Column(db.Boolean, default=False)
    important = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, default='')

class JoinedChannel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(100), unique=True, nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                password_hash=generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123'))
            )
            db.session.add(admin_user)
            db.session.commit()



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
        logger.error(f"File read error ({filename}): {e}")
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
        with app.app_context():
            channels = JoinedChannel.query.all()
            return [channel.url for channel in channels]
    except Exception as e:
        logger.error(f"Error reading joined channels from DB: {e}")
        return []

def write_joined_channel(channel_url):
    try:
        with app.app_context():
            if not JoinedChannel.query.filter_by(url=channel_url).first():
                new_channel = JoinedChannel(url=channel_url)
                db.session.add(new_channel)
                db.session.commit()
            return True
    except Exception as e:
        logger.error(f"Error writing joined channel to DB: {e}")
        with app.app_context():
            db.session.rollback()
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
        logger.error(f"Keyword file parse error: {e}")
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
        msg['Subject'] = f"Telegram Alert: {alert_data['chat']}"
        
        html = f"""
        <html>
        <body>
            <h2>Telegram Alert</h2>
            <p><strong>Date:</strong> {alert_data['timestamp']}</p>
            <p><strong>Group:</strong> {escape(alert_data['chat'])}</p>
            <p><strong>Sender:</strong> {escape(alert_data['sender'])}</p>
            <p><strong>Categories:</strong> {', '.join(alert_data['categories'])}</p>
            <hr>
            <p><strong>Message:</strong></p>
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
        logger.error("API_ID and API_HASH are not defined. Check .env file.")
        return False
    
    try:
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            if not PHONE:
                logger.error("Phone number is not defined. Check .env file.")
                return False
            
            await client.send_code_request(PHONE)
            code = input("Enter the code sent by Telegram: ")
            
            try:
                await client.sign_in(PHONE, code)
            except SessionPasswordNeededError:
                password = input("Enter your two-factor authentication password: ")
                await client.sign_in(password=password)
        
        connected = True
        logger.info("Telegram client connected successfully")
        return True
    
    except Exception as e:
        logger.error(f"Telegram client setup error: {e}")
        return False

async def join_channels(channel_urls):
    global client
    
    if not client or not connected:
        logger.error("Telegram client is not connected")
        return False
    
    successful_joins = 0
    failed_joins = 0
    already_joined = 0
    
    joined_channels = read_joined_channels()
    
    for url in channel_urls:
        if url in joined_channels:
            logger.info(f"Already joined group: {url}")
            already_joined += 1
            continue
        
        try:
            channel_entity = await client.get_entity(url)
            await client(JoinChannelRequest(channel_entity))
            logger.info(f"Joined group: {url}")
            successful_joins += 1
            
            if not write_joined_channel(url):
                logger.warning(f"Failed to record joined channel in database: {url}")
            
            await asyncio.sleep(2)
        
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError: waiting {wait_time} seconds. Group: {url}")
            await asyncio.sleep(wait_time)
            try:
                channel_entity = await client.get_entity(url)
                await client(JoinChannelRequest(channel_entity))
                logger.info(f"Joined group (after retry): {url}")
                successful_joins += 1
                
                if not write_joined_channel(url):
                    logger.warning(f"Failed to record joined channel in database: {url}")
            except Exception as e2:
                logger.error(f"Error joining group (after retry): {url} - {e2}")
                failed_joins += 1
        
        except Exception as e:
            logger.error(f"Error joining group: {url} - {e}")
            failed_joins += 1
    
    logger.info(f"Group joining completed. Successful: {successful_joins}, Failed: {failed_joins}, Already Joined: {already_joined}")
    return True

async def start_monitoring(keywords_dict):
    global client, connected, monitoring_active
    
    if not client or not connected:
        logger.error("Telegram client is not connected")
        return False
    
    monitoring_active = True
    
    @client.on(events.NewMessage)
    async def handle_new_message(event):
        if not monitoring_active:
            return
        
        try:
            message_text = event.message.message
            
            if not message_text:
                return
                
            try:
                sender = await event.get_sender()
                sender_name = getattr(sender, 'title', None) or getattr(sender, 'username', None) or getattr(sender, 'first_name', '')
                
                if hasattr(sender, 'last_name') and sender.last_name:
                    sender_name += f" {sender.last_name}"
                
                chat = await event.get_chat()
                chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or sender_name
            except:
                sender_name = "Unknown"
                chat_title = "Unknown Group"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alert_id = generate_alert_id()
            
            matched_categories = check_message_for_keywords(message_text, keywords_dict)
            is_filtered = len(matched_categories) > 0
            
            alert_data = {
                'id': alert_id,
                'timestamp': timestamp,
                'sender': sender_name,
                'chat': chat_title,
                'message': message_text,
                'categories': matched_categories,
                'filtered': is_filtered,
                'read': False,
                'important': False,
                'notes': ''
            }
            
            if is_filtered:
                high_priority_categories = os.getenv('HIGH_PRIORITY_CATEGORIES', '').split(',')
                should_send_email = False

                if EMAIL_ENABLED and high_priority_categories:
                    for category in matched_categories:
                        if category in high_priority_categories:
                            should_send_email = True
                            break

                if should_send_email:
                    send_email_notification(alert_data)
            
            with app.app_context():
                new_alert = Alert(
                    id=alert_id,
                    timestamp=timestamp,
                    sender=sender_name,
                    chat=chat_title,
                    message=message_text,
                    categories=matched_categories,
                    filtered=is_filtered,
                    read=False,
                    important=False,
                    notes=''
                )
                
                db.session.add(new_alert)
                
                if is_filtered:
                    filtered_count = db.session.query(func.count(Alert.id)).filter(Alert.filtered == True).scalar()
                    if filtered_count > max_alerts:
                        oldest_filtered = Alert.query.filter(Alert.filtered == True).order_by(Alert.timestamp).limit(filtered_count - max_alerts).all()
                        for old_alert in oldest_filtered:
                            db.session.delete(old_alert)
                else:
                    unfiltered_count = db.session.query(func.count(Alert.id)).filter(Alert.filtered == False).scalar()
                    if unfiltered_count > max_alerts * 2:  
                        oldest_unfiltered = Alert.query.filter(Alert.filtered == False).order_by(Alert.timestamp).limit(unfiltered_count - (max_alerts * 2)).all()
                        for old_alert in oldest_unfiltered:
                            db.session.delete(old_alert)
                
                db.session.commit()
            
            socketio.emit('new_alert', alert_data)
            
            if is_filtered:
                logger.info(f"Filtered Alert: {chat_title} - {matched_categories}")
            else:
                logger.debug(f"Unfiltered Message: {chat_title}")
        
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    logger.info("Message monitoring started")
    return True

async def stop_monitoring():
    global monitoring_active
    monitoring_active = False
    logger.info("Message monitoring stopped")
    return True

def start_client_and_monitor():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    with app.app_context():
        channel_urls = read_file('channels.txt')
        keywords_dict = parse_keywords_file('keyword.txt')
        
        loop.run_until_complete(setup_client())
        
        if connected:
            loop.run_until_complete(join_channels(channel_urls))
            loop.run_until_complete(start_monitoring(keywords_dict))
            loop.run_forever()

def translate_text(text, target_language):
    """
    Translate text to the target language using LibreTranslate API (no API key required)
    
    Args:
        text (str): Text to translate
        target_language (str): Target language code (e.g., 'en', 'tr', 'de')
    
    Returns:
        str: Translated text
    """
    try:
        url = "https://translate.argosopentech.com/translate"
        
        language_map = {
            "en": "en",
            "tr": "tr",
            "de": "de",
            "fr": "fr",
            "es": "es",
            "ru": "ru",
            "ar": "ar",
            "zh": "zh",
            "it": "it",
            "ja": "ja",
            "ko": "ko",
            "pt": "pt",
            "nl": "nl",
            "pl": "pl",
            "sv": "sv",
            "uk": "uk"
        }
        
        target = language_map.get(target_language, target_language)
        
        data = {
            "q": text,
            "source": "auto",
            "target": target,
            "format": "text"
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            return result["translatedText"]
        else:
            return _translate_fallback(text, target_language)
    
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return _translate_fallback(text, target_language)

def _translate_fallback(text, target_language):
    """
    Fallback translation method using web scraping (use only as backup)
    """
    try:
        url = f"https://translate.google.com/m?sl=auto&tl={target_language}&q={requests.utils.quote(text)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Mobile Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            result = soup.find("div", {"class": "result-container"})
            if result:
                return result.text
            else:
                raise Exception("Translation result not found")
        else:
            raise Exception(f"HTTP error {response.status_code}")
    
    except Exception as e:
        logger.error(f"Translation fallback error: {e}")
        raise Exception(f"Translation failed: {str(e)}")
    
@app.route('/')
@login_required
def index():
    return render_template('index.html', 
                          connected=connected, 
                          monitoring_active=monitoring_active)

@app.route('/alerts')
@login_required
def get_alerts():
    filter_type = request.args.get('filter', 'filtered')
    
    if filter_type == 'all':
        alerts = Alert.query.order_by(desc(Alert.timestamp)).all()
    elif filter_type == 'unfiltered':
        alerts = Alert.query.filter(Alert.filtered == False).order_by(desc(Alert.timestamp)).all()
    else: 
        alerts = Alert.query.filter(Alert.filtered == True).order_by(desc(Alert.timestamp)).all()
    
    return jsonify([{
        'id': alert.id,
        'timestamp': alert.timestamp,
        'sender': alert.sender,
        'chat': alert.chat,
        'message': alert.message,
        'categories': alert.categories,
        'filtered': alert.filtered,
        'read': alert.read,
        'important': alert.important,
        'notes': alert.notes
    } for alert in alerts])

@app.route('/alert_counts')
@login_required
def get_alert_counts():
    with app.app_context():
        filtered_count = db.session.query(func.count(Alert.id)).filter(Alert.filtered == True).scalar()
        unfiltered_count = db.session.query(func.count(Alert.id)).filter(Alert.filtered == False).scalar()
    
    return jsonify({
        'filtered': filtered_count,
        'unfiltered': unfiltered_count,
        'total': filtered_count + unfiltered_count
    })

@app.route('/start', methods=['POST'])
@login_required
def start():
    global client_thread, monitoring_active
    
    if client_thread is None or not client_thread.is_alive():
        client_thread = Thread(target=start_client_and_monitor)
        client_thread.daemon = True
        client_thread.start()
        flash('Telegram monitoring started', 'success')
    elif not monitoring_active:
        loop = asyncio.new_event_loop()
        keywords_dict = parse_keywords_file('keyword.txt')
        loop.run_until_complete(start_monitoring(keywords_dict))
        flash('Telegram monitoring restarted', 'success')
    else:
        flash('Telegram monitoring is already running', 'info')
    
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
@login_required
def stop():
    global monitoring_active
    
    if monitoring_active:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(stop_monitoring())
        flash('Telegram monitoring stopped', 'warning')
    else:
        flash('Telegram monitoring is already stopped', 'info')
    
    return redirect(url_for('index'))

@app.route('/clear', methods=['POST'])
@login_required
def clear_alerts():
    try:
        clear_type = request.form.get('clear_type', 'all')
        
        if clear_type == 'filtered':
            Alert.query.filter(Alert.filtered == True).delete()
            flash('Filtered alerts cleared', 'info')
        elif clear_type == 'unfiltered':
            Alert.query.filter(Alert.filtered == False).delete()
            flash('Unfiltered alerts cleared', 'info')
        else:  # clear all
            Alert.query.delete()
            flash('All alerts cleared', 'info')
            
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error clearing alerts: {e}")
        flash('Error clearing alerts', 'danger')
        
    return redirect(url_for('index'))

@app.route('/keywords', methods=['GET', 'POST'])
@login_required
def manage_keywords():
    if request.method == 'POST':
        if 'content' in request.form:
            success = write_keywords_file(request.form['content'])
            if success:
                flash('Keywords updated successfully', 'success')
            else:
                flash('Error updating keywords', 'danger')
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
                flash('Groups updated successfully', 'success')
            else:
                flash('Error updating groups', 'danger')
        return redirect(url_for('manage_channels'))
    
    channels = read_file('channels.txt')
    channels_content = read_channels_file()
    return render_template('channels.html', channels=channels, channels_content=channels_content,
                          connected=connected, monitoring_active=monitoring_active,
                          active_page='channels')

@app.route('/api/alerts/add', methods=['POST'])
@login_required
def add_alert():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid data format'}), 400
    
    if 'id' not in data:
        data['id'] = generate_alert_id()
    if 'timestamp' not in data:
        data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if 'read' not in data:
        data['read'] = False
    if 'important' not in data:
        data['important'] = False
    if 'notes' not in data:
        data['notes'] = ''
    if 'filtered' not in data:
        data['filtered'] = bool(data.get('categories', []))
    
    required_fields = ['sender', 'chat', 'message', 'categories']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400
    
    try:
        new_alert = Alert(
            id=data['id'],
            timestamp=data['timestamp'],
            sender=data['sender'],
            chat=data['chat'],
            message=data['message'],
            categories=data['categories'],
            filtered=data['filtered'],
            read=data['read'],
            important=data['important'],
            notes=data['notes']
        )
        
        db.session.add(new_alert)
        
        if data['filtered']:
            filtered_count = db.session.query(func.count(Alert.id)).filter(Alert.filtered == True).scalar()
            if filtered_count > max_alerts:
                oldest_filtered = Alert.query.filter(Alert.filtered == True).order_by(Alert.timestamp).limit(filtered_count - max_alerts).all()
                for old_alert in oldest_filtered:
                    db.session.delete(old_alert)
        else:
            unfiltered_count = db.session.query(func.count(Alert.id)).filter(Alert.filtered == False).scalar()
            if unfiltered_count > max_alerts * 2:
                oldest_unfiltered = Alert.query.filter(Alert.filtered == False).order_by(Alert.timestamp).limit(unfiltered_count - (max_alerts * 2)).all()
                for old_alert in oldest_unfiltered:
                    db.session.delete(old_alert)
                
        db.session.commit()
        
        socketio.emit('new_alert', data)
        
        return jsonify({'success': True, 'id': data['id']})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding alert: {e}")
        return jsonify({'error': str(e)}), 500

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
    
    flash('Configuration reloaded', 'success')
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
            
            flash('Email notification configuration updated', 'success')
        else:
            flash('Email notifications disabled', 'info')
        
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
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            error = 'Invalid username or password'
    
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/alerts/<alert_id>/read', methods=['POST'])
@login_required
def mark_alert_read(alert_id):
    try:
        alert = Alert.query.get(alert_id)
        if alert:
            alert.read = request.json.get('read', True)
            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking alert read: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/<alert_id>/important', methods=['POST'])
@login_required
def mark_alert_important(alert_id):
    try:
        alert = Alert.query.get(alert_id)
        if alert:
            alert.important = request.json.get('important', True)
            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking alert important: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/<alert_id>/notes', methods=['POST'])
@login_required
def update_alert_notes(alert_id):
    try:
        alert = Alert.query.get(alert_id)
        if alert:
            alert.notes = request.json.get('notes', '')
            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating alert notes: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/<alert_id>/delete', methods=['POST'])
@login_required
def delete_alert(alert_id):
    try:
        alert = Alert.query.get(alert_id)
        if alert:
            db.session.delete(alert)
            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting alert: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/translate', methods=['POST'])
@login_required
def api_translate():
    try:
        data = request.get_json()
        if not data or 'text' not in data or 'targetLang' not in data:
            return jsonify({
                'error': 'Invalid request. Required fields: text, targetLang'
            }), 400
        
        text = data['text']
        target_lang = data['targetLang']
        
        if not text or not target_lang:
            return jsonify({'error': 'Text and target language are required'}), 400
        
        if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', target_lang):
            return jsonify({'error': 'Invalid language code format'}), 400
        
        base_lang = target_lang.split('-')[0]
        
        translated_text = translate_text(text, base_lang)
        
        return jsonify({
            'success': True,
            'originalText': text,
            'translatedText': translated_text,
            'targetLanguage': target_lang
        })
    
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return jsonify({
            'error': str(e)
        }), 500
    
if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)