import time

import sys

import qrcode
import os
import json

from typing import List, Literal

from selenium import webdriver

from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.common.keys import Keys

from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager


from .models import Message, ChatChannel


class WhatsAppWeb:

    def __init__(self, headless: bool = True, session_path: str = None, browser: Literal["chrome", "edge", "auto"] = "auto"):
        """Initializes the Selenium WebDriver. 'browser' can be 'chrome', 'edge', or 'auto' (Edge priority)."""
        
        if not session_path:
            session_path = os.path.abspath(os.path.join(os.getcwd(), "whatsapp_session"))
        else:
            session_path = os.path.abspath(session_path)

        def configure_options(options, browser_type):
            # Create a browser-specific session subfolder
            browser_session = os.path.abspath(os.path.join(session_path, browser_type))
            if not os.path.exists(browser_session):
                os.makedirs(browser_session, exist_ok=True)

            if headless:
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
            
            # CRITICAL Robustness flags for Windows/CI environments
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-allow-origins=*")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-setuid-sandbox")
            options.add_argument("--remote-debugging-pipe") # Fixes DevToolsActivePort issues
            options.add_argument("--disable-gpu-sandbox")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            
            options.add_argument(f"--user-data-dir={browser_session}")
            options.add_argument("--start-maximized")
            options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
            return options

        # 1. Try Edge
        if browser in ["edge", "auto"]:
            try:
                print(">>> Attempting to initialize Edge driver...", flush=True)
                edge_options = configure_options(EdgeOptions(), "edge")            
                try:
                    service = EdgeService(EdgeChromiumDriverManager().install())
                    self.driver = webdriver.Edge(service=service, options=edge_options)
                except:
                    self.driver = webdriver.Edge(options=edge_options)
                print(">>> Edge started successfully.")
                return
            except Exception as e:
                print(f">>> Edge failed: {e}")
                if browser == "edge":
                    sys.exit(1)
                print(">>> Falling back to Chrome...")

        # 2. Try Chrome
        if browser in ["chrome", "auto"]:
            try:
                print(">>> Attempting to initialize Chrome driver...", flush=True)
                chrome_options = configure_options(ChromeOptions(), "chrome")
                try:
                    service = ChromeService(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except:
                    self.driver = webdriver.Chrome(options=chrome_options)
                print(">>> Chrome started successfully.")
            except Exception as e:
                print(f">>> CRITICAL: Could not start selected browser. {e}", flush=True)
                sys.exit(1)


    def login(self, timeout: int = 600):

        """Goes to WhatsApp Web and waits for login/QR scan."""

        self.driver.get("https://web.whatsapp.com/")

        print(">>> Waiting for WhatsApp Web to load...", flush=True)
        

        last_ref = None

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


    def list_chats(self) -> List[ChatChannel]:
        """Scans the 'Chatliste' and returns visible chat names. Waits for stability."""
        print(">>> identifying chats...", flush=True)
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Chatliste']"))
            )
            start_wait = time.time()
            rows = []
            while len(rows) == 0 and (time.time() - start_wait) < 15:
                rows = self.driver.find_elements(By.XPATH, "//div[@aria-label='Chatliste']//div[@role='row']")
                if not rows: time.sleep(1)

            chats = []
            for row in rows:
                try:
                    name_element = row.find_element(By.XPATH, ".//span[@title]")
                    title = name_element.get_attribute("title")
                    try:
                        if row.find_elements(By.XPATH, ".//span[contains(text(), '(du)')]"):
                            title = f"{title} (du)"
                    except:
                        pass
                    
                    is_group = False
                    try:
                        if row.find_elements(By.XPATH, ".//span[@data-icon='default-group-refreshed']"):
                            is_group = True
                    except:
                        pass

                    if title and not any(c.name == title for c in chats):
                        chats.append(ChatChannel(name=title, is_group=is_group))
                except:
                    continue
            return chats
        except Exception as e:
            print(f">>> Error identifying chats: {e}")
            return []

    def list_channels(self) -> List[str]:
        """Navigates to the Updates tab and lists followed channels."""
        print(">>> identifying followed channels...", flush=True)
        try:
            # Click on 'Updates' / 'Aktuelles' tab
            updates_xpath = "//div[@aria-label='Aktuelles' or @aria-label='Updates' or @title='Aktuelles' or @title='Updates']"
            updates_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, updates_xpath)))
            updates_btn.click()
            time.sleep(2)

            # Extract followed channel names
            # On WhatsApp Web, channels are usually displayed in a specific section
            channel_elements = self.driver.find_elements(By.XPATH, "//div[@role='listitem']//span[@dir='auto']")
            channels = list(set([el.text.strip() for el in channel_elements if el.text.strip()]))

            # Go back to 'Chats' tab
            chats_xpath = "//div[@aria-label='Chats' or @title='Chats']"
            self.driver.find_element(By.XPATH, chats_xpath).click()
            time.sleep(1)
            
            return channels
        except Exception as e:
            print(f">>> Error identifying channels: {e}")
            return []



    def get_history(self, chat_name: str, limit: int = 10) -> List[Message]:

        """Fetches history for a Specific chat and formats it as LLM-style Message objects."""

        print(f">>> Fetching history for: '{chat_name}'", flush=True)

        try:

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


                    try:

                        text_el = msg.find_element(By.CSS_SELECTOR, ".copyable-text")

                        content = text_el.text

                        timestamp = text_el.get_attribute("data-pre-plain-text")

                        if "BOT:" in content:

                            role = "outgoing"

                    except:

                        try:

                            audio_indicators = [
                                ".//span[@data-icon='audio-play']",
                                ".//span[@data-icon='ptt-play']",
                                ".//span[@data-icon='ptt-status']",
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
                                # Try to find the duration string (e.g. "0:02")
                                try:
                                    # We look for a div with aria-hidden="true" containing a colon (most reliable indicator)
                                    duration_el = msg.find_element(By.XPATH, ".//div[@aria-hidden='true' and contains(text(), ':')]")
                                    content = f"[Voice Message - {duration_el.text}]"
                                except:
                                    content = "[Voice Message]"
                            elif msg.find_elements(By.TAG_NAME, "video") or msg.find_elements(By.XPATH, ".//span[@data-icon='video-play']"):
                                msg_type = "video"
                                content = "[Video Message]"
                        except:
                            pass

                        # 3. Check for Contact card
                        try:
                            contact_indicators = [
                                ".//button[contains(., 'Kontakt speichern')]",
                                ".//button[contains(., 'Save contact')]",
                                ".//button[contains(@title, 'Nachricht an')]",
                                ".//button[contains(@title, 'Message ')]"
                            ]
                            is_contact = False
                            for selector in contact_indicators:
                                if msg.find_elements(By.XPATH, selector):
                                    is_contact = True
                                    break
                            
                            if is_contact:
                                msg_type = "contact"
                                try:
                                    name_el = msg.find_element(By.CSS_SELECTOR, "div[data-testid='selectable-text']")
                                    content = f"[Contact Card: {name_el.text}]"
                                except:
                                    content = "[Contact Card]"
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


    def send_message(self, chat_name: str, text: str):

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


    def start_chat_with_shared_contact(self, chat_name: str, contact_name: str):
        """Locates a contact card in a chat and clicks 'Message' to start a chat with them."""
        print(f">>> Attempting to start chat with shared contact: '{contact_name}'", flush=True)
        try:
            xpath_chat = f"//div[@aria-label='Chatliste']//span[@title='{chat_name}']"
            WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath_chat))).click()
            time.sleep(2)

            card_xpath = f"//div[@data-testid='selectable-text' and contains(text(), '{contact_name}')]/ancestor::div[@role='button']"
            btn_xpath = ".//button[contains(@title, 'Nachricht') or contains(@title, 'Message')]"
            
            card = self.driver.find_element(By.XPATH, card_xpath)
            msg_button = card.find_element(By.XPATH, btn_xpath)
            msg_button.click()
            
            print(f">>> Successfully opened chat with {contact_name}.")
            return True
        except Exception as e:
            print(f">>> Error accepting contact: {e}")
            return False

    def download_media(self, chat_name: str, message_index: int = -1, media_type: str = None) -> List[str]:
        """
        Finds and downloads media (Audio, Video, Image) from a message.
        Returns a list of base64 data strings.
        """
        print(f">>> Attempting to capture {media_type or 'media'} from '{chat_name}'...", flush=True)
        try:
            # 1. Switch to chat using robust search
            target_msg = None
            try:
                search_box = self.driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
                search_box.click()
                search_box.send_keys(Keys.CONTROL + "a")
                search_box.send_keys(Keys.BACKSPACE)
                search_box.send_keys(chat_name)
                time.sleep(1)
                search_box.send_keys(Keys.ENTER)
                time.sleep(2)

                messages = self.driver.find_elements(By.XPATH, '//div[contains(@class, "message-")]')
                if not messages:
                    print(">>> No messages found in chat.")
                    return []
                
                target_msg = messages[message_index]
            except Exception as e:
                print(f">>> Failed to locate message: {e}")
                return []

            # 2. Trigger Play if audio/video to force blob generation
            if media_type in ["audio", "video"]:
                try:
                    trigger = target_msg.find_element(By.XPATH, ".//span[@data-icon='audio-play' or @data-icon='video-play' or @data-icon='ptt-play']")
                    self.driver.execute_script("arguments[0].click();", trigger)
                    print(f">>> Triggered {media_type} play button (waiting 3s)...")
                except:
                    pass

            # 3. Discover Blobs using Sniffers
            all_unique_blobs = []
            matching_blob_found = False
            
            # Reset recorder
            self.driver.execute_script("if (window.__blob_recorder) window.__blob_recorder = [];")
            
            print(f">>> Searching for {media_type} blobs (up to 15s)...", flush=True)
            time.sleep(2) 
            
            for attempt in range(15):
                sniffer_script = """
                    if (!window.__blob_recorder) {
                        window.__blob_recorder = [];
                        const grab = (val) => {
                            if (val && typeof val === 'string' && val.startsWith('blob:') && !window.__blob_recorder.includes(val)) {
                                window.__blob_recorder.push(val);
                            }
                        };
                        const observer = new MutationObserver((mutations) => {
                            for (const m of mutations) {
                                if (m.type === 'attributes') {
                                    grab(m.target.getAttribute(m.attributeName));
                                    grab(m.target.src || m.target.currentSrc);
                                } else if (m.addedNodes) {
                                    m.addedNodes.forEach(node => {
                                        grab(node.src || node.currentSrc || node.href);
                                        if (node.querySelectorAll) {
                                            node.querySelectorAll('[src],[href]').forEach(el => grab(el.src || el.href));
                                        }
                                    });
                                }
                            }
                        });
                        observer.observe(document.body, { 
                            childList: true, 
                            subtree: true, 
                            attributes: true, 
                            attributeFilter: ['src', 'href', 'data-uri'] 
                        });
                    }
                    function getAllBlobs() {
                        let found = [];
                        if (window.__blob_recorder) {
                            window.__blob_recorder.forEach(b => found.push({url: b, source: 'recorder', isMedia: true}));
                        }
                        try {
                            performance.getEntriesByType('resource')
                                .filter(r => r.name.startsWith('blob:'))
                                .forEach(r => {
                                    let is_m = (r.initiatorType === 'media' || r.initiatorType === 'video' || r.initiatorType === 'audio');
                                    found.push({url: r.name, source: 'performance', initiator: r.initiatorType, isMedia: is_m});
                                });
                        } catch(e) {}
                        function scan(root) {
                            try {
                                let all = root.querySelectorAll('*');
                                for (let el of all) {
                                    let src = el.src || el.currentSrc || el.getAttribute('src') || el.getAttribute('data-uri');
                                    if (src && typeof src === 'string' && src.startsWith('blob:')) {
                                        let is_m = (el.tagName === 'AUDIO' || el.tagName === 'VIDEO' || el.tagName === 'SOURCE');
                                        found.push({url: src, source: 'dom', tag: el.tagName.toLowerCase(), isMedia: is_m});
                                    }
                                    if (el.shadowRoot) scan(el.shadowRoot);
                                }
                            } catch(e) {}
                        }
                        scan(document);
                        return found;
                    }
                    return getAllBlobs();
                """
                
                results = self.driver.execute_script(sniffer_script)
                if results:
                    for res in results:
                        url = res['url']
                        is_match = res.get('isMedia', False)
                        if not is_match and media_type in ["audio", "video"] and res.get('source') == 'performance':
                            if res.get('initiator') in ['media', 'other', 'fetch']:
                                is_match = True
                        
                        if url not in [b['url'] for b in all_unique_blobs]:
                            all_unique_blobs.append({'url': url, 'is_match': is_match})
                            if is_match:
                                matching_blob_found = True
                                print(f">>> Found potential {media_type} blob: {url[:60]}...")

                if matching_blob_found and attempt > 2:
                    break
                time.sleep(1)

            if not all_unique_blobs:
                print(f">>> No blobs found.")
                return []

            # 4. Filter and capture base64
            results_list = []
            sorted_blobs = sorted(all_unique_blobs, key=lambda x: x['is_match'], reverse=True)
            print(f">>> Capturing {len(sorted_blobs)} unique blobs...")

            for i, blob_info in enumerate(sorted_blobs):
                blob_url = blob_info['url']
                try:
                    js_script = """
                        var uri = arguments[0];
                        var callback = arguments[1];
                        fetch(uri).then(res => res.blob()).then(blob => {
                            var reader = new FileReader();
                            reader.onloadend = function() { callback(reader.result); }
                            reader.readAsDataURL(blob);
                        }).catch(e => callback("error: " + e));
                    """
                    self.driver.set_script_timeout(30)
                    base64_data = self.driver.execute_async_script(js_script, blob_url)
                    
                    if base64_data.startswith("error:"):
                        continue

                    header, _ = base64_data.split(",", 1)
                    print(f">>> [{i+1}/{len(sorted_blobs)}] Captured {header.split(';')[0]} blob.")
                    results_list.append(base64_data)
                except Exception as e:
                    print(f">>> Error capturing blob {i}: {e}")

            return results_list
        except Exception as e:
            print(f">>> Error in download_media: {e}")
            return []

    def close(self):
        self.driver.quit()

