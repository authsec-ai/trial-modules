# Aegis --- Voice AI Agent with CIBA Authentication (AuthSec SDK)

A Jarvis-like voice assistant that searches and books flights. Uses the **AuthSec CIBA SDK** to authenticate users via mobile push notifications at booking time --- no passwords, no login screens, just approve on your phone.

**Key idea:** Browsing and searching flights requires zero authentication. Only when the user says "book it" does the agent trigger a CIBA push notification to verify their identity.

---

## How CIBA Authentication Works

**CIBA** (Client-Initiated Backchannel Authentication) lets an AI agent authenticate a user without redirecting them to a browser. The agent sends a push notification to the user's phone, and the user approves or denies from the AuthSec mobile app.

```
User (voice): "Book flight option 2"
        |
        v
  +-------------+       +-----------------+       +------------------+
  | Voice Agent |------>| AuthSec CIBA API|------>| User's Phone     |
  | (Aegis)     |       | (push notify)   |       | (AuthSec App)    |
  +-------------+       +-----------------+       +------------------+
        |                       |                         |
        |                  polls for                  user taps
        |                  approval                   "Approve"
        |                       |                         |
        v                       v                         v
  +-----------+          +-------------+           +-----------+
  | Booking   |<---------| Auth Token  |<----------| Approved! |
  | Confirmed |          | Returned    |           +-----------+
  +-----------+          +-------------+
```

If the push notification isn't approved (phone offline, timeout), the agent falls back to a **TOTP 6-digit code** --- spoken by the user and verified via the same SDK.

---

## AuthSec SDK Usage --- CIBAClient

This demo uses three methods from the AuthSec SDK's `CIBAClient`:

### 1. Initialize the Client

```python
from AuthSec_SDK import CIBAClient

ciba = CIBAClient(
    client_id="b1e16626-5fcc-49ea-9a3b-a5a742641141",
    base_url="https://prod.api.authsec.ai",
)
```

| Parameter    | Description                                  |
|-------------|----------------------------------------------|
| `client_id` | Your application's UUID from [app.authsec.ai](https://app.authsec.ai) |
| `base_url`  | AuthSec API endpoint                         |

### 2. Send Push Notification

```python
result = ciba.initiate_app_approval(email)
auth_req_id = result["auth_req_id"]
```

Sends a push notification to the user's AuthSec mobile app. Returns an `auth_req_id` used to poll for the result.

### 3. Poll for Approval

```python
approval = ciba.poll_for_approval(
    email=email,
    auth_req_id=auth_req_id,
    interval=5,      # poll every 5 seconds
    timeout=120,      # give up after 2 minutes
)

if approval["status"] == "approved":
    token = approval["token"]  # JWT access token
```

Blocks until the user approves/denies or the timeout is reached.

### 4. TOTP Fallback (Optional)

```python
result = ciba.verify_totp(email, "123456")

if result["success"]:
    token = result["token"]
```

If the push notification fails, the user can speak a 6-digit TOTP code from their authenticator app.

---

## CIBAClient API Reference

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `CIBAClient(client_id, base_url)` | `client_id`: str, `base_url`: str | CIBAClient instance | Initialize the CIBA client |
| `initiate_app_approval(email)` | `email`: str | `{"auth_req_id": "..."}` | Send push notification to user's phone |
| `poll_for_approval(email, auth_req_id, interval, timeout)` | `email`: str, `auth_req_id`: str, `interval`: int, `timeout`: int | `{"status": "approved", "token": "..."}` | Wait for user to approve on their phone |
| `verify_totp(email, code)` | `email`: str, `code`: str (6 digits) | `{"success": bool, "token": "...", "remaining": int}` | Verify a TOTP code as fallback |

---

## Architecture

```
voice_agent.py
  |
  +-- AudioManager          # Voice I/O (Whisper STT + OpenAI TTS + VAD)
  |     - record_until_silence()   # Mic capture with voice activity detection
  |     - transcribe(pcm)          # OpenAI Whisper API
  |     - speak(text)              # OpenAI TTS API (voice: onyx)
  |
  +-- CIBAAuthenticator     # AuthSec CIBA SDK integration
  |     - authenticate()           # Full flow: email -> push -> poll -> token
  |     - _ciba_flow(email)        # Push notification + polling
  |     - _totp_fallback(email)    # 6-digit code fallback via voice
  |     - _get_email_via_voice()   # Voice-guided email capture
  |
  +-- VoiceAgent             # Main agent (GPT-4o-mini + tool calling)
  |     - chat(user_input)         # LLM conversation with tool execution
  |     - run()                    # Voice interaction loop
  |     - execute_tool(name, args) # Route to tool executors
  |
  +-- AmadeusClient          # Live flight data (optional)
  +-- MockFlightData         # Realistic mock flights (fallback)
```

### When Does Authentication Happen?

| Action | Auth Required? |
|--------|---------------|
| "Search flights from NYC to LA" | No |
| "What's the cheapest option?" | No |
| "Search the web for..." | No |
| "What time is it?" | No |
| **"Book flight option 2"** | **Yes --- CIBA push notification** |
| "Check my booking status" | No (session-scoped) |

Authentication is triggered **once per session** --- after the first booking, subsequent bookings reuse the token.

---

## Prerequisites

### 1. AuthSec Account

1. Sign up at [app.authsec.ai](https://app.authsec.ai)
2. Install the **AuthSec mobile app** on your phone
3. Register your account in the mobile app (same email)

### 2. Install the AuthSec SDK

**Option A: From PyPI (recommended for trying it out)**

```bash
pip install authsec-sdk
```

**Option B: From source (recommended for SDK development)**

```bash
git clone https://github.com/authsec-ai/sdk-authsec.git
pip install -e /path/to/sdk-authsec/packages/python-sdk
```

### 3. Configure the SDK

**Path 1: `authsec init` (recommended --- interactive setup)**

```bash
cd ai-voice-agent
authsec init
```

```
AuthSec SDK --- interactive setup

Use default AuthSec URLs or custom? (default/custom) [default]: default
client_id (required): a1b2c3d4-e5f6-7890-abcd-ef1234567890

Config saved to /path/to/ai-voice-agent/.authsec.json
```

This creates `.authsec.json` in the current directory. The voice agent **automatically reads it** at startup --- no manual config needed.

> **Troubleshooting: `authsec: command not found`**
>
> If `authsec init` fails, pip likely installed the binary to a directory not on your PATH:
> ```bash
> # Quick fix --- run with full path:
> /Users/<you>/Library/Python/3.11/bin/authsec init
>
> # Permanent fix --- add to ~/.zshrc or ~/.bashrc:
> export PATH="$PATH:$HOME/Library/Python/3.11/bin"
> source ~/.zshrc
> ```

**Path 2: Manual `.env` file**

```bash
cp .env.example .env
# Edit .env and set CLIENT_ID
```

**Configuration Priority Chain**

| Priority | Source | Example |
|----------|--------|---------|
| 1 | CLI flags | `python voice_agent.py --client-id "..."` |
| 2 | Environment variables | `export CLIENT_ID=...` |
| 3 | `.authsec.json` in cwd | Created by `authsec init` |
| 4 | Hardcoded defaults | `https://prod.api.authsec.ai` (for CIBA URL) |

### 4. OpenAI API Key

Required for voice I/O (Whisper STT, TTS) and the LLM (GPT-4o-mini).

```bash
export OPENAI_API_KEY=sk-proj-...
```

### 5. System Dependencies

**macOS:**
```bash
brew install portaudio
```

**Ubuntu/Debian:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
```

**Windows:**
```
PortAudio is bundled with the sounddevice pip package.
```

---

## Quick Start

```bash
# 1. Navigate to the voice agent directory
cd ai-voice-agent

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure AuthSec (creates .authsec.json with your client_id)
authsec init

# 4. Export your OpenAI API key
export OPENAI_API_KEY=sk-proj-...

# 5. Run the agent
python voice_agent.py
```

### Alternative: Pass config via CLI flags

```bash
python voice_agent.py --client-id YOUR_CLIENT_ID --ciba-base-url https://prod.api.authsec.ai
```

---

## What Happens When You Run It

### Startup

```
[Config] client_id:       b1e16626-5fcc-49ea-9a3b-a5a742641141
[Config] ciba_base_url:   https://prod.api.authsec.ai
[Config] amadeus_api_key: not set (mock mode)

============================================================
  AEGIS --- Flight Booking Voice Assistant
============================================================
  Flight data: Mock data
  Auth: CIBA push notification (triggered at booking time)
  Tools: ['search_flights', 'book_flight', 'get_booking_status', 'web_search', 'calculator', 'get_current_time']
  Say 'goodbye' to exit
============================================================
```

Aegis speaks a greeting and begins listening for your voice.

### Example Conversation

```
You (voice): "Find me flights from New York to Los Angeles on April 15th"
  [Tool] search_flights({"origin":"New York","destination":"Los Angeles","departure_date":"2025-04-15"})
  [Mock] Generated 5 flights

Aegis: "I found 5 flights from JFK to LAX on April 15th. Option 1 is Delta,
        departing at 7:30 AM, arriving at 11:15 AM, nonstop, for 242 dollars..."

You (voice): "Book option 1"
  [Tool] book_flight({"flight_number":"1"})

Aegis: "Before I can book this flight, I need to verify your identity."
Aegis: "Please say your email address."

You (voice): "john at example dot com"

Aegis: "I heard john@example.com. Is that correct?"

You (voice): "Yes"

Aegis: "Sending a verification request to the AuthSec app for john@example.com."
Aegis: "A notification has been sent to your phone. Please approve it."
  [CIBA] User approved! Token received.

Aegis: "Identity verified. Your booking is confirmed! Reference: A3F8B2C1."
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **Yes** | --- | OpenAI API key (for Whisper, TTS, GPT-4o-mini) |
| `CLIENT_ID` | No | from `.authsec.json` | AuthSec application client ID |
| `CIBA_BASE_URL` | No | `https://prod.api.authsec.ai` | AuthSec CIBA API endpoint |
| `AMADEUS_API_KEY` | No | --- | Amadeus API key for live flight data |
| `AMADEUS_API_SECRET` | No | --- | Amadeus API secret |

### Configuration Priority

| Priority | Source |
|----------|--------|
| 1 | CLI flags (`--client-id`, `--ciba-base-url`) |
| 2 | Environment variables (`CLIENT_ID`, `CIBA_BASE_URL`) |
| 3 | `.authsec.json` in cwd (created by `authsec init`) |
| 4 | `.env` file (loaded by python-dotenv) |

---

## Flight Data Sources

| Source | When Used | Setup |
|--------|-----------|-------|
| **Mock data** | Default (no Amadeus keys) | No setup needed --- generates realistic flights |
| **Amadeus API** | When `AMADEUS_API_KEY` and `AMADEUS_API_SECRET` are set | Free at [developers.amadeus.com](https://developers.amadeus.com/) (2000 req/month) |

The agent automatically falls back to mock data if the Amadeus API is unavailable or returns an error.

---

## Tools Available to the Agent

| Tool | Description | Auth Required |
|------|-------------|--------------|
| `search_flights` | Search flights by origin, destination, and date | No |
| `book_flight` | Book a flight from search results | **Yes (CIBA)** |
| `get_booking_status` | Check booking by reference or list all | No |
| `web_search` | Search the web via DuckDuckGo | No |
| `calculator` | Evaluate math expressions | No |
| `get_current_time` | Get current date and time | No |

---

## File Structure

```
ai-voice-agent/
├── voice_agent.py      # Main agent --- voice I/O, CIBA auth, flight tools
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── README.md           # This file
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No module named 'sounddevice'` | Install PortAudio: `brew install portaudio` (macOS) then `pip install sounddevice` |
| `Microphone not available` | Check system permissions --- allow terminal/app access to microphone |
| `CIBA push not received` | Ensure the AuthSec mobile app is installed and you're signed in with the same email |
| `TOTP code rejected` | Make sure you're reading the code from your AuthSec authenticator, not a different app |
| `No flights found` | Mock data covers major routes. Try common city pairs like "New York to Los Angeles" |
| `OpenAI API error` | Verify `OPENAI_API_KEY` is exported: `echo $OPENAI_API_KEY` |

---

## Compare With

| Demo | SDK Feature | Auth Trigger |
|------|-------------|-------------|
| [ai-agent/protected](../ai-agent/protected/) | DelegationClient --- scoped tokens, permission gates | Pre-flight (pull token before acting) |
| **ai-voice-agent** (this) | **CIBAClient --- mobile push + TOTP fallback** | **At booking time (user-initiated)** |
| [mcp-server/protected](../mcp-server/protected/) | `@protected_by_AuthSec` decorator --- RBAC | Every tool call (decorator-enforced) |
