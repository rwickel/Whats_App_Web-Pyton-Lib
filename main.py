import time
from whatsapp_web import WhatsAppWeb

SHOW_BROWSER = True  # Set to True to see the browser window, False for headless mode
BROWSER_TYPE = "edge" # "chrome", "edge", or "auto"

if __name__ == "__main__":
    whatsapp = WhatsAppWeb(headless=not SHOW_BROWSER, browser=BROWSER_TYPE)
    
    if whatsapp.login():
        chats = whatsapp.list_chats()
        print(f">>> Found {len(chats)} chats.")

        print(chats)

        for c in chats[:5]: 
            print(f" - {c.name} (is_group={c.is_group})")

        # Fetch some history for a specific chat
        if chats:
            target_chat = chats[0].name # Change this to a valid chat name
            history = whatsapp.get_history(target_chat, limit=5)
            print(f"\n>>> History for {target_chat}:")
            for msg in history:
                print(f"    [{msg.role}] {msg.content}")

            # If the last message contains media, download it
            if history and history[-1].type in ["audio", "video", "image"]:
                msg_type = history[-1].type
                print(f"\n>>> Attempting to capture {msg_type} from last message...")
                
                # download_media now returns a list of base64 strings
                media_blobs = whatsapp.download_media(target_chat, message_index=-1, media_type=msg_type)
                
                if media_blobs:
                    # Add to message for LLM use
                    history[-1].media_base64 = media_blobs
                    
                    print(f">>> Captured {len(media_blobs)} media blobs (base64) for LLM integration.")
                    # We no longer save files to disk as requested.
                else:
                    print(">>> No media blobs captured.")
        else:
            print(">>> No chats found to fetch history from.")

        print("\n>>> Done. Monitoring for unread messages (Press Ctrl+C to stop)...")
        try:
            while True:
                unread = whatsapp.get_unread_chats()
                for chat in unread:
                    print(f">>> Unread message in: {chat.name} ({chat.unread_count})")
                time.sleep(10)
        except KeyboardInterrupt:
            print(">>> Stopping...")
            whatsapp.close()
