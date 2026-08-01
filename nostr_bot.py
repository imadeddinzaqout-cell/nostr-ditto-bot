import os
import time
import requests
from nostr_sdk import Keys, Client, EventBuilder, Filter, Kind, Tag
from datetime import timedelta

# ==========================================
# 1. إعدادات المفاتيح (من GitHub Secrets)
# ==========================================
NOSTR_NSEC = os.getenv("NOSTR_NSEC")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# استخراج مفتاح البوت العام ليتجاهل منشوراته
bot_keys = Keys.parse(NOSTR_NSEC)
BOT_PUBKEY = bot_keys.public_key().to_hex()

# ضع الـ Hex Pubkey الخاص بحسابك الأساسي (imad gaza) هنا
MAIN_ACCOUNT_PUBKEY = "ضع_مفتاحك_الأساسي_هنا"

# القائمة السوداء: المفاتيح التي لن يرد عليها البوت
IGNORED_PUBKEYS = [BOT_PUBKEY, MAIN_ACCOUNT_PUBKEY]

# ==========================================
# 2. العقل المدبر (DeepSeek API)
# ==========================================
def generate_reply(post_text):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """
    You are Emad, a developer and accountant from Gaza. You are interacting on Ditto (a decentralized social app).
    Keep the reply very natural, brief (1-2 sentences), and directly relevant to the user's topic. 
    Do not sound like a bot. Do not repeat the same phrases. 
    If appropriate, you can organically hint at your family's situation or your crowdfunding campaign, but keep it conversational.
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Reply naturally to this post: {post_text}"}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error generating AI reply: {e}")
        return None

# ==========================================
# 3. محرك Ditto / Nostr
# ==========================================
def main():
    print("--- Starting Ditto Bot ---")
    
    # الاتصال بخوادم Ditto الأساسية
    client = Client(bot_keys)
    client.add_relay("wss://relay.ditto.pub")
    client.add_relay("wss://nos.lol")
    client.add_relay("wss://relay.damus.io")
    client.connect()

    # جلب أحدث المنشورات (آخر 10 منشورات نصية كمثال)
    f = Filter().kind(Kind(1)).limit(10)
    
    try:
        # جلب المنشورات من الخوادم
        events = client.get_events_of([f], timedelta(seconds=10))
        
        for event in events:
            author_pubkey = event.author().to_hex()
            
            # فلترة القائمة السوداء (لمنع التكرار والرد على النفس)
            if author_pubkey in IGNORED_PUBKEYS:
                print(f"Skipping post from blacklisted pubkey: {author_pubkey}")
                continue
                
            post_text = event.content()
            print(f"\n--- Found new post on Ditto ---")
            print(f"Content: {post_text[:100]}...")
            
            # توليد الرد
            reply_text = generate_reply(post_text)
            
            if reply_text:
                print(f"AI Reply: {reply_text}")
                
                # بناء وتوقيع الرد ليظهر كتعليق على المنشور الأصلي
                # إضافة Tag للربط بالمنشور الأصلي (e tag) وصاحب المنشور (p tag)
                reply_event = EventBuilder.text_note(reply_text, [
                    Tag.parse(["e", event.id().to_hex(), "", "reply"]),
                    Tag.parse(["p", author_pubkey])
                ]).to_event(bot_keys)
                
                # نشر الرد
                client.send_event(reply_event)
                print("✅ Reply posted successfully on Ditto!")
                
                # تأخير زمني لتجنب حظر الخوادم (Spam Limits)
                time.sleep(30)
                
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
