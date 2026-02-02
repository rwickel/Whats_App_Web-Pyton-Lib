# WhatsApp Web Bot

A robust, headless WhatsApp automation bot built with Python and Selenium. Featuring structured data models via Pydantic and terminal-based QR code login.

## Features

- **Headless Operation**: Runs in the background (supports Chrome and Edge).
- **Edge Priority**: Intelligent driver selection (Edge first, Chrome fallback).
- **Terminal QR Login**: Prints the WhatsApp login QR code directly to your terminal.
- **Structured Data**: Uses **Pydantic** models for `Message` and `ChatChannel`.
- **Deep Media Sniffing**: Captures audio, video, and images directly as **Base64** blobs (no disk write required).
- **LLM Ready**: Formats media data for direct injection into vision-capable AI models.
- **Shadow DOM Support**: Pierces through WhatsApp's complex Web Components to find hidden media URLs.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/rwickel/WhatsAppWebBot.git
   cd WhatsAppWebBot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Configure `LISTEN_CHANNELS` in `main.py` to target specific names.

## Usage

Run the example:
```bash
python main.py
```

- **Browser Selection**: Toggle `BROWSER_TYPE` between `"chrome"`, `"edge"`, or `"auto"` (default Edge) in `main.py`.
- **Browser Visibility**: Toggle the `SHOW_BROWSER` variable at the top of `main.py`.
- **Login**: When the QR code appears in your terminal, scan it. Sessions are saved in the `whatsapp_session/` folder, which keeps you logged in across restarts.
- **Media Capture**: The bot will capture media blobs and add them to the `Message` objects under the `media_base64` field.
- The bot will stay active, monitoring for unread messages and printing detected activity.

## Testing

The project includes a suite of unit tests for data models and core logic.

To run the tests:
```bash
pytest
```

## Data Models

The bot uses strict types for reliable automation:

### `Message`
- `role`: "incoming" | "outgoing"
- `content`: Message text or description
- `type`: "text" | "audio" | "video" | "image" | "contact" | "other"
- `media_base64`: List of raw Base64 strings for captured media.
- `timestamp`: Message metadata

### `ChatChannel`
- `name`: Display name
- `unread_count`: Number of waiting messages
- `is_group`: Group chat detection

## Disclaimer
This project is for educational purposes. Use WhatsApp automation according to their terms of service.
