# WhatsApp Bot via WhatsApp Web

This is a simple Python script that automates a WhatsApp account to act as a chatbot.

## Prerequisites
- Python installed
- Microsoft Edge installed

## Setup
1. Open a terminal in this directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Bot
1. Run the script:
   ```bash
   python bot.py
   ```
2. An Edge window will open. Scan the QR code with your phone.
3. Once logged in, the script will start polling for unread messages.
4. When a new message is received from a user, the bot will automatically reply with:
   `BOT: <Original Message>`

## How it works
- **Selenium**: Uses Selenium to control a Chrome instance.
- **Session Management**: Saves the browser profile in the `whatsapp_session` folder, so you don't need to scan the QR code every time.
- **Polling**: Every 5 seconds, the script looks for chats with the "Unread" badge and responds to them.
