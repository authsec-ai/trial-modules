"""
Aegis --- Jarvis-like Voice AI Assistant for Flight Booking.

A voice-controlled AI assistant that searches and books flights using
the Amadeus API (with mock data fallback). Authentication via CIBA
push notifications happens only at booking time --- no auth needed to
browse or search.

Voice I/O:
  - STT:  OpenAI Whisper API
  - TTS:  OpenAI TTS API (voice: onyx)
  - VAD:  webrtcvad (voice activity detection)
  - Audio: sounddevice (capture + playback)

Flight Data:
  - Primary: Amadeus Self-Service API (test environment, 2000 req/month free)
  - Fallback: Realistic mock flight data

Auth:
  - CIBA mobile push notification via AuthSec SDK
  - TOTP 6-digit code fallback
  - Triggered only when user books a flight

Usage:
  1. Run: authsec init  (creates .authsec.json with your client_id)
  2. Export your OpenAI API key:  export OPENAI_API_KEY=sk-...
  3. python3 voice_agent.py
"""

import asyncio
import argparse
import datetime
import hashlib
import io
import json
import math
import os
import random
import re
import sys
import threading
import wave
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

# Load .env file (if present) before reading config
load_dotenv()

import numpy as np
import sounddevice as sd
import webrtcvad
import aiohttp
from openai import OpenAI

from authsec_sdk import CIBAClient


# ---------------------------------------------------------
# Configuration — .authsec.json > env vars > defaults
# ---------------------------------------------------------

def _load_authsec_json() -> dict:
    """Load .authsec.json created by `authsec init`, if it exists."""
    config_path = os.path.join(os.getcwd(), ".authsec.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}

_authsec_config = _load_authsec_json()

# Priority: env var > .authsec.json > hardcoded default
CLIENT_ID = os.getenv("CLIENT_ID") or _authsec_config.get("client_id", "")
CIBA_BASE_URL = os.getenv("CIBA_BASE_URL") or _authsec_config.get("ciba_base_url", "https://prod.api.authsec.ai")
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY", "")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET", "")


# ---------------------------------------------------------
# Tool Definitions --- Aegis capabilities
# ---------------------------------------------------------

AEGIS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search for available flights between two cities on a specific date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin city name or IATA airport code (e.g. 'New York' or 'JFK')",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination city name or IATA airport code (e.g. 'Los Angeles' or 'LAX')",
                    },
                    "departure_date": {
                        "type": "string",
                        "description": "Departure date in YYYY-MM-DD format",
                    },
                    "return_date": {
                        "type": "string",
                        "description": "Return date in YYYY-MM-DD format (optional, for round-trip)",
                    },
                    "passengers": {
                        "type": "integer",
                        "description": "Number of passengers (default: 1)",
                        "default": 1,
                    },
                },
                "required": ["origin", "destination", "departure_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_flight",
            "description": "Book a specific flight from the most recent search results. Requires identity verification via mobile app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number": {
                        "type": "string",
                        "description": "The flight option number from search results (e.g. '1', '2', '3')",
                    },
                },
                "required": ["flight_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_booking_status",
            "description": "Check the status of a booking by reference number, or list all bookings if no reference provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_reference": {
                        "type": "string",
                        "description": "Booking reference code (optional --- omit to see all bookings)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results to return (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression safely.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression (e.g. '2**10', 'math.sqrt(144)', '(45*3)+17')",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ---------------------------------------------------------
# Airport Code Lookup
# ---------------------------------------------------------

AIRPORT_CODES = {
    # US major airports
    "new york": "JFK", "nyc": "JFK", "jfk": "JFK",
    "newark": "EWR", "ewr": "EWR",
    "los angeles": "LAX", "la": "LAX", "lax": "LAX",
    "chicago": "ORD", "ord": "ORD",
    "miami": "MIA", "mia": "MIA",
    "san francisco": "SFO", "sf": "SFO", "sfo": "SFO",
    "seattle": "SEA", "sea": "SEA",
    "boston": "BOS", "bos": "BOS",
    "atlanta": "ATL", "atl": "ATL",
    "dallas": "DFW", "dfw": "DFW",
    "denver": "DEN", "den": "DEN",
    "houston": "IAH", "iah": "IAH",
    "phoenix": "PHX", "phx": "PHX",
    "las vegas": "LAS", "vegas": "LAS", "las": "LAS",
    "orlando": "MCO", "mco": "MCO",
    "washington": "DCA", "dc": "DCA", "dca": "DCA",
    "detroit": "DTW", "dtw": "DTW",
    "minneapolis": "MSP", "msp": "MSP",
    "tampa": "TPA", "tpa": "TPA",
    "san diego": "SAN", "san": "SAN",
    "portland": "PDX", "pdx": "PDX",
    "austin": "AUS", "aus": "AUS",
    "nashville": "BNA", "bna": "BNA",
    # International
    "london": "LHR", "lhr": "LHR", "heathrow": "LHR",
    "paris": "CDG", "cdg": "CDG",
    "tokyo": "NRT", "nrt": "NRT", "narita": "NRT",
    "toronto": "YYZ", "yyz": "YYZ",
    "dubai": "DXB", "dxb": "DXB",
    "singapore": "SIN", "sin": "SIN",
    "hong kong": "HKG", "hkg": "HKG",
    "sydney": "SYD", "syd": "SYD",
    "mumbai": "BOM", "bom": "BOM",
    "delhi": "DEL", "del": "DEL",
    "bangalore": "BLR", "blr": "BLR",
    "cancun": "CUN", "cun": "CUN",
}


def resolve_airport_code(city_or_code: str) -> str:
    """Resolve a city name or IATA code to a 3-letter IATA code."""
    normalized = city_or_code.strip().lower()
    if len(normalized) == 3 and normalized.isalpha():
        return normalized.upper()
    if normalized in AIRPORT_CODES:
        return AIRPORT_CODES[normalized]
    for key, code in AIRPORT_CODES.items():
        if key in normalized:
            return code
    return city_or_code.strip().upper()[:3]


# ---------------------------------------------------------
# Mock Flight Data (fallback when Amadeus unavailable)
# ---------------------------------------------------------

class MockFlightData:
    """Generates realistic mock flight data when Amadeus API is unavailable."""

    AIRLINES = [
        {"code": "DL", "name": "Delta Air Lines"},
        {"code": "UA", "name": "United Airlines"},
        {"code": "AA", "name": "American Airlines"},
        {"code": "B6", "name": "JetBlue Airways"},
        {"code": "WN", "name": "Southwest Airlines"},
        {"code": "NK", "name": "Spirit Airlines"},
        {"code": "AS", "name": "Alaska Airlines"},
        {"code": "F9", "name": "Frontier Airlines"},
    ]

    ROUTE_BASE_PRICES = {
        ("JFK", "LAX"): 250, ("LAX", "JFK"): 250,
        ("JFK", "MIA"): 180, ("MIA", "JFK"): 180,
        ("ORD", "LAX"): 200, ("LAX", "ORD"): 200,
        ("JFK", "SFO"): 270, ("SFO", "JFK"): 270,
        ("JFK", "LHR"): 550, ("LHR", "JFK"): 550,
        ("LAX", "NRT"): 700, ("NRT", "LAX"): 700,
        ("JFK", "ORD"): 160, ("ORD", "JFK"): 160,
        ("SFO", "SEA"): 120, ("SEA", "SFO"): 120,
        ("BOS", "MIA"): 190, ("MIA", "BOS"): 190,
        ("ATL", "LAX"): 230, ("LAX", "ATL"): 230,
        ("DFW", "JFK"): 210, ("JFK", "DFW"): 210,
        ("DEL", "BOM"): 80, ("BOM", "DEL"): 80,
        ("DEL", "BLR"): 90, ("BLR", "DEL"): 90,
        ("JFK", "DEL"): 650, ("DEL", "JFK"): 650,
        ("JFK", "DXB"): 600, ("DXB", "JFK"): 600,
    }
    DEFAULT_BASE_PRICE = 220

    @classmethod
    def search(cls, origin: str, destination: str, departure_date: str,
               return_date: str = None, passengers: int = 1) -> List[Dict]:
        """Generate 4-6 mock flight results."""
        seed = hashlib.md5(f"{origin}{destination}{departure_date}".encode()).hexdigest()
        rng = random.Random(seed)

        num_flights = rng.randint(4, 6)
        base_price = cls.ROUTE_BASE_PRICES.get((origin, destination), cls.DEFAULT_BASE_PRICE)

        results = []
        used_times = set()

        for i in range(num_flights):
            airline = rng.choice(cls.AIRLINES)

            dep_hour = rng.choice([6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 18, 20])
            while dep_hour in used_times:
                dep_hour = rng.choice([5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21])
            used_times.add(dep_hour)
            dep_min = rng.choice([0, 15, 30, 45])

            stops = rng.choices([0, 1, 2], weights=[50, 35, 15])[0]
            base_duration_min = rng.randint(150, 360)
            if stops > 0:
                base_duration_min += stops * rng.randint(60, 120)

            dep_dt = datetime.datetime.strptime(departure_date, "%Y-%m-%d").replace(
                hour=dep_hour, minute=dep_min
            )
            arr_dt = dep_dt + datetime.timedelta(minutes=base_duration_min)

            price_multiplier = rng.uniform(0.8, 1.6)
            if stops == 0:
                price_multiplier *= 1.2
            price = round(base_price * price_multiplier * passengers, 2)

            duration_h = base_duration_min // 60
            duration_m = base_duration_min % 60

            results.append({
                "flight_number": f"{airline['code']}{rng.randint(100, 9999)}",
                "airline": airline["name"],
                "origin": origin,
                "destination": destination,
                "departure_time": dep_dt.strftime("%I:%M %p"),
                "arrival_time": arr_dt.strftime("%I:%M %p"),
                "departure_date": departure_date,
                "duration": f"{duration_h}h {duration_m}m",
                "stops": stops,
                "price": price,
                "currency": "USD",
                "passengers": passengers,
                "source": "mock",
            })

        results.sort(key=lambda x: x["price"])
        return results


# ---------------------------------------------------------
# Amadeus API Client
# ---------------------------------------------------------

class AmadeusClient:
    """Client for Amadeus Self-Service Flight Offers Search API (test environment)."""

    TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
    SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token: Optional[str] = None
        self.token_expires: float = 0

    async def _get_token(self) -> str:
        """Obtain or refresh OAuth2 client_credentials token."""
        if self.access_token and datetime.datetime.now().timestamp() < self.token_expires:
            return self.access_token

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.api_secret,
            }
            async with session.post(self.TOKEN_URL, data=data) as resp:
                if resp.status != 200:
                    raise Exception(f"Amadeus token error: {resp.status}")
                body = await resp.json()
                self.access_token = body["access_token"]
                self.token_expires = datetime.datetime.now().timestamp() + body.get("expires_in", 1799) - 60
                return self.access_token

    async def search_flights(self, origin: str, destination: str, departure_date: str,
                             return_date: str = None, adults: int = 1) -> List[Dict]:
        """Search for flight offers. Returns parsed list of flights."""
        token = await self._get_token()

        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "max": 6,
            "currencyCode": "USD",
        }
        if return_date:
            params["returnDate"] = return_date

        headers = {"Authorization": f"Bearer {token}"}
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.SEARCH_URL, params=params, headers=headers) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    raise Exception(f"Amadeus search error {resp.status}: {error_body[:200]}")
                body = await resp.json()
                return self._parse_results(body, adults)

    def _parse_results(self, raw_response: dict, passengers: int) -> List[Dict]:
        """Parse Amadeus API response into simplified flight list."""
        results = []
        carrier_dict = raw_response.get("dictionaries", {}).get("carriers", {})

        for offer in raw_response.get("data", []):
            itinerary = offer["itineraries"][0]
            segments = itinerary["segments"]
            first_seg = segments[0]
            last_seg = segments[-1]

            duration_raw = itinerary.get("duration", "")
            duration_match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration_raw)
            if duration_match:
                h = duration_match.group(1) or "0"
                m = duration_match.group(2) or "0"
                duration_str = f"{h}h {m}m"
            else:
                duration_str = duration_raw

            carrier_code = first_seg.get("carrierCode", "")
            airline_name = carrier_dict.get(carrier_code, carrier_code)
            flight_num = f"{carrier_code}{first_seg.get('number', '')}"

            dep_time_raw = first_seg["departure"]["at"]
            arr_time_raw = last_seg["arrival"]["at"]
            dep_dt = datetime.datetime.fromisoformat(dep_time_raw)
            arr_dt = datetime.datetime.fromisoformat(arr_time_raw)

            price_total = float(offer["price"]["grandTotal"])

            results.append({
                "flight_number": flight_num,
                "airline": airline_name,
                "origin": first_seg["departure"]["iataCode"],
                "destination": last_seg["arrival"]["iataCode"],
                "departure_time": dep_dt.strftime("%I:%M %p"),
                "arrival_time": arr_dt.strftime("%I:%M %p"),
                "departure_date": dep_dt.strftime("%Y-%m-%d"),
                "duration": duration_str,
                "stops": len(segments) - 1,
                "price": price_total,
                "currency": offer["price"].get("currency", "USD"),
                "passengers": passengers,
                "source": "amadeus",
            })

        results.sort(key=lambda x: x["price"])
        return results


# ---------------------------------------------------------
# System Prompt --- Aegis Personality
# ---------------------------------------------------------

AEGIS_SYSTEM_PROMPT = """You are Aegis, an advanced AI assistant. Think of yourself as a sophisticated, capable, and slightly witty personal assistant --- similar in spirit to Jarvis from the Avengers.

The user interacts with you entirely through voice. Your responses will be spoken aloud via text-to-speech.

Your primary specialty is flight search and booking. You can also help with web searches, calculations, and general conversation.

When searching flights:
- Ask for origin city, destination city, and travel date if not provided.
- Present results clearly: number each option, say the airline, departure and arrival times, price, and stops.
- Keep it natural --- describe flights conversationally, do not use tables.

When booking:
- Confirm the flight details before proceeding.
- Call the book_flight tool to complete the booking --- authentication happens automatically.
- After booking, provide the booking reference.

Available tools: search_flights, book_flight, get_booking_status, web_search, calculator, get_current_time

Rules:
- Keep responses SHORT and CONVERSATIONAL --- they will be spoken aloud.
- Avoid markdown, code blocks, bullet lists, or special characters.
- Use natural spoken language. Say numbers as words when appropriate.
- Be helpful, polished, and occasionally witty.
- Address the user respectfully.
- For dates, always convert to YYYY-MM-DD format before calling search_flights.
- If the user says something like "April 15th", convert it to the correct date in the current year."""


# ---------------------------------------------------------
# Audio Manager --- Voice I/O with VAD
# ---------------------------------------------------------

class AudioManager:
    """Handles microphone capture with VAD, Whisper STT, and OpenAI TTS."""

    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = "int16"
    FRAME_DURATION_MS = 30
    SILENCE_DURATION = 1.5
    MAX_RECORD_SECONDS = 30

    def __init__(self, openai_client: OpenAI):
        self.openai = openai_client
        self.vad = webrtcvad.Vad(2)
        self.frame_size = int(self.SAMPLE_RATE * self.FRAME_DURATION_MS / 1000)
        self.frame_bytes = self.frame_size * 2

    def record_until_silence(self) -> Optional[bytes]:
        """
        Continuously listen via microphone. Start recording when speech is
        detected (VAD), stop after SILENCE_DURATION seconds of silence.
        Returns raw PCM bytes (16-bit, 16kHz, mono) or None if no speech.
        """
        print("  [Mic] Listening...")

        frames = []
        speech_detected = False
        silence_frames = 0
        max_frames = int(self.MAX_RECORD_SECONDS * self.SAMPLE_RATE / self.frame_size)
        silence_frame_threshold = int(self.SILENCE_DURATION * 1000 / self.FRAME_DURATION_MS)

        pre_speech_timeout = int(10 * 1000 / self.FRAME_DURATION_MS)
        pre_speech_frames = 0

        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                blocksize=self.frame_size,
            ) as stream:
                for _ in range(max_frames + pre_speech_timeout):
                    data, overflowed = stream.read(self.frame_size)
                    pcm_bytes = data.tobytes()

                    if len(pcm_bytes) != self.frame_bytes:
                        continue

                    is_speech = self.vad.is_speech(pcm_bytes, self.SAMPLE_RATE)

                    if not speech_detected:
                        if is_speech:
                            speech_detected = True
                            frames.append(pcm_bytes)
                            silence_frames = 0
                            print("  [Mic] Speech detected, recording...")
                        else:
                            pre_speech_frames += 1
                            if pre_speech_frames >= pre_speech_timeout:
                                print("  [Mic] No speech detected, timeout.")
                                return None
                    else:
                        frames.append(pcm_bytes)
                        if is_speech:
                            silence_frames = 0
                        else:
                            silence_frames += 1
                            if silence_frames >= silence_frame_threshold:
                                print("  [Mic] Silence detected, done recording.")
                                break

        except sd.PortAudioError as e:
            print(f"  [Mic] ERROR: Microphone not available --- {e}")
            return None

        if not frames:
            return None

        return b"".join(frames)

    def pcm_to_wav(self, pcm_bytes: bytes) -> bytes:
        """Convert raw PCM bytes to WAV format in memory."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    def transcribe(self, pcm_bytes: bytes) -> str:
        """Send audio to OpenAI Whisper API, return transcribed text."""
        wav_bytes = self.pcm_to_wav(pcm_bytes)

        wav_file = io.BytesIO(wav_bytes)
        wav_file.name = "audio.wav"

        try:
            result = self.openai.audio.transcriptions.create(
                model="whisper-1",
                file=wav_file,
                language="en",
            )
            text = result.text.strip()
            print(f'  [STT] "{text}"')
            return text
        except Exception as e:
            print(f"  [STT] ERROR: {e}")
            return ""

    def speak(self, text: str):
        """Convert text to speech via OpenAI TTS API and play through speakers."""
        if not text:
            return

        print(f'  [TTS] Speaking: "{text[:80]}{"..." if len(text) > 80 else ""}"')

        try:
            response = self.openai.audio.speech.create(
                model="tts-1",
                voice="onyx",
                input=text,
                response_format="pcm",
            )

            pcm_data = response.content
            audio_array = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0

            sd.play(audio_array, samplerate=24000, blocksize=1024)
            sd.wait()

        except Exception as e:
            print(f"  [TTS] ERROR: {e}")
            print(f"  Aegis: {text}")


# ---------------------------------------------------------
# CIBA Authenticator --- Mobile Push + TOTP Fallback
# ---------------------------------------------------------

class CIBAAuthenticator:
    """
    Handles user authentication via CIBA mobile push notifications
    with TOTP (6-digit code) fallback, all through voice interaction.

    Uses the AuthSec SDK's CIBAClient:
      - initiate_app_approval(email)  -> sends push notification
      - poll_for_approval(...)        -> waits for user to approve
      - verify_totp(email, code)      -> fallback 6-digit code
    """

    def __init__(self, client_id: str, base_url: str, audio: AudioManager):
        self.ciba = CIBAClient(client_id=client_id, base_url=base_url)
        self.audio = audio
        self.token: Optional[str] = None
        self.user_email: Optional[str] = None

    async def authenticate(self) -> bool:
        """
        Full voice-guided CIBA authentication flow.
        Returns True if user is authenticated, False otherwise.
        """
        self.audio.speak("To complete this booking, I'll need to verify your identity.")

        # Step 1: Get email via voice
        email = await self._get_email_via_voice()
        if not email:
            self.audio.speak("I couldn't get your email address. Please try again later.")
            return False

        self.user_email = email
        self.audio.speak(f"Understood. Sending a verification request to the AuthSec app for {email}.")

        # Step 2: Try CIBA push notification flow
        success = await self._ciba_flow(email)
        if success:
            self.audio.speak("Identity verified. Proceeding with your booking.")
            return True

        # Step 3: Offer TOTP fallback
        self.audio.speak(
            "The push notification wasn't approved. "
            "Would you like to use a 6-digit code instead? Say yes or no."
        )

        pcm = self.audio.record_until_silence()
        if pcm:
            response = self.audio.transcribe(pcm)
            if "yes" in response.lower() or "yeah" in response.lower() or "sure" in response.lower():
                success = await self._totp_fallback(email)
                if success:
                    self.audio.speak("Identity verified. Proceeding with your booking.")
                    return True

        self.audio.speak("Authentication was not completed. The booking has been cancelled.")
        return False

    async def _get_email_via_voice(self, max_attempts: int = 3) -> Optional[str]:
        """Ask the user for their email address via voice, with retries."""
        for attempt in range(max_attempts):
            if attempt == 0:
                self.audio.speak("Please say your email address.")
            else:
                self.audio.speak("I didn't catch that. Please say your email address again.")

            pcm = self.audio.record_until_silence()
            if not pcm:
                continue

            transcription = self.audio.transcribe(pcm)
            if not transcription:
                continue

            email = self._extract_email(transcription)
            if email:
                self.audio.speak(f"I heard {email}. Is that correct? Say yes or no.")
                confirm_pcm = self.audio.record_until_silence()
                if confirm_pcm:
                    confirm = self.audio.transcribe(confirm_pcm)
                    if "yes" in confirm.lower() or "yeah" in confirm.lower() or "correct" in confirm.lower():
                        return email
            else:
                self.audio.speak("That didn't sound like an email address.")

        return None

    def _extract_email(self, transcription: str) -> Optional[str]:
        """
        Extract an email address from spoken text.
        Handles: "john at example dot com" -> john@example.com
        """
        text = transcription.strip().lower()

        match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', text)
        if match:
            return match.group(0)

        text = re.sub(r'\s+at\s+', '@', text)
        text = re.sub(r'\s+dot\s+', '.', text)
        text = re.sub(r'\s+', '', text)

        match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', text)
        if match:
            return match.group(0)

        return None

    async def _ciba_flow(self, email: str) -> bool:
        """
        CIBA push notification flow:
        1. initiate_app_approval(email) -> sends push to user's phone
        2. poll_for_approval(...)       -> waits up to 120s for approval
        """
        try:
            result = self.ciba.initiate_app_approval(email)
            auth_req_id = result["auth_req_id"]
        except Exception as e:
            print(f"  [CIBA] ERROR initiating approval: {e}")
            self.audio.speak("I couldn't send the notification. There was an error.")
            return False

        self.audio.speak("A notification has been sent to your phone. Please approve it.")

        poll_result = {"status": None, "token": None}
        poll_done = threading.Event()

        def poll_thread():
            try:
                approval = self.ciba.poll_for_approval(
                    email=email,
                    auth_req_id=auth_req_id,
                    interval=5,
                    timeout=120,
                )
                poll_result["status"] = approval.get("status")
                poll_result["token"] = approval.get("token")
            except Exception as e:
                print(f"  [CIBA] Poll error: {e}")
                poll_result["status"] = "error"
            finally:
                poll_done.set()

        thread = threading.Thread(target=poll_thread, daemon=True)
        thread.start()

        update_interval = 15
        elapsed = 0
        while not poll_done.is_set():
            poll_done.wait(timeout=update_interval)
            elapsed += update_interval
            if not poll_done.is_set() and elapsed < 120:
                self.audio.speak("Still waiting for your approval...")

        if poll_result["status"] == "approved" and poll_result["token"]:
            self.token = poll_result["token"]
            print("  [CIBA] User approved! Token received.")
            return True
        else:
            print(f"  [CIBA] Authentication failed: {poll_result['status']}")
            return False

    async def _totp_fallback(self, email: str, max_attempts: int = 3) -> bool:
        """Voice-guided TOTP code entry with retries."""
        for attempt in range(max_attempts):
            if attempt == 0:
                self.audio.speak("Please tell me your 6-digit authentication code.")
            else:
                self.audio.speak("Please try again. Tell me your 6-digit code.")

            pcm = self.audio.record_until_silence()
            if not pcm:
                continue

            transcription = self.audio.transcribe(pcm)
            if not transcription:
                continue

            code = self._extract_digits(transcription)
            if not code or len(code) != 6:
                self.audio.speak("I need exactly 6 digits. Please try again.")
                continue

            try:
                result = self.ciba.verify_totp(email, code)
                if result.get("success"):
                    self.token = result["token"]
                    print("  [TOTP] Verified! Token received.")
                    return True
                else:
                    remaining = result.get("remaining", 0)
                    error = result.get("error", "invalid_code")
                    if error == "too_many_retries" or remaining == 0:
                        self.audio.speak("Too many failed attempts. Please try again later.")
                        return False
                    self.audio.speak(
                        f"That code was incorrect. You have {remaining} attempts remaining."
                    )
            except Exception as e:
                print(f"  [TOTP] ERROR: {e}")
                self.audio.speak("There was an error verifying your code.")

        return False

    def _extract_digits(self, transcription: str) -> str:
        """Extract digits from transcription. Handles spoken numbers."""
        text = transcription.strip().lower()

        word_to_digit = {
            "zero": "0", "oh": "0", "o": "0",
            "one": "1", "two": "2", "to": "2", "too": "2",
            "three": "3", "four": "4", "for": "4",
            "five": "5", "six": "6", "seven": "7",
            "eight": "8", "ate": "8", "nine": "9",
        }

        digits = []
        for word in text.split():
            if word in word_to_digit:
                digits.append(word_to_digit[word])
            else:
                for ch in word:
                    if ch.isdigit():
                        digits.append(ch)

        return "".join(digits)


# ---------------------------------------------------------
# Aegis --- Main Voice Agent
# ---------------------------------------------------------

class VoiceAgent:
    """
    Aegis --- Jarvis-like voice AI assistant for flight booking.
    Uses Amadeus API for flight search with mock data fallback.
    CIBA authentication triggered only at booking time.
    """

    def __init__(self, client_id: str, ciba_base_url: str):
        self.client_id = client_id
        self.openai = OpenAI()
        self.audio = AudioManager(self.openai)
        self.ciba_auth = CIBAAuthenticator(client_id, ciba_base_url, self.audio)
        self.messages: list = []
        self.active_tools = AEGIS_TOOLS

        # Flight data sources
        if AMADEUS_API_KEY and AMADEUS_API_SECRET:
            self.amadeus = AmadeusClient(AMADEUS_API_KEY, AMADEUS_API_SECRET)
            print("[Aegis] Amadeus API configured (live flight data)")
        else:
            self.amadeus = None
            print("[Aegis] No Amadeus credentials --- using mock flight data")

        # State
        self.last_search_results: List[Dict] = []
        self.bookings: List[Dict] = []

    async def initialize(self):
        """Set up system prompt and speak greeting. NO authentication here."""
        self.messages = [
            {"role": "system", "content": AEGIS_SYSTEM_PROMPT}
        ]

        self.audio.speak(
            "Good day. I'm Aegis, your personal AI assistant. "
            "I can help you search and book flights, look up information on the web, "
            "perform calculations, and more. How may I assist you?"
        )

    # -------------------------------------------------
    # Tool Executors
    # -------------------------------------------------

    async def execute_tool(self, name: str, args: dict) -> str:
        """Route tool call to the correct executor."""
        executors = {
            "search_flights": self._exec_search_flights,
            "book_flight": self._exec_book_flight,
            "get_booking_status": self._exec_get_booking_status,
            "web_search": self._exec_web_search,
            "calculator": self._exec_calculator,
            "get_current_time": self._exec_get_current_time,
        }
        executor = executors.get(name)
        if not executor:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            return await executor(args)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _exec_search_flights(self, args: dict) -> str:
        """Search flights via Amadeus API with mock data fallback."""
        origin = resolve_airport_code(args["origin"])
        destination = resolve_airport_code(args["destination"])
        departure_date = args["departure_date"]
        return_date = args.get("return_date")
        passengers = args.get("passengers", 1)

        results = None

        if self.amadeus:
            try:
                results = await self.amadeus.search_flights(
                    origin, destination, departure_date, return_date, passengers
                )
                print(f"  [Amadeus] Found {len(results)} flights")
            except Exception as e:
                print(f"  [Amadeus] API error, falling back to mock data: {e}")

        if not results:
            results = MockFlightData.search(origin, destination, departure_date, return_date, passengers)
            print(f"  [Mock] Generated {len(results)} flights")

        self.last_search_results = results

        formatted = []
        for i, flight in enumerate(results, 1):
            stops_str = "nonstop" if flight["stops"] == 0 else f"{flight['stops']} stop{'s' if flight['stops'] > 1 else ''}"
            formatted.append({
                "option": i,
                "airline": flight["airline"],
                "flight_number": flight["flight_number"],
                "departure": flight["departure_time"],
                "arrival": flight["arrival_time"],
                "duration": flight["duration"],
                "stops": stops_str,
                "price": f"${flight['price']:.2f}",
            })

        return json.dumps({
            "route": f"{origin} -> {destination}",
            "date": departure_date,
            "passengers": passengers,
            "flights": formatted,
        }, indent=2)

    async def _exec_book_flight(self, args: dict) -> str:
        """Book a flight from search results. Triggers CIBA auth if needed."""
        flight_idx_str = args["flight_number"]

        try:
            flight_idx = int(flight_idx_str) - 1
        except ValueError:
            return json.dumps({"error": "Please provide a valid flight number (e.g. 1, 2, 3)"})

        if not self.last_search_results:
            return json.dumps({"error": "No search results available. Please search for flights first."})

        if flight_idx < 0 or flight_idx >= len(self.last_search_results):
            return json.dumps({
                "error": f"Invalid flight number. Please choose between 1 and {len(self.last_search_results)}."
            })

        flight = self.last_search_results[flight_idx]

        # Trigger CIBA authentication if not yet authenticated
        if not self.ciba_auth.token:
            self.audio.speak(
                f"Before I can book this flight, I need to verify your identity. "
                f"This is a one-time step for this session."
            )
            authenticated = await self.ciba_auth.authenticate()
            if not authenticated:
                return json.dumps({
                    "error": "Authentication failed. Unable to complete booking. You can try again."
                })

        # Generate booking reference
        ref_seed = f"{flight['flight_number']}{datetime.datetime.now().isoformat()}{random.randint(0, 9999)}"
        booking_ref = hashlib.md5(ref_seed.encode()).hexdigest()[:8].upper()

        booking = {
            "booking_reference": booking_ref,
            "status": "confirmed",
            "flight": flight,
            "passenger_email": self.ciba_auth.user_email,
            "booked_at": datetime.datetime.now().isoformat(),
        }
        self.bookings.append(booking)

        return json.dumps({
            "success": True,
            "booking_reference": booking_ref,
            "airline": flight["airline"],
            "flight_number": flight["flight_number"],
            "route": f"{flight['origin']} -> {flight['destination']}",
            "departure": f"{flight['departure_date']} at {flight['departure_time']}",
            "arrival": flight["arrival_time"],
            "price": f"${flight['price']:.2f}",
            "passenger": self.ciba_auth.user_email,
            "status": "confirmed",
        }, indent=2)

    async def _exec_get_booking_status(self, args: dict) -> str:
        """Check booking status by reference or list all bookings."""
        ref = args.get("booking_reference")

        if ref:
            for booking in self.bookings:
                if booking["booking_reference"] == ref.upper():
                    return json.dumps(booking, indent=2, default=str)
            return json.dumps({"error": f"Booking {ref} not found."})

        if not self.bookings:
            return json.dumps({"message": "No bookings found for this session."})

        summary = []
        for b in self.bookings:
            summary.append({
                "reference": b["booking_reference"],
                "flight": b["flight"]["flight_number"],
                "route": f"{b['flight']['origin']} -> {b['flight']['destination']}",
                "date": b["flight"]["departure_date"],
                "status": b["status"],
            })
        return json.dumps({"bookings": summary}, indent=2)

    async def _exec_web_search(self, args: dict) -> str:
        """Search the web via DuckDuckGo."""
        query = args["query"]
        max_results = args.get("max_results", 5)
        url = f"https://html.duckduckgo.com/html/?q={query}"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers={"User-Agent": "Aegis-VoiceAgent/1.0"}) as resp:
                html = await resp.text()
        results = []
        links = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html)
        snippets = re.findall(r'class="result__snippet">(.*?)</(?:td|span|a)', html, re.DOTALL)
        for i, (link, title) in enumerate(links[:max_results]):
            snippet = snippets[i].strip() if i < len(snippets) else ""
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            title = re.sub(r"<[^>]+>", "", title).strip()
            results.append({"title": title, "url": link, "snippet": snippet[:200]})
        return json.dumps({"query": query, "results": results}, indent=2)[:4000]

    async def _exec_calculator(self, args: dict) -> str:
        """Evaluate a math expression safely."""
        expr = args["expression"]
        allowed = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "len": len, "int": int, "float": float,
            "pow": pow, "divmod": divmod,
            **{k: getattr(math, k) for k in dir(math) if not k.startswith("_")},
        }
        try:
            result = eval(expr, {"__builtins__": {}}, allowed)
            return json.dumps({"expression": expr, "result": result})
        except Exception as e:
            return json.dumps({"expression": expr, "error": str(e)})

    async def _exec_get_current_time(self, args: dict) -> str:
        """Return current date and time."""
        now = datetime.datetime.now()
        return json.dumps({
            "date": now.strftime("%A, %B %d, %Y"),
            "time": now.strftime("%I:%M %p"),
            "timezone": "local",
        })

    # -------------------------------------------------
    # Chat & Voice Loop
    # -------------------------------------------------

    async def chat(self, user_input: str) -> str:
        """Process user message, call tools if needed, return response."""
        self.messages.append({"role": "user", "content": user_input})

        kwargs = {"model": "gpt-4o-mini", "messages": self.messages}
        if self.active_tools:
            kwargs["tools"] = self.active_tools
            kwargs["tool_choice"] = "auto"

        response = self.openai.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        while msg.tool_calls:
            self.messages.append(msg)
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments or "{}")
                print(f"  [Tool] {fn_name}({json.dumps(fn_args)[:100]})")
                result = await self.execute_tool(fn_name, fn_args)
                print(f"  [Result] {result[:150]}{'...' if len(result) > 150 else ''}")
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

            response = self.openai.chat.completions.create(**kwargs)
            msg = response.choices[0].message

        self.messages.append({"role": "assistant", "content": msg.content})
        return msg.content

    async def run(self):
        """Main voice interaction loop: listen -> transcribe -> chat -> speak."""
        while True:
            try:
                pcm = self.audio.record_until_silence()
                if pcm is None:
                    continue

                text = self.audio.transcribe(pcm)
                if not text:
                    continue

                lower = text.lower().strip()
                if lower in ("quit", "exit", "goodbye", "bye", "stop", "shut down"):
                    self.audio.speak("Goodbye. It was a pleasure assisting you.")
                    break

                print(f"\n  You (voice): {text}")
                response = await self.chat(text)
                print(f"  Aegis: {response}\n")

                self.audio.speak(response)

            except KeyboardInterrupt:
                self.audio.speak("Session ended. Until next time.")
                break
            except Exception as e:
                print(f"\n  [Error] {e}\n")
                self.audio.speak("My apologies, something went wrong. Please try again.")


# ---------------------------------------------------------
# Entry Point
# ---------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(
        description="Aegis --- Jarvis-like Voice AI Assistant for Flight Booking"
    )
    parser.add_argument("--client-id", default=None,
                        help="Client ID for CIBA auth (or set CLIENT_ID env var)")
    parser.add_argument("--ciba-base-url", default=None,
                        help="CIBA base URL (or set CIBA_BASE_URL env var)")
    args = parser.parse_args()

    client_id = args.client_id or CLIENT_ID
    ciba_base_url = args.ciba_base_url or CIBA_BASE_URL

    if not client_id:
        print("ERROR: No client_id found.")
        print()
        print("  Fix this by running one of:")
        print("    1. authsec init                          # creates .authsec.json (recommended)")
        print("    2. export CLIENT_ID=your-client-id-here  # env var")
        print("    3. python voice_agent.py --client-id ... # CLI flag")
        sys.exit(1)

    print(f"[Config] client_id:       {client_id}")
    print(f"[Config] ciba_base_url:   {ciba_base_url}")
    print(f"[Config] amadeus_api_key: {'configured' if AMADEUS_API_KEY else 'not set (mock mode)'}")

    agent = VoiceAgent(
        client_id=client_id,
        ciba_base_url=ciba_base_url,
    )

    await agent.initialize()

    print("\n" + "=" * 60)
    print("  AEGIS --- Flight Booking Voice Assistant")
    print("=" * 60)
    print(f"  Flight data: {'Amadeus API' if agent.amadeus else 'Mock data'}")
    print(f"  Auth: CIBA push notification (triggered at booking time)")
    print(f"  Tools: {[t['function']['name'] for t in agent.active_tools]}")
    print(f"  Say 'goodbye' to exit")
    print("=" * 60 + "\n")

    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
