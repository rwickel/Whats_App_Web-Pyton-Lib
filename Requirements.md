# WhatsApp Bridge Requirements

The `whatsapp_bridge` manages the WebDriver lifecycle and translates platform-specific interactions into standardized `Message` objects.

---

## 1. Connection & Login
- **REQ-WAP-001**: The bridge **shall** support both Chrome and Edge browsers.
- **REQ-WAP-002**: The bridge **shall** persist session data in the `whatsapp_session/` directory to avoid re-scanning QR codes on every restart.
- **REQ-WAP-003**: The login timeout **shall** be configurable (default 90 seconds).

---

## 2. Chat Navigation & Switching
- **REQ-WAP-004**: When switching to a chat identified by a phone number (e.g., `ADMIN_CHAT`), the system **shall** use direct URL navigation (`web.whatsapp.com/send?phone=...`) for maximum reliability.
- **REQ-WAP-005**: For direct URL navigation to phone numbers, the system **shall** consider the switch successful immediately without further header verification.
- **REQ-WAP-006**: For name-based navigation (Groups), the system **shall** use the search box and verify the UI header before proceeding.

---

## 3. Message Delivery
- **REQ-WAP-007**: The bridge **shall** support sending multi-line text messages and emojis via JavaScript injection to bypass browser BMP limitations.
- **REQ-WAP-008**: The bridge **shall** retrieve history in batches (default 10 messages) to prevent UI lag.

---

## 4. Admin Handling
- **REQ-WAP-009**: The bridge **shall** correctly identify the "Me" chat in German localized environments by recognizing the header string "Sende dir selbst eine Nachricht".
- **REQ-WAP-010**: The bridge **shall** leverage the Core's robust normalization to resolve discrepancies between user-friendly UI titles and registered session identifiers.
