import os
import time
import base64
import json
import re
import urllib.parse
import threading
from typing import List, Optional, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from core.base_bridge import AbstractBridge
from .models import Message, MessageType, MessageRole, ChatChannel

class WhatsAppWeb:
    def __init__(self, headless: bool = False, browser: str = "chrome"):
        self.headless = headless
        self.browser_type = browser
        self.driver = None
        self.wait = None
        self.lock = threading.RLock()
        # Ensure session directory exists
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.user_data_dir = os.path.join(base_path, "whatsapp_session")
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)

    def login(self, timeout: int = 90) -> bool:
        """Initializes the browser and handles login."""
        with self.lock:
            try:
                if self.browser_type == "chrome":
                    options = webdriver.ChromeOptions()
                    options.add_argument(f"--user-data-dir={self.user_data_dir}")
                    if self.headless:
                        options.add_argument("--headless=new")
                    options.add_argument("--no-sandbox")
                    options.add_argument("--disable-dev-shm-usage")
                    options.add_argument("--window-size=1280,800")
                    options.add_argument("--log-level=3")
                    
                    service = ChromeService(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=options)
                else:
                    options = webdriver.EdgeOptions()
                    options.add_argument(f"user-data-dir={self.user_data_dir}")
                    if self.headless:
                        options.add_argument("--headless=new")
                    
                    service = EdgeService(EdgeChromiumDriverManager().install())
                    self.driver = webdriver.Edge(service=service, options=options)

                self.wait = WebDriverWait(self.driver, 20)
                self.driver.get("https://web.whatsapp.com")

                print(">>> Waiting for QR code or chat list...")
                
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        if self.driver.find_elements(By.XPATH, "//div[@aria-label='Chat list']") or \
                           self.driver.find_elements(By.ID, "side"):
                            print(">>> Login successful.")
                            time.sleep(2)
                            return True
                        time.sleep(1)
                    except Exception:
                        time.sleep(1)

                print(">>> Login timed out.")
                return False
            except Exception as e:
                print(f">>> Error during login: {e}")
                if self.driver:
                    self.driver.quit()
                return False

    def is_connected(self) -> bool:
        """Checks if the session is still active."""
        with self.lock:
            try:
                return bool(self.driver.find_elements(By.ID, "side"))
            except:
                return False

    def get_unread_chats(self) -> List[ChatChannel]:
        """Returns a list of chats with unread messages."""
        unread_chats = []
        with self.lock:
            try:
                badges = self.driver.find_elements(By.XPATH, "//span[contains(@aria-label, 'unread message')]")
                for badge in badges:
                    try:
                        row = badge.find_element(By.XPATH, "./ancestor::div[@role='row']")
                        name_el = row.find_element(By.CSS_SELECTOR, "span[title]")
                        name = name_el.get_attribute("title")
                        
                        label = badge.get_attribute("aria-label")
                        count = 1
                        if label:
                            parts = label.split(" ")
                            if parts[0].isdigit():
                                count = int(parts[0])
                        
                        unread_chats.append(ChatChannel(name=name, unread_count=count))
                    except:
                        continue
            except Exception as e:
                print(f">>> Error getting unread chats: {e}")
        return unread_chats

    def open_chat(self, chat_name: str) -> bool:
        """Opens a chat by searching. Avoids driver.get() to prevent app reloads."""
        with self.lock:
            try:
                # 1. Check if current chat is already the target
                active_name = self.get_active_chat_name()
                if self._names_match(active_name, chat_name):
                    return True

                print(f">>> Switching to chat: {chat_name}")
                
                # 2. Try to search and open
                for attempt in range(2):
                    try:
                        # Find search box and clear it
                        search_box = self.driver.find_element(By.XPATH, "//div[@contenteditable='true'][@data-tab='3']")
                        search_box.click()
                        search_box.send_keys(Keys.CONTROL + "a")
                        search_box.send_keys(Keys.BACKSPACE)
                        time.sleep(0.5)
                        
                        # Type target name
                        search_box.send_keys(chat_name)
                        time.sleep(2.0 + (attempt * 1.0)) # Wait for results to stabilize
                        
                        # Look for the row in search results
                        # We look for rows that are NOT the "search box" itself or "Chats" header
                        rows = self.driver.find_elements(By.XPATH, "//div[@role='row']")
                        found = False
                        
                        # Optimization: filter out obviously wrong rows if possible
                        for row in rows:
                            try:
                                # Look for the title span inside this row
                                # WhatsApp Web search results often use different structures
                                # Try a wider range of title selectors
                                name_el = None
                                for s in ["span[title]", "div[title]", "[role='gridcell'] span"]:
                                    try:
                                        name_el = row.find_element(By.CSS_SELECTOR, s)
                                        if name_el: break
                                    except: continue
                                
                                if not name_el: continue
                                
                                found_name = name_el.get_attribute("title") or name_el.text
                                if self._names_match(found_name, chat_name):
                                    print(f">>> Found matching row for '{chat_name}' (Display: '{found_name}'). Clicking...")
                                    
                                    # Sometimes row.click() hits the icon, let's try to click the text directly
                                    try:
                                        name_el.click()
                                    except:
                                        row.click()
                                        
                                    found = True
                                    break
                            except:
                                continue
                        
                        if not found:
                            print(f">>> Row matching '{chat_name}' not found explicitly. Trying Enter key fallback.")
                            search_box.send_keys(Keys.ENTER)
                        
                        time.sleep(2.0) 

                        # Verify switch
                        new_active = self.get_active_chat_name()
                        if self._names_match(new_active, chat_name):
                            print(f">>> Successfully switched to {new_active}")
                            return True
                        
                        print(f">>> Attempt {attempt+1}: Failed to switch. Currently on: '{new_active}'")
                    except Exception as e:
                        print(f">>> Attempt {attempt+1}: Search error: {e}")
                        time.sleep(1)

                return False
            except Exception as e:
                print(f">>> Critical error in open_chat: {e}")
                return False

    def _names_match(self, n1: Optional[str], n2: Optional[str]) -> bool:
        if not n1 or not n2: return False
        
        # Normalize: remove spaces, pluses, underscores, hyphens, and dots
        def norm(s):
            return re.sub(r'[\s\+\-_\.]', '', s).lower()
            
        norm1 = norm(n1)
        norm2 = norm(n2)
        
        # Self-contact detection
        me_names = ["du", "you", "me", "ich", "yo", "moi", "self"]
        if norm1 in me_names or norm2 in me_names:
            is_n1_me = norm1 in me_names
            is_n2_me = norm2 in me_names
            if is_n1_me and is_n2_me: return True
            
            other = norm2 if is_n1_me else norm1
            # If searched for phone number and got "Du", it's a match
            if other.isdigit() and len(other) > 7:
                return True
            return False

        # Strict equality after normalization
        # Note: avoid 'in' check which causes "Agent_work" to match "Agent" or numbers
        return norm1 == norm2

    def get_history(self, chat_name: str, limit: int = 10) -> List[Message]:
        """Opens a chat and retrieves recent messages."""
        with self.lock:
            print(f">>> Getting history for {chat_name}...")
            
            messages = []
            if not self.open_chat(chat_name):
                return []
            
            # Double-check we are in the correct chat to prevent cross-talk
            active = self.get_active_chat_name()
            if not self._names_match(active, chat_name):
                print(f">>> Safety check failed: Requested '{chat_name}' but active is '{active}'. Skipping.")
                return []
            else:
                # Debug log to verify what we matched
                if active != chat_name:
                    print(f">>> Safety check passed: matched '{chat_name}' with active UI title '{active}'")

            try:
                msg_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-id]")
                valid_elements = []
                for el in msg_elements:
                    data_id = el.get_attribute("data-id")
                    if data_id and ("true_" in data_id or "false_" in data_id):
                        valid_elements.append(el)
                
                recent_elements = valid_elements[-limit:]
                
                for el in recent_elements:
                    try:
                        data_id = el.get_attribute("data-id")
                        role = MessageRole.OUTGOING if data_id.startswith("true_") else MessageRole.INCOMING
                        
                        text = ""
                        try:
                            text_el = el.find_element(By.CSS_SELECTOR, "span.selectable-text")
                            text = text_el.text
                        except:
                            text = el.text
                        
                        text = text.strip()
                        text = re.sub(r'\n\d{1,2}:\d{2}(?:\s?[APMapm]{2})?$', '', text)
                        
                        if role == MessageRole.OUTGOING:
                            sender = "Bot" if text.startswith("Bot:") else "Me"
                        else:
                            sender = chat_name
                            
                        msg_type = MessageType.TEXT
                        if el.find_elements(By.TAG_NAME, "img"):
                            msg_type = MessageType.IMAGE
                        elif el.find_elements(By.CSS_SELECTOR, "span[data-testid='audio-play']"):
                            msg_type = MessageType.AUDIO
                        elif el.find_elements(By.CSS_SELECTOR, "span[data-testid='video-play']"):
                            msg_type = MessageType.VIDEO
                        
                        # Extract chat_id (JID) from data-id: [true/false]_[JID]_[ID]
                        chat_id = None
                        if data_id and "_" in data_id:
                            id_parts = data_id.split("_")
                            if len(id_parts) > 1:
                                chat_id = id_parts[1]

                        messages.append(Message(
                            sender=sender,
                            chat_id=chat_id,
                            content=text,
                            timestamp=data_id,
                            role=role,
                            type=msg_type
                        ))
                    except:
                        continue
            except Exception as e:
                print(f">>> Error getting history for {chat_name}: {e}")
                
            return messages

    def send_message(self, chat_name: str, message: str):
        """Sends a text message to the specified chat (supports emojis via JS injection)."""
        with self.lock:
            if not self.open_chat(chat_name):
                return

            try:
                input_box = self.driver.find_element(By.XPATH, "//div[@contenteditable='true'][@data-tab='10']")
                input_box.click()
                
                # Use JS to set the message. This bypasses the BMP error (ChromeDriver emoji limitation).
                # We convert newlines to <br> because it's a contenteditable div.
                safe_message = message.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                js_script = """
                    var element = arguments[0];
                    var text = arguments[1];
                    element.focus();
                    document.execCommand('insertText', false, text);
                """
                # Note: execCommand('insertText') is the most compatible way to trigger 
                # WhatsApp's internal state listeners so the 'Send' button appears.
                self.driver.execute_script(js_script, input_box, message)
                
                time.sleep(0.5)
                input_box.send_keys(Keys.ENTER)
            except Exception as e:
                print(f">>> Error sending message to {chat_name}: {e}")

    def deselect_active_chat(self):
        """Presses ESC to deselect chat."""
        with self.lock:
            try:
                webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            except:
                pass

    def get_active_chat_name(self) -> Optional[str]:
        """Returns the name of the currently open chat."""
        with self.lock:
            try:
                # Try multiple precise selectors for the header title
                selectors = [
                    "header [data-testid='conversation-info-header-chat-title']",
                    "header [aria-label='Chat details'] span[title]",
                    "header span[title]",
                    "#main header span[title]"
                ]
                for selector in selectors:
                    try:
                        # Use find_element instead of find_elements to get the topmost one
                        el = self.driver.find_element(By.CSS_SELECTOR, selector)
                        # Prefer 'title' attribute if it exists, as it's more definitive
                        name = el.get_attribute("title") or el.text
                        if name and name.strip():
                            # Skip if the name is just a timestamp or status
                            clean_name = name.strip()
                            if not re.match(r'^\d{1,2}:\d{2}$', clean_name):
                                return clean_name
                    except: continue
                return None
            except:
                return None

    def close(self):
        if self.driver:
            self.driver.quit()

    def download_media(self, chat_name: str, message_index: int = -1, media_type: MessageType = MessageType.IMAGE) -> List[str]:
        """Downloads media by converting elements to data URLs via JS."""
        with self.lock:
            if not self.open_chat(chat_name):
                return []

            try:
                # Find the message element again
                msg_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-id]")
                valid_elements = []
                for el in msg_elements:
                    data_id = el.get_attribute("data-id")
                    if data_id and ("true_" in data_id or "false_" in data_id):
                        valid_elements.append(el)
                
                if not valid_elements:
                    return []
                
                target_el = valid_elements[message_index]
                
                # Script to extract media as data URL
                script = """
                const callback = arguments[arguments.length - 1];
                const element = arguments[0];
                const type = arguments[1];

                async function getMediaData() {
                    try {
                        if (type === 'image') {
                            const img = element.querySelector('img');
                            if (!img) return null;
                            const canvas = document.createElement('canvas');
                            canvas.width = img.naturalWidth;
                            canvas.height = img.naturalHeight;
                            const ctx = canvas.getContext('2d');
                            ctx.drawImage(img, 0, 0);
                            return canvas.toDataURL('image/jpeg');
                        } else if (type === 'audio' || type === 'video') {
                            const media = element.querySelector(type);
                            if (!media) return null;
                            const response = await fetch(media.src);
                            const blob = await response.blob();
                            return new Promise((resolve) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.readAsDataURL(blob);
                            });
                        }
                    } catch (e) {
                        return 'ERROR: ' + e.message;
                    }
                    return null;
                }
                getMediaData().then(result => callback(result));
                """
                
                data_url = self.driver.execute_async_script(script, target_el, media_type.value)
                
                if data_url and data_url.startswith("ERROR:"):
                    print(f">>> Media script error: {data_url}")
                    return []
                    
                return [data_url] if data_url else []
                
            except Exception as e:
                print(f">>> Error downloading media: {e}")
                return []

    def get_all_chats(self) -> List[ChatChannel]:
        """Returns a list of all visible chats in the sidebar."""
        chats = []
        with self.lock:
            try:
                rows = self.driver.find_elements(By.XPATH, "//div[@role='row']")
                for row in rows:
                    try:
                        name_el = row.find_element(By.CSS_SELECTOR, "span[title]")
                        name = name_el.get_attribute("title")
                        is_group = bool(row.find_elements(By.XPATH, ".//span[@data-testid='default-group']"))
                        
                        if name:
                            chats.append(ChatChannel(name=name, is_group=is_group))
                    except:
                        pass
            except Exception as e:
                print(f"Error getting all chats: {e}")
        return chats
