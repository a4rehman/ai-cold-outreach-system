
import os, re, json, asyncio, operator, warnings, csv, sys, random, smtplib
from typing import TypedDict, List, Optional, Annotated
from datetime import datetime
from email.message import EmailMessage

# Handle Windows Encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --- Integrations ---
from openai import OpenAI
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# LangGraph imports
from langgraph.graph import StateGraph, END

load_dotenv()

# --- Config & Keys ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if OPENAI_API_KEY:
    OPENAI_API_KEY = OPENAI_API_KEY.strip().strip('"').strip("'")

if not OPENAI_API_KEY:
    # Fallback to check if it's named differently
    OPENAI_API_KEY = os.environ.get("openai_key")

if not OPENAI_API_KEY:
    print("❌ ERROR: OPENAI_API_KEY not found in .env file.")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)
console = Console()

# --- Workflow Settings ---
TARGET          = 50                   
DATA_DIR        = "data"
OUTPUT_FILE     = os.path.join(DATA_DIR, "lead_gen_results.json")
CSV_FILE        = os.path.join(DATA_DIR, "leads_for_google_sheets.csv")
MEMORY_FILE     = os.path.join(DATA_DIR, "processed_leads.json") 
AI_MODEL        = "gpt-4o-mini"
AI_MAX_RETRIES  = 3

# --- Prompts ---
VALIDATION_PROMPT = """
You are an expert email quality checker.

Check the following cold email and return JSON only:
{
    "is_good": "YES" or "NO",
    "mistakes": ["list of mistakes in grammar, tone, personalization, or spammy language"],
    "improved_subject": "fixed subject line",
    "improved_message": "fixed email body"
}

Rules:
- Keep it under 120 words
- Make it natural and human
- Avoid generic sales phrases
- Ensure proper personalization
- Clear CTA required
"""

# --- SMTP Config ---
SMTP_SERVER     = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT       = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_USER      = os.environ.get("EMAIL_USER")
EMAIL_PASS      = os.environ.get("EMAIL_PASSWORD")

# --- State Definition ---
class WorkflowState(TypedDict):
    discovered_urls: Annotated[List[str], operator.add]
    current_index: int
    reports: Annotated[List[dict], operator.add]
    node_info: dict
    emails_sent: int
    failed_count: int

    output_json: str
    output_csv: str


# --- Utility Functions ---

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return set(json.load(f))
        except: return set()
    return set()

def save_memory(url):
    try:
        memory = list(load_memory())
        if url not in memory:
            memory.append(url)
            with open(MEMORY_FILE, "w") as f:
                json.dump(memory, f)
    except: pass

def get_next_filename(base_name, extension):
    os.makedirs(DATA_DIR, exist_ok=True)
    counter = 1
    while True:
        file_path = os.path.join(DATA_DIR, f"{base_name}({counter}){extension}")
        if not os.path.exists(file_path):
            return file_path
        counter += 1


def _node_info(state, node, status, message=""):
    ni = state.get("node_info", {})
    ni[node] = {"status": status, "message": message}
    return ni

def print_dashboard(state: WorkflowState, status_line: str = ""):
    table = Table(box=None, expand=True)
    table.add_column("Node", style="bold cyan")
    table.add_column("Status", style="bold magenta")
    table.add_column("Message", style="white")

    ni = state.get("node_info", {})
    nodes = ["discover_leads", "scrape_website", "analyze_with_ai", "validate_with_ai", "send_email", "save_progress"]
    for node in nodes:
        info = ni.get(node, {"status": "⏳ Pending", "message": "Waiting..."})
        table.add_row(node.replace("_", " ").title(), info["status"], info["message"])

    total = len(state["discovered_urls"])
    curr = state["current_index"]
    
    summary_panel = Panel(
        table,
        title=f"🚀 [bold green]LEAD GEN SYSTEM[/] | Progress: {curr}/{TARGET}",
        subtitle=f"Sent: [bold green]{state['emails_sent']}[/] | Failed: [bold red]{state['failed_count']}[/]",
        border_style="bright_blue"
    )
    console.clear()
    console.print(summary_panel)

# --- NODES ---

async def discover_leads(state: WorkflowState):
    ni = _node_info(state, "discover_leads", "🔍 Searching", "Scanning Google Maps...")
    print_dashboard({**state, "node_info": ni})
    
    processed_memory = load_memory()
    cities = [
        "New York City", "Brooklyn", "Manhattan", "Chicago", "Los Angeles",
        "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego",
        "Dallas", "San Jose", "Austin", "Jacksonville", "Fort Worth"
    ]
    random.shuffle(cities)
    
    new_urls = []
    
    async with async_playwright() as p:
        # Switching to headless=False so you can see if it's being blocked
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        page = await context.new_page()
        
        for city in cities:
            if len(new_urls) >= TARGET: break
            
            # Random delay to look human
            await asyncio.sleep(random.uniform(3, 7))
            for attempt in range(2):
                try:
                    # Using Google Local Search (tbm=lcl) which is faster than full Maps
                    search_url = f"https://www.google.com/search?q=beauty+salon+parlor+in+{city.replace(' ', '+')}&tbm=lcl"
                    console.print(f"  [cyan]Searching {city} on Google Local...[/cyan]")
                    
                    # Ensure page is still open
                    if page.is_closed():
                        page = await context.new_page()

                    await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(5)
                    
                    # Extract business websites
                    # In Google Local, websites are usually in <a> tags with specific attributes or text
                    links = await page.query_selector_all('a[aria-label*="Website"], a:has-text("Website")')
                    
                    found_in_city = 0
                    for link in links:
                        if len(new_urls) >= TARGET: break
                        href = await link.get_attribute("href")
                        if not href or "google.com" in href: continue
                        
                        clean_url_match = re.match(r"(https?://[^/\s]+)", href.lower())
                        if clean_url_match:
                            url = clean_url_match.group(1).lower()
                            bad_domains = ["yelp.com", "expertise.com", "fresha.com", "vagaro.com", "yellowpages.com", "mapquest.com", "mindbodyonline.com", "instagram.com", "facebook.com", "tiktok.com", "styleseat.com"]
                            if not any(bad in url for bad in bad_domains) and url not in processed_memory and url not in new_urls:
                                new_urls.append(url)
                                found_in_city += 1
                    
                    if found_in_city > 0:
                        console.print(f"  [green]Found {found_in_city} leads in {city}[/green]")
                        break
                    else:
                        console.print(f"  [yellow]No leads found in {city}, trying next city...[/yellow]")
                        break
                except Exception as e:
                    console.print(f"  [red]Search Error in {city}: {str(e)[:60]}[/red]")
                    if "closed" in str(e).lower():
                        page = await context.new_page() # Recreate page if crashed
                    await asyncio.sleep(5)

        await browser.close()


    ni = _node_info(state, "discover_leads", "✅ Done", f"Found {len(new_urls)} new leads.")
    return {"discovered_urls": new_urls, "node_info": ni}

async def scrape_website(state: WorkflowState):
    urls = state["discovered_urls"]
    idx = state["current_index"]
    if idx >= len(urls): return state

    url = urls[idx]
    ni = _node_info(state, "scrape_website", "🌐 Scraping", f"Fetching {url}")
    print_dashboard({**state, "node_info": ni})

    scrape_data = {"website": url, "text": "", "emails": [], "status": "pending"}
    
    async def get_emails_from_url(client_http, target_url):
        try:
            resp = await client_http.get(target_url, timeout=10.0)
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
            
            # Enhanced exclusion list to prevent false positives
            blocked_domains = [
                'sentry.io', 'wix.com', 'shopify.com', 'google.com', 'example.com', 
                'domain.com', 'mysite.com', 'yourdomain.com', 'email.com', '2x.png', '3x.png'
            ]
            blocked_keywords = ['test', 'example', 'placeholder', 'mysite', 'yourdomain', 'template', 'globe@']
            blocked_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf', '.webp', '.css', '.js')
            
            clean_emails = []
            for email in set(emails):
                email_lower = email.lower()
                
                # Basic validation
                if any(email_lower.endswith(ext) for ext in blocked_extensions): continue
                if any(kw in email_lower for kw in blocked_keywords): continue
                
                # Convert googlemail.com to gmail.com as requested
                if "googlemail.com" in email_lower:
                    email_lower = email_lower.replace("googlemail.com", "gmail.com")
                
                domain = email_lower.split('@')[-1]
                user = email_lower.split('@')[0]
                
                # Final check
                if domain not in blocked_domains and len(user) < 30 and not re.search(r'[a-f0-9]{20,}', user) and 'sentry' not in email_lower and 'noreply' not in email_lower:
                    clean_emails.append(email_lower)
            
            # Prioritize gmail.com addresses
            clean_emails = sorted(list(set(clean_emails)), key=lambda x: ("gmail.com" not in x))

            
            # Extract links to contact/about pages
            soup = BeautifulSoup(resp.text, "html.parser")
            subpages = []
            for a in soup.find_all('a', href=True):
                href = a['href'].lower()
                if any(word in href for word in ['contact', 'about', 'reach', 'get-in-touch']):
                    if href.startswith('/'):
                        subpages.append(target_url.rstrip('/') + href)
                    elif href.startswith('http') and target_url in href:
                        subpages.append(href)
            
            return clean_emails, subpages, soup.stripped_strings
        except:
            return [], [], []

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client_http:
            emails, subpages, strings = await get_emails_from_url(client_http, url)
            scrape_data["text"] = " ".join(strings)[:3000]
            
            # If no emails, try subpages
            if not emails and subpages:
                for subpage in list(set(subpages))[:3]: # Check up to 3 subpages
                    sub_emails, _, _ = await get_emails_from_url(client_http, subpage)
                    if sub_emails:
                        emails.extend(sub_emails)
                        break
            
            scrape_data["emails"] = list(set(emails))
            
        ni = _node_info(state, "scrape_website", "✅ Done", f"Found {len(scrape_data['emails'])} valid email(s)")
    except:
        ni = _node_info(state, "scrape_website", "⚠️ Failed", "Scraping error")
        scrape_data["status"] = "scrape_failed"

    reports = [scrape_data]
    return {"reports": reports, "node_info": ni}

async def analyze_with_ai(state: WorkflowState):
    if not state.get("reports"):
        ni = _node_info(state, "analyze_with_ai", "⏭ Skipped", "No reports to analyze")
        return {"node_info": ni}
        
    report = state["reports"][-1]
    if report.get("status") == "scrape_failed":
        ni = _node_info(state, "analyze_with_ai", "⏭ Skipped", "No data")
        return {"node_info": ni}

    ni = _node_info(state, "analyze_with_ai", "🤖 AI Analyzing", f"Processing {report['website']}")
    print_dashboard({**state, "node_info": ni})

    prompt = f"""
    You are an expert cold email copywriter.
    Your job is to generate SHORT, HUMAN, and HIGH-CONVERTING cold emails for local businesses and salons.
    
    The emails must:
    - sound natural and professional
    - NOT sound robotic or spammy
    - be personalized using business details
    - focus on helping the business improve online presence
    - be concise (80–140 words)
    - include a simple CTA
    - use the sender name: Abdul Rehman
    
    ========================
    INPUT DATA
    ========================
    Business Website: {report['website']}
    Scraped Content: {report['text']}
    Our Website: 100solutionz.vercel.app
    Our Location: London, England
    
    ========================
    EMAIL REQUIREMENTS
    ========================
    1. Create:
       - business_name
       - email_subject
       - email_message
    
    2. The email should:
       - appreciate something about the business found in the scraped content
       - mention 1–2 real issues or optimization opportunities found in the content
       - explain how digital improvements (like local SEO or pro booking) can help
       - ask for a short call or discussion
    
    3. Tone:
       - friendly, confident, professional, and human
    
    4. Avoid:
       - fake urgency, overpromising, spam wording, or long paragraphs
    
    5. End every email with:
    
    Best regards,
    Abdul Rehman
    
    ========================
    OUTPUT FORMAT
    ========================
    Return ONLY valid JSON:
    
    {{
      "business_name": "...",
      "email_subject": "...",
      "email_message": "..."
    }}
    """

    for attempt in range(AI_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "system", "content": "You are a business analyst. Output JSON only."},
                          {"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            ai_data = json.loads(response.choices[0].message.content)
            report.update(ai_data)
            ni = _node_info(state, "analyze_with_ai", "✅ Done", "Analysis complete")
            return {"reports": [report], "node_info": ni}
        except:
            await asyncio.sleep((attempt + 1) * 3)
            
    ni = _node_info(state, "analyze_with_ai", "❌ Failed", "AI unreachable")
    report["status"] = "ai_failed"
    return {"node_info": ni, "failed_count": state["failed_count"] + 1}

async def validate_with_ai(state: WorkflowState):
    if not state.get("reports"):
        return {"node_info": _node_info(state, "validate_with_ai", "⏭ Skipped", "No report")}
        
    report = state["reports"][-1]
    if report.get("status") in ["scrape_failed", "ai_failed"]:
        return {"node_info": _node_info(state, "validate_with_ai", "⏭ Skipped", "No content")}

    ni = _node_info(state, "validate_with_ai", "🛡️ Validating", f"Reviewing email for {report['website']}")
    print_dashboard({**state, "node_info": ni})

    validation_input = f"""
    Subject: {report.get('email_subject')}
    Message: {report.get('email_message')}
    """

    for attempt in range(AI_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "system", "content": VALIDATION_PROMPT},
                          {"role": "user", "content": validation_input}],
                response_format={ "type": "json_object" }
            )
            val_data = json.loads(response.choices[0].message.content)
            
            # Apply improvements
            report["validation_results"] = val_data
            if val_data.get("improved_subject"):
                report["email_subject"] = val_data["improved_subject"]
            if val_data.get("improved_message"):
                report["email_message"] = val_data["improved_message"]
            
            ni = _node_info(state, "validate_with_ai", "✅ Done", f"Quality: {val_data.get('is_good')}")
            return {"reports": [report], "node_info": ni}
        except:
            await asyncio.sleep(2)
            
    ni = _node_info(state, "validate_with_ai", "⚠️ Warning", "Validation failed, using original")
    return {"node_info": ni}

async def send_email_node(state: WorkflowState):
    if not state.get("reports"):
        return {"node_info": _node_info(state, "send_email", "⏭ Skipped", "No report")}
        
    report = state["reports"][-1]
    
    # Check if we have credentials
    if not EMAIL_USER or not EMAIL_PASS:
        ni = _node_info(state, "send_email", "⏭ Skipped", "SMTP credentials missing in .env")
        return {"node_info": ni}

    if not report.get("emails") or report.get("status") != "pending":
        ni = _node_info(state, "send_email", "⏭ Skipped", "No email address found")
        return {"node_info": ni}

    target_email = report["emails"][0].strip()

    # --- VALIDATION: Email Format ---
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, target_email):
        ni = _node_info(state, "send_email", "⏭ Skipped", "Invalid email format")
        report["status"] = "invalid_email"
        return {"node_info": ni}

    # --- VALIDATION: Subject ---
    subject = report.get("email_subject", "").strip()
    if not subject or subject in ["...", "Subject", "None", "null"] or len(subject) < 3:
        ni = _node_info(state, "send_email", "⏭ Skipped", "Invalid or missing subject")
        report["status"] = "invalid_subject"
        return {"node_info": ni}

    ni = _node_info(state, "send_email", "📧 Sending", f"To: {target_email}")
    print_dashboard({**state, "node_info": ni})

    try:
        msg = EmailMessage()
        msg.set_content(report.get("email_message", ""))
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = target_email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
            
        report["status"] = "sent"
        return {"emails_sent": state["emails_sent"] + 1, "node_info": _node_info(state, "send_email", "✅ Sent", "Email delivered")}
    except Exception as e:
        report["status"] = "email_failed"
        return {"failed_count": state["failed_count"] + 1, "node_info": _node_info(state, "send_email", "❌ Error", "SMTP failed")}

async def save_progress(state: WorkflowState):
    if not state.get("reports"):
        return {"node_info": _node_info(state, "save_progress", "⏭ Skipped", "No report")}
        
    ni = _node_info(state, "save_progress", "💾 Saving", "Updating files...")
    report = state["reports"][-1]
    save_memory(report["website"]) 
    
    output_json = state.get("output_json", OUTPUT_FILE)
    output_csv = state.get("output_csv", CSV_FILE)

    # Update JSON
    try:
        all_data = []
        if os.path.exists(output_json):
            with open(output_json, "r") as f: all_data = json.load(f)
        all_data.append(report)
        with open(output_json, "w") as f: json.dump(all_data, f, indent=2)
        
        # Update CSV
        file_exists = os.path.exists(output_csv)
        with open(output_csv, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Name", "Email", "Message", "Website", "Status"])
            writer.writerow([report.get("business_name", "Unknown"), report.get("emails")[0] if report.get("emails") else "N/A", report.get("email_message"), report.get("website"), report.get("status")])
            
        ni = _node_info(state, "save_progress", "✅ Done", f"Saved to {os.path.basename(output_csv)}")

    except: ni = _node_info(state, "save_progress", "❌ Error", "Write error")

    return {"current_index": state["current_index"] + 1, "node_info": ni}

# --- GRAPH ---
def build_graph():
    g = StateGraph(WorkflowState)
    g.add_node("discover_leads", discover_leads)
    g.add_node("scrape_website", scrape_website)
    g.add_node("analyze_with_ai", analyze_with_ai)
    g.add_node("validate_with_ai", validate_with_ai)
    g.add_node("send_email", send_email_node)
    g.add_node("save_progress", save_progress)

    g.set_entry_point("discover_leads")
    g.add_edge("discover_leads", "scrape_website")
    g.add_edge("scrape_website", "analyze_with_ai")
    g.add_edge("analyze_with_ai", "validate_with_ai")
    g.add_edge("validate_with_ai", "send_email")
    g.add_edge("send_email", "save_progress")
    
    def should_continue(state):
        if state["emails_sent"] >= TARGET:
            return END
        if state["current_index"] < len(state["discovered_urls"]):
            return "scrape_website"
        return "discover_leads"

    g.add_conditional_edges("save_progress", should_continue)
    return g.compile()

async def run_pipeline():
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    console.print(Panel("[bold yellow]LEAD GEN SYSTEM v2.0[/]\n[dim]Professional Pipeline Initialized...[/]", border_style="yellow"))
    app = build_graph()
    
    # Generate unique filenames for this run
    current_json = get_next_filename("lead_gen_results", ".json")
    current_csv = get_next_filename("leads_for_google_sheets", ".csv")
    
    initial_state = {
        "discovered_urls": [],
        "current_index": 0,
        "reports": [],
        "node_info": {},
        "emails_sent": 0,
        "failed_count": 0,
        "output_json": current_json,
        "output_csv": current_csv
    }

    try:
        await app.ainvoke(initial_state)
    except Exception as e:
        console.print(f"\n[bold red]FATAL ERROR:[/] {e}")
    console.rule("[bold green]SESSION COMPLETE[/bold green]")

