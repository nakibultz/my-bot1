import re
import json
import time
import requests
from bs4 import BeautifulSoup

# ==========================================
# CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = "9271214629:AAFBcvqget27W3O0KzlNvx3Xs8nWnLy3dEc"      # Apnar Bot Token din
TELEGRAM_GROUP_ID = "-1003989494988"            # Apnar Telegram Group ID din
LAMIX_API_URL = "https://panel.lamix.org/api/v1/messages?token=h8DCQGYrX07FtCTdm807KCx4_fKyWSgrAu8ixYGTpUk..." # Apnar Lamix Panel er API/CDR URL din
LAMIX_TOKEN = "h8DCQGYrX07FtCTdm807KCx4_fKyWSgrAu8ixYGTpUk"     # Apnar Lamix Panel er Token din

# Dummy stex_assigned_numbers (jodi na thake faka rakhben)
stex_assigned_numbers = {}

def extract_otp_code(text):
    if not text:
        return None
    match = re.search(r'\b\d{4,8}\b', text)
    return match.group(0) if match else None

def send_telegram_otp(number, message, otp):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = (
        f"🔔 <b>NEW OTP RECEIVED</b>\n"
        f"------------------\n"
        f"📱 <b>Number:</b> <code>+{number}</code>\n"
        f"🔑 <b>OTP:</b> <code>{otp}</code>\n"
        f"------------------\n"
        f"💬 <b>Message:</b> {message}"
    )
    payload = {
        "chat_id": TELEGRAM_GROUP_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("ok", False)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

# Apnar bot-er asol parse_panel_response er API logic
def parse_panel_response(response_text):
    results = []
    try:
        data = json.loads(response_text)
        temp_results = []

        def process_item(item):
            pot_nums_list = []
            pot_msg = None
            values = []

            if isinstance(item, dict):
                lower_keys = {str(k).lower(): v for k, v in item.items()}
                
                # Sothik number key guloke priority deya ebong cli ke avoid kora
                for k in ["number", "num", "phone", "msisdn"]:
                    if k in lower_keys and lower_keys[k]:
                        clean_val = re.sub(r'\D', '', str(lower_keys[k]))
                        if 5 <= len(clean_val) <= 18:
                            if clean_val not in pot_nums_list: 
                                pot_nums_list.append(clean_val)
                                
                for k in ["message", "msg", "sms", "content", "text"]:
                    if k in lower_keys and lower_keys[k]:
                        val = str(lower_keys[k])
                        if len(val) > 4:
                            pot_msg = val
                            break
                values = list(item.values())
            elif isinstance(item, list):
                values = item

            for v in values:
                if isinstance(v, (dict, list)) or v is None: continue
                v_str = str(v).strip()

                clean_v = re.sub(r'\D', '', v_str)
                if 7 <= len(clean_v) <= 18 and not re.search(r'[a-zA-Z]', v_str):
                    if not re.search(r'\d{4}[-/]\d{2}[-/]\d{2}', v_str) and not re.search(r'\d{2}:\d{2}:\d{2}', v_str) and "." not in v_str:
                        if clean_v not in pot_nums_list:
                            pot_nums_list.append(clean_v)

                if len(v_str) > 4 and not v_str.isdigit():
                    if extract_otp_code(v_str):
                        if pot_msg is None or len(v_str) > len(pot_msg):
                            pot_msg = v_str

            pot_num = None
            if pot_nums_list:
                matched_user_num = None
                for n in pot_nums_list:
                    if n in stex_assigned_numbers or any(n in str(key) for key in stex_assigned_numbers.keys()):
                        matched_user_num = n
                        break

                if matched_user_num:
                    pot_num = matched_user_num
                else:
                    pot_num = pot_nums_list[0] # Prothom valid number ti nibe

            if pot_num and pot_msg:
                otp = extract_otp_code(pot_msg)
                if otp:
                    temp_results.append({"number": pot_num, "message": pot_msg, "otp": otp})

        def traverse_json(node):
            if isinstance(node, list):
                if len(node) > 0 and not isinstance(node[0], (dict, list)):
                    process_item(node)
                for child in node:
                    if isinstance(child, (dict, list)):
                        traverse_json(child)
            elif isinstance(node, dict):
                process_item(node)
                for val in node.values():
                    if isinstance(val, (dict, list)):
                        traverse_json(val)

        traverse_json(data)

        seen = set()
        for r in temp_results:
            uid = f"{r['number']}_{r['otp']}"
            if uid not in seen:
                seen.add(uid)
                results.append(r)
    except Exception as e:
        print(f"❌ Parse Error: {e}")

    return results

# ==========================================
# MAIN LOOP
# ==========================================
if __name__ == "__main__":
    print("🚀 Lamix Panel Direct Parser Started...")
    processed_otps = set()
    
    headers = {
        "Authorization": f"Bearer {LAMIX_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    while True:
        try:
            res = requests.get(LAMIX_API_URL, headers=headers, timeout=15)
            if res.status_code == 200:
                cdrs = parse_panel_response(res.text)
                for cdr in cdrs:
                    num = cdr["number"]
                    msg = cdr["message"]
                    otp = cdr["otp"]
                    
                    unique_id = f"{num}_{otp}"
                    if unique_id not in processed_otps:
                        success = send_telegram_otp(num, msg, otp)
                        if success:
                            print(f"✅ Forwarded OTP: +{num} -> {otp}")
                            processed_otps.add(unique_id)
                            if len(processed_otps) > 1000:
                                processed_otps.pop()
            else:
                print(f"⚠️ Panel Response Status: {res.status_code}")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            
        time.sleep(5)
      
