import time
import sys
import qrcode
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from pydantic import BaseModel
from typing import List, Optional, Literal

class Message(BaseModel):
    role: Literal["incoming", "outgoing"]
    content: str
    type: Literal["text", "audio", "image", "other"] = "text"
    timestamp: Optional[str] = None

class ChatChannel(BaseModel):
    name: str
    unread_count: int = 0
    is_group: bool = False

class WhatsAppWeb:
    def __init__(self):
        """Initializes the Selenium WebDriver using Microsoft Edge."""
        edge_options = Options()
        edge_options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        
        # Path to store session data
        session_path = os.path.join(os.getcwd(), "whatsapp_session")
        edge_options.add_argument(f"--user-data-dir={session_path}")
        edge_options.add_argument("--start-maximized")
        edge_options.add_experimental_option("detach", True)
        
        try:
            print(">>> Attempting to initialize Edge driver...", flush=True)
            service = Service(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(service=service, options=edge_options)
        except Exception as e:
            print(f">>> Automatic driver download failed: {e}", flush=True)
            print(">>> Attempting to start with system-installed msedgedriver...", flush=True)
            try:
                self.driver = webdriver.Edge(options=edge_options)
            except Exception as fallback_e:
                print(f">>> CRITICAL: Could not start Edge. {fallback_e}", flush=True)
                sys.exit(1)

    def login(self):
        """Goes to WhatsApp Web and waits for login/QR scan."""
        self.driver.get("https://web.whatsapp.com/")
        print(">>> Waiting for WhatsApp Web to load...", flush=True)
        
        last_ref = None
        timeout = 600
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if self.driver.find_elements(By.XPATH, "//div[@id='pane-side']"):
                print(">>> Logged in successfully!", flush=True)
                return True

            qr_containers = self.driver.find_elements(By.CSS_SELECTOR, "div._akau")
            if qr_containers:
                try:
                    qr_data = qr_containers[0].get_attribute("data-ref")
                    if qr_data and qr_data != last_ref:
                        last_ref = qr_data
                        print("\n" + "="*50)
                        print(">>> SCAN QR CODE:")
                        qr = qrcode.QRCode()
                        qr.add_data(qr_data)
                        qr.print_ascii(invert=True)
                        print("="*50 + "\n")
                except:
                    pass
            time.sleep(2)
        return False

    def list_channels(self) -> List[ChatChannel]:
        """Scans the 'Chatliste' and returns visible chat names. Waits for stability."""
        print(">>> identifying channels...", flush=True)
        try:
            # 1. Wait for the 'Chatliste' container
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Chatliste']"))
            )
            
            # 2. Robustly wait for at least one chat row to appear (syncing state)
            start_wait = time.time()
            rows = []
            while len(rows) == 0 and (time.time() - start_wait) < 15:
                rows = self.driver.find_elements(By.XPATH, "//div[@aria-label='Chatliste']//div[@role='row']")
                if not rows: time.sleep(1)

            channels = []
            for row in rows:
                try:
                    name_element = row.find_element(By.XPATH, ".//span[@title]")
                    title = name_element.get_attribute("title")
                    
                    # Handle (du) marker if present
                    try:
                        if row.find_elements(By.XPATH, ".//span[contains(text(), '(du)')]"):
                            title = f"{title} (du)"
                    except:
                        pass
                    
                    # Basic group detection (usually have different icon or metadata)
                    is_group = False
                    try:
                        # Groups often have a 'default-group' icon or multiple participants
                        if row.find_elements(By.XPATH, ".//span[@data-icon='default-group-refreshed']"):
                            is_group = True
                    except:
                        pass

                    if title and not any(c.name == title for c in channels):
                        channels.append(ChatChannel(name=title, is_group=is_group))
                except:
                    continue
            
            return channels
            
        except Exception as e:
            print(f">>> Error identifying channels: {e}")
            return []

    def get_history(self, chat_name: str, limit: int = 10) -> List[Message]:
        """
        Fetches history for a Specific chat and formats it as LLM-style Message objects.
        """
        print(f">>> Fetching history for: '{chat_name}'", flush=True)
        try:
            # Locate and click chat
            xpath = f"//div[@aria-label='Chatliste']//span[@title='{chat_name}']"
            chat_element = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            chat_element.click()
            time.sleep(2)

            messages_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.message-in, div.message-out")
            
            history = []
            for msg in messages_elements[-limit:]:
                try:
                    is_out = "message-out" in msg.get_attribute("class")
                    role = "outgoing" if is_out else "incoming"
                    
                    content = ""
                    msg_type = "text"
                    timestamp = None

                    # 1. Try to find text content
                    try:
                        text_el = msg.find_element(By.CSS_SELECTOR, ".copyable-text")
                        content = text_el.text
                        timestamp = text_el.get_attribute("data-pre-plain-text")
                        
                        # If we have "BOT:" prefix, it's definitely outgoing bot logic
                        if "BOT:" in content:
                            role = "outgoing"
                    except:
                        # 2. Check for Audio/Voice note
                        try:
                            # WhatsApp voice notes often have specific indicators
                            # They usually contain a button/span with a play icon
                            audio_indicators = [
                                ".//span[@data-icon='audio-play']",
                                ".//span[@data-icon='ptt-play']",
                                ".//div[contains(@aria-label, 'Sprachnachricht')]",
                                ".//div[contains(@aria-label, 'Voice note')]"
                            ]
                            is_audio = False
                            for selector in audio_indicators:
                                if msg.find_elements(By.XPATH, selector):
                                    is_audio = True
                                    break
                            
                            if is_audio:
                                msg_type = "audio"
                                # Try to find the duration string (e.g. "0:12")
                                try:
                                    # Duration is often in a specific class inside the voice note container
                                    duration_el = msg.find_element(By.XPATH, ".//div[contains(@class, 'x12v9rci')]")
                                    content = f"[Audio Message - {duration_el.text}]"
                                except:
                                    content = "[Audio Message]"
                        except:
                            pass

                    if not content:
                        content = "[Unsupported Message Type]"
                        msg_type = "other"
                    
                    history.append(Message(role=role, content=content, type=msg_type, timestamp=timestamp))
                except Exception as e:
                    print(f">>> Skipping a message due to error: {e}")
                    continue
            return history
        except Exception as e:
            print(f">>> Error getting history: {e}")
            return []

    def send_message(self, chat_name, text):
        """Opens a chat and sends a message."""
        try:
            xpath = f"//div[@aria-label='Chatliste']//span[@title='{chat_name}']"
            chat_element = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            chat_element.click()
            
            input_box = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @data-tab='10']"))
            )
            input_box.send_keys(text)
            input_box.send_keys(Keys.ENTER)
            return True
        except Exception as e:
            print(f">>> Error sending message: {e}")
            return False

    def get_unread_chats(self) -> List[ChatChannel]:
        """Returns a list of ChatChannel objects that have unread messages."""
        xpath = (
            "//div[@aria-label='Chatliste']//span[contains(@aria-label, 'unread message') or "
            "contains(@aria-label, 'Unread message') or "
            "contains(@aria-label, 'Nachricht') or "
            "contains(@aria-label, 'Nachrichten')]"
        )
        badges = self.driver.find_elements(By.XPATH, xpath)
        unread_chats = []
        for badge in badges:
            try:
                ancestor = badge.find_element(By.XPATH, "./ancestor::div[@role='row']")
                name_el = ancestor.find_element(By.XPATH, ".//span[@title]")
                name = name_el.get_attribute("title")
                
                # Extract unread count text
                count_text = badge.text.strip()
                if not count_text:
                    try:
                        count_text = badge.find_element(By.TAG_NAME, "span").text.strip()
                    except:
                        count_text = "1"
                
                count = int(count_text) if count_text.isdigit() else 1
                
                unread_chats.append(ChatChannel(name=name, unread_count=count))
            except:
                continue
        return unread_chats

    def close(self):
        self.driver.quit()

# --- Example usage as requested ---
if __name__ == "__main__":
    whatsapp = WhatsAppWeb()
    if whatsapp.login():
        channels = whatsapp.list_channels()
        print(f">>> Found {len(channels)} channels.")
        # Pydantic models can be printed or converted to dict/json easily
        for c in channels[:5]: 
            print(f" - {c.model_dump()}")

        history = whatsapp.get_history("+49 176 45975276", limit=5)    
        print(f"History: {history}")

        history = whatsapp.get_history("Laura Penkert", limit=5)    
        print(f"History: {history}")
        
        # Example: Loop and check for unread
        try:
            while True:
                unread = whatsapp.get_unread_chats()
                for chat in unread:
                    print(f">>> Unread message in: {chat.name} ({chat.unread_count})")
                    history = whatsapp.get_history(chat.name, limit=5)
                    for msg in history:
                        print(f"    [{msg.role}] {msg.content}")
                
                time.sleep(5)
        except KeyboardInterrupt:
            print(">>> Stopping...")
            whatsapp.close()
