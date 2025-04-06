# Telegram Monitoring Application

This application monitors Telegram channels and groups for specific keywords and provides a web interface to manage alerts.

## Features

- Monitor multiple Telegram channels/groups
- Filter messages based on keywords
- Web interface for managing alerts, channels, and keywords
- Email notifications for important alerts
- Authentication system

## Setup with Docker (Recommended)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/burakozcn01/telegram-izleme.git
   cd telegram-izleme
   ```

2. Create a `.env` file with your Telegram API credentials:
   ```
   API_ID=your_api_id
   API_HASH=your_api_hash
   PHONE_NUMBER=your_phone_number
   SECRET_KEY=your_secret_key
   ADMIN_PASSWORD=your_admin_password
   ```

3. Build and start the Docker container:
   ```
   docker-compose up -d
   ```

4. Access the web interface at http://localhost:5000
   - Login with the default username: `admin` and the password you set in `.env` (ADMIN_PASSWORD)

### Stopping the Application

```
docker-compose down
```

### Viewing Logs

```
docker-compose logs -f
```

## Configuration

### Channels

Edit the `channels.txt` file to add or remove Telegram channels/groups to monitor:
```
https://t.me/channel1
https://t.me/channel2
```

### Keywords

Edit the `keyword.txt` file to add or remove keywords to filter messages:
```
## CATEGORY1
keyword1
keyword2

## CATEGORY2
keyword3
keyword4
```

## Manual Setup (Without Docker)

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Access the web interface at http://localhost:5000