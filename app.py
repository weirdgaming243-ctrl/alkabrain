# Master Node Alpha Running
# Node: 01 | Relay: Alpha
import os, time, re, random, smtplib, traceback
from playwright.sync_api import sync_playwright
from supabase import create_client, Client
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
EXT_PATH     = os.path.join(os.getcwd(), "my_extension")

print("=" * 50, flush=True)
print("🚀 ALKABRAIN Node 01 (Alpha) Starting...", flush=True)
print("=" * 50, flush=True)

if not SUPABASE_URL:
    print("❌ SECRET MISSING: SUPABASE_URL nahi hai!", flush=True)
    exit(1)
else:
    print("✅ SUPABASE_URL found", flush=True)

if not SUPABASE_KEY:
    print("❌ SECRET MISSING: SUPABASE_SERVICE_KEY nahi hai!", flush=True)
    exit(1)
else:
    print("✅ SUPABASE_SERVICE_KEY found", flush=True)

if not os.getenv("AUTH_SESSION"):
    print("⚠️  AUTH_SESSION nahi mila (optional)", flush=True)
else:
    print("✅ AUTH_SESSION found", flush=True)

if not os.path.exists(EXT_PATH):
    print(f"❌ my_extension folder nahi mila: {EXT_PATH}", flush=True)
    exit(1)
else:
    files = os.listdir(EXT_PATH)
    print(f"✅ my_extension found ({len(files)} files)", flush=True)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    supabase.table("task_queue").select("id").limit(1).execute()
    print("✅ Supabase connected & tested!", flush=True)
except Exception as e:
    print(f"❌ Supabase failed: {e}", flush=True)
    exit(1)

session_text = os.getenv("AUTH_SESSION")
if session_text:
    try:
        with open("auth.json", "w") as f:
            f.write(session_text)
        print("✅ auth.json saved!", flush=True)
    except Exception as e:
        print(f"⚠️ auth.json save failed: {e}", flush=True)

def get_email_template(occ):
    templates = [
        {
            "subject": f"Business Inquiry for {occ}",
            "body": f"Hi,\n\nI came across your {occ} services online and was really impressed. "
                    f"Are you currently taking on new clients or open to business collaborations? "
                    f"Let me know!\n\nBest regards,"
        },
        {
            "subject": f"Question regarding your {occ} services",
            "body": f"Hello,\n\nI was searching for top-tier {occ} professionals and found your profile. "
                    f"I have a quick business inquiry. Are you available for a brief chat this week?\n\nThanks,"
        },
        {
            "subject": f"Collaboration opportunities - {occ}",
            "body": f"Hi there,\n\nI'm reaching out because I'm looking to connect with experienced {occ} "
                    f"experts for potential client referrals and collaborations. "
                    f"Would you be open to discussing this?\n\nLooking forward to hearing from you,"
        },
    ]
    return random.choice(templates)

def validate_email(raw):
    email = raw.lower().strip().rstrip('.')
    if re.match(r'^[a-z0-9._%+-]+@gmail\.com$', email):
        return email
    return None

def send_outreach(sender, pwd, target, occ):
    template = get_email_template(occ)
    msg = MIMEMultipart()
    msg['From']    = sender
    msg['To']      = target
    msg['Subject'] = template['subject']
    msg.attach(MIMEText(template['body'], 'plain'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as s:
            s.login(sender, pwd)
            s.send_message(msg)
        print(f"   📨 Template: '{template['subject']}'", flush=True)
        return True
    except Exception as e:
        print(f"⚠️ Mail Error to {target}: {e}", flush=True)
        return False

def run_ghost_hunter():
    res = supabase.table("task_queue").select("*").eq("status", "pending").limit(5).execute()
    if not res.data:
        print("💤 Koi task nahi. Node so raha hai.", flush=True)
        return

    print(f"📋 {len(res.data)} tasks mile!", flush=True)

    for task in res.data:
        task_id = task['id']
        camp_id = task['campaign_id']
        query   = task['query']

        print(f"\n🎯 Hunting: {query}", flush=True)

        c_res = supabase.table("campaigns").select("*").eq("id", camp_id).single().execute()
        if not c_res.data:
            print(f"❌ Campaign {camp_id} nahi mila, skip", flush=True)
            supabase.table("task_queue").update({"status": "failed"}).eq("id", task_id).execute()
            continue

        camp = c_res.data
        supabase.table("task_queue").update({"status": "processing"}).eq("id", task_id).execute()

        with sync_playwright() as p:
            auth_file = "auth.json" if os.path.exists("auth.json") else None
            try:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir="./gh_profile",
                    headless=False,
                    storage_state=auth_file,
                    args=[
                        f"--disable-extensions-except={EXT_PATH}",
                        f"--load-extension={EXT_PATH}",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ]
                )
                print("✅ Browser launched!", flush=True)
            except Exception as e:
                print(f"❌ Browser launch failed: {e}\n{traceback.format_exc()}", flush=True)
                supabase.table("task_queue").update({"status": "failed"}).eq("id", task_id).execute()
                continue

            page = browser.pages[0] if browser.pages else browser.new_page()

            try:
                page.goto(
                    f"https://www.google.com/search?q={query.replace(' ', '+')}&num=100",
                    timeout=30000
                )
                print("✅ Google loaded!", flush=True)
                print("⏳ 15 sec wait (Hunter Extension)...", flush=True)
                time.sleep(15)
                page.mouse.wheel(0, 2000)
                time.sleep(3)

                emails = re.findall(
                    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                    page.content()
                )
                print(f"📧 {len(set(emails))} unique emails mile", flush=True)

                count = 0
                for raw in set(emails):
                    valid = validate_email(raw)
                    if valid:
                        if send_outreach(camp['sender_email'], camp['app_password'], valid, camp['occupation']):
                            supabase.table("leads").insert({
                                "campaign_id": camp_id,
                                "email": valid,
                                "status": "sent"
                            }).execute()
                            count += 1
                            print(f"✉️  Sent: {valid}", flush=True)
                            delay = random.uniform(30, 60)
                            print(f"⏳ Anti-spam: {delay:.0f}s wait...", flush=True)
                            time.sleep(delay)

                print(f"\n✅ Task done. Total leads: {count}", flush=True)
                try:
                    supabase.rpc('update_campaign_stats', {'camp_id': camp_id, 'inc_leads': count}).execute()
                except Exception as e:
                    print(f"⚠️ Stats update failed: {e}", flush=True)

            except Exception as e:
                print(f"❌ Hunt error: {e}\n{traceback.format_exc()}", flush=True)
            finally:
                supabase.table("task_queue").update({"status": "completed"}).eq("id", task_id).execute()
                browser.close()

    print(f"\n🏆 Node 01 (Alpha) — All tasks complete!", flush=True)

if __name__ == "__main__":
    run_ghost_hunter()

# End of Node 01 — Alpha
