from __future__ import annotations

import argparse
import asyncio
import base64
from contextvars import ContextVar, Token
from datetime import datetime, timezone, timedelta
from functools import lru_cache
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import struct
from typing import Any

import aiohttp
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    import brotli
except ImportError:
    brotli = None

from Crypto.Cipher import AES

# ==========================================
# CONFIGURATION
# ==========================================
API_TOKEN = "8871310106:AAEppR6b_XgKjZnECpQGJJ0Ax1gYUnMNBNk"  # Replace with your Telegram Bot Token
ADMIN_ID = 8296992233 # Admin Telegram User ID
ADMIN_USERNAME = "@meow98989898"
SUBSCRIPTIONS_FILE = "subscriptions.json"
USER_IDS_FILE = "known_users.json"

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")
user_sessions: dict[int, dict[str, Any]] = {}
logging.basicConfig(level=logging.INFO)

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def load_known_users() -> set[int]:
    try:
        with open(USER_IDS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {int(uid) for uid in raw if str(uid).isdigit()}
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def save_known_user(user_id: int) -> None:
    users = load_known_users()
    users.add(int(user_id))
    try:
        with open(USER_IDS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(users), f, indent=2)
    except OSError:
        logging.exception("Could not save known user")


# ==========================================
# INTEGRATED CAR DATABASE (mobil.txt)
# ==========================================
MOBIL_CARS: dict[int, str] = {
    1: "Bmw 1 Series F20",
    2: "Volkswagen Scirocco R",
    3: "Bmw M5 F10",
    4: "Mercedes Benz G65 AMG",
    5: "Chevrolet Camaro Chevy",
    6: "GT86",
    7: "Lexus LFA",
    8: "Infinity G37 Sport Coupe",
    9: "Subaru Impreza 2011 WRX STI",
    10: "Ferrari F12 Berlinetta",
    11: "Nissan Skyline R34 GTR",
    12: "Mitsubshi Lancer Evo X GSR",
    13: "Honda Civic Ek9",
    14: "Nissan Skyline R35 GTR",
    15: "Audi RS4 Avant",
    17: "Mercedes Benz C63 AMG",
    18: "Lamborghini Huracán",
    19: "Mercedes Benz AMG GT3 GTR",
    20: "Audi TT RS",
    21: "Jeep Wrangler",
    22: "Bmw m6 Coupe",
    23: "Peugeot",
    24: "Porsche Panamera 970",
    27: "Bugatti Veyron",
    28: "Porsche Cayenne",
    29: "Honda Civic Type R Euro",
    30: "Bmw E39 M5",
    31: "Bmw M5 E60",
    32: "Koenigsegg Agera RS",
    35: "Ford Mustang S197",
    37: "Mini Van",
    39: "Dodge Charger R/T 1970",
    40: "Chevrolet Corvette C7",
    41: "McLaren P1",
    42: "Lamborghini Aventador",
    43: "Lexus GS 350",
    44: "Lamborghini Veneno",
    45: "Bmw E34",
    47: "Honda S2000",
    48: "Mazda",
    49: "Toyota Supra Mk4",
    51: "Ferrari 250 GT California Spyder",
    53: "Nissan Skyline Hardtop 2000 GTR Kpg610",
    54: "Bmw M5 E28",
    55: "Hummer H1 4 Door Wagon",
    56: "Bmw E92 M3",
    57: "Cadillac CTS",
    58: "Ferrari 458 Italia",
    59: "Smart Fortwo",
    60: "Cadillac Escalade ESV Platinum",
    61: "Mercedes Benz W221",
    62: "Dodge Charger",
    65: "Lamborghini Gallardo LP560-4 Spyder",
    66: "Chrysler 300c",
    70: "Truck",
    74: "Peugeot 308",
    76: "Bmw Z4 E89",
    77: "Mini John Cooper Works",
    81: "Subaru Impreza 2006 WRX STI",
    82: "Mitsubishi Lancer Evo IX",
    85: "Ford F150 SVT Raptor",
    86: "Bmw X5 M",
    87: "Mercedes Benz CL 65 AMG",
    88: "Bmw M3 GTR",
    89: "Hudson Hornet",
    99: "Vaz Lada Priora",
    100: "Vaz Tofas Dogan Tofas Kartal",
    101: "Tow Truck",
    102: "Vaz 2114",
    103: "Bmw M4 Coupe F82",
    104: "BMW M5 F90",
    105: "Dodge Challenger SRT Demon",
    106: "Mercedes Benz 190 E 26 16 Evo II",
    107: "Audi R8 Type 42",
    108: "Audi Quattro",
    109: "Porsche 911 Carrera S 2012",
    110: "Land Rover Sport",
    111: "Honda NSX/Acura NSX",
    112: "Mercedes Benz W140",
    113: "Volkswagen Golf 7",
    114: "Mercedes AMG E63",
    115: "Audi R8 Coupe V10",
    116: "Ford Mustang Shelby GT500",
    117: "Audi S5 Sportback",
    118: "Bmw X6 F16",
    119: "Jeep thing",
    120: "Toyota Camry",
    121: "Toyota Land Cruiser",
    123: "Mercedes Benz GLE 450",
    124: "Rolls Royce Dawn",
    125: "Lamborghini Urus",
    126: "GMC Sierra 1500 Denali",
    127: "Bmw M2",
    128: "Nissan Silvia S15",
    129: "Mazda RX7",
    130: "Ford GT40 MK1",
    131: "Nissan 180 SX",
    132: "Lada Riva Vaz 2105",
    133: "Perodua Myvi",
    134: "Toyota Mark 2",
    135: "Audi RS6 Avant",
    136: "Mercedes Benz AMG S65/W222",
    137: "Honda Civic FD",
    138: "BMW i8",
    139: "Ford Crown Victoria LX",
    140: "Toyota AE86 Trueno",
    141: "Dodge Viper ZB1",
    142: "Mercedes AMG GT63",
    143: "Mercedes Benz AMG G65",
    144: "BMW M850i",
    145: "Nissan 350Z",
    146: "Mercedes AMG GT 43",
    147: "Honda Civic Type R FK8",
    148: "Ford Mustang Boss 302",
    149: "NSX",
    150: "2024 GR Supra",
    151: "Toyota Vellfire",
    152: "Vaz Tofas Kartal",
    153: "BMW M4 G82 Coupe",
    154: "Toyota Hilux",
    155: "F1 McLaren MP4/8",
    156: "Nissan Skyline R32 GTR",
    157: "Volkswagen Golf GTI Mk2",
    158: "Mazda MX-5 Miata",
    159: "Lamborghini Aventador SVJ",
    160: "Dodge Challenger 1960",
    161: "Dodge Jeep Grand Cherokee 2021",
    162: "McLaren 720S",
    163: "Mercedes Benz 280 SL",
    164: "Beach Buggy",
    165: "F1 Formula 1 2022",
    166: "Chevrolet Corvette C6",
    167: "Truck",
    168: "Ford Explorer",
    169: "Bentley Continental GT",
    170: "Truck",
    171: "Yellow Big Truck",
    172: "Rolls Royce Cullinan SUV",
    173: "Mercedes",
    175: "Mercedes Benz E32 1999",
    176: "Chevrolet Silverado C10",
    177: "Nissan Silvia S13",
    178: "Bugatti Chiron",
    179: "Dodge Diplomat",
    180: "Ford F100 1973",
    181: "Ford Mustang 1964",
    182: "Ken Block Truck",
    183: "Ford Mustang 1965",
    184: "Mitsubishi Eclipse",
    185: "Chevrolet Impala 1967",
    186: "Chevrolet Astro 1999",
    187: "Mazda MX-5 NA Miata",
    188: "Porsche 922 GT3 RS",
    189: "Ford F150 Raptor R 2023",
    190: "Peugeot 406 D9",
    191: "Blue Bus",
    192: "Dodge Ram TRX",
    193: "BMW M3 G81 Touring",
    194: "Mercedes Benz SLR McLaren",
    195: "Green Bus",
    196: "Ford Falcon XB GT",
    197: "Volkswagen Type 2",
    198: "Koenigsegg Jesko",
    199: "Chevrolet Corvette C8",
    200: "Dodge Red Trackhawk SRT 2019 AWD",
    201: "Mercedes Benz CLK GTR",
    202: "Pagani Zonda",
    203: "BMW Drag",
    204: "White Minivan",
    205: "Porsche 993",
    206: "Alfa Romeo Giulia",
    207: "Porsche 919 Hybrid",
    208: "Ford Bronco",
    209: "Lexus IS Type F",
    210: "GT Spirit Chevrolet Corvette C3",
    211: "Audi RS7",
    212: "Mercedes AMG G63 6x6",
    213: "Nissan Skyline GTR R33",
    214: "Toyota Chaser",
    215: "Chevrolet Tahoe",
    216: "McLaren Senna",
    217: "BMW X7",
    218: "Toyota Crown",
    219: "Volkswagen Passat",
    220: "1970 Nissan Fairlady Z -240Z",
    221: "Honda NSX 90",
    222: "Porsche 918",
    223: "DMC DeLorean",
    224: "Subaru WRX STI",
    225: "Honda CRX Del Sol",
    226: "Fiat Doblo",
    227: "Mercedes AMG One",
    228: "Audi RS2",
    229: "Ferrari F40",
    230: "Land Rover Defender",
    231: "Land Cruiser J80",
    232: "KIA Stinger",
    233: "BMW I7",
    234: "2023 Aston Martin Vantage",
    235: "Mustang",
    236: "Mobile Home",
    237: "Big Truck",
    238: "2024 BMW M5 G90",
    239: "2021 Cadillac Escalade",
    240: "2009 Ford Focus",
    241: "LaFerrari",
    242: "2016 Chevrolet Camaro",
    243: "Jeep",
    244: "Land Rover New",
    245: "Toyota GR",
    249: "New Mercedes Maybach",
    250: "Porsche Carrera GT",
    251: "New Yellow Car",
    252: "Green BMW",
    254: "New Red Car",
    255: "Blue Paid Car",
    257: "New BMW",
    262: "Toyota Celica",
    263: "Old School",
    266: "Maserati",
}


# ==========================================
# SUBSCRIPTION MANAGEMENT SYSTEM
# ==========================================
def load_subscriptions() -> dict[str, str]:
    if os.path.exists(SUBSCRIPTIONS_FILE):
        try:
            with open(SUBSCRIPTIONS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_subscriptions(subs: dict[str, str]) -> None:
    with open(SUBSCRIPTIONS_FILE, "w") as f:
        json.dump(subs, f, indent=2)


def add_subscription(user_id: int, days: int) -> datetime:
    subs = load_subscriptions()
    now = datetime.now(timezone.utc)
    current_expiry_str = subs.get(str(user_id))
    
    if current_expiry_str:
        try:
            current_expiry = datetime.fromisoformat(current_expiry_str)
            base_time = current_expiry if current_expiry > now else now
        except Exception:
            base_time = now
    else:
        base_time = now

    new_expiry = base_time + timedelta(days=days)
    subs[str(user_id)] = new_expiry.isoformat()
    save_subscriptions(subs)
    return new_expiry


def remove_subscription(user_id: int) -> bool:
    subs = load_subscriptions()
    if str(user_id) in subs:
        del subs[str(user_id)]
        save_subscriptions(subs)
        return True
    return False


def check_subscription(user_id: int) -> tuple[bool, str]:
    if is_admin(user_id):
        return True, "Lifetime (Admin Access)"
    subs = load_subscriptions()
    exp_str = subs.get(str(user_id))
    if not exp_str:
        return False, "No active subscription"
    try:
        exp_date = datetime.fromisoformat(exp_str)
        now = datetime.now(timezone.utc)
        if exp_date > now:
            remaining = exp_date - now
            days = remaining.days
            hours = remaining.seconds // 3600
            return True, f"{days} days and {hours} hours remaining (Valid until {exp_date.strftime('%Y-%m-%d %H:%M UTC')})"
        else:
            return False, f"Expired on {exp_date.strftime('%Y-%m-%d %H:%M UTC')}"
    except Exception:
        return False, "Invalid subscription record"


# ==========================================
# CPM CONSTANTS & UTILITIES
# ==========================================
CPM1_API_KEY = os.getenv("CPM1_API_KEY", "AIzaSyBW1ZbMiUeDZHYUO2bY8Bfnf5rRgrQGPTM").strip()
CPM2_API_KEY = os.getenv("CPM2_API_KEY", "AIzaSyCQDz9rgjgmvmFkvVfmvr2-7fT4tfrzRRQ").strip()
CPM1_DATABASE_URL = os.getenv(
    "CPM1_DATABASE_URL",
    "https://carparkingmultiplayer-dc1d2.firebaseio.com",
).rstrip("/")
CPM1_API_BASE = os.getenv(
    "CPM1_API_BASE",
    "https://us-central1-carparkingmultiplayer-dc1d2.cloudfunctions.net",
).rstrip("/")
CPM2_API_BASE = os.getenv(
    "CPM2_API_BASE",
    "https://europe-west1-cpm-2-7cea1.cloudfunctions.net",
).rstrip("/")

CPM1_UNSUPPORTED_CLOUD_ERROR = "CPM1_CLOUD_UNSUPPORTED_OR_NEW_FORMAT"
CPM1_CARS_FUNCTION = "GetAllCars2"
CPM1_FALLBACK_BASES = (
    "https://europe-west1-cp-multiplayer.cloudfunctions.net",
    "https://us-central1-cp-multiplayer.cloudfunctions.net",
)
CPM2_CARS_FUNCTION_CANDIDATES = (
    "GetAllCars24_1",
    "GetAllCars22_1",
    "GetAllCars21_1",
    "GetAllCars20_2",
)
CPM2_SAVE_CAR_FUNCTION = "SaveCar24_1"

_cars_function_name: str | None = None
_cars_function_lock = asyncio.Lock()
_balance_http_session: ContextVar[aiohttp.ClientSession | None] = ContextVar(
    "balance_http_session",
    default=None,
)


def set_balance_http_session(session: aiohttp.ClientSession) -> Token:
    return _balance_http_session.set(session)


def reset_balance_http_session(token: Token) -> None:
    _balance_http_session.reset(token)


@lru_cache(maxsize=1)
def _load_car_names() -> dict[str, str]:
    result = {str(k): v for k, v in MOBIL_CARS.items()}
    return result


def send_chunked_messages(chat_id: int, text: str) -> None:
    max_length = 3800
    lines = text.split("\n")
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > max_length:
            bot.send_message(chat_id, chunk, parse_mode="HTML")
            chunk = ""
        chunk += line + "\n"
    if chunk.strip():
        bot.send_message(chat_id, chunk, parse_mode="HTML")


def make_progress_bar(current: int, total: int, length: int = 10) -> str:
    percent = current / total if total > 0 else 0
    filled = int(round(length * percent))
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {current}/{total} ({int(percent * 100)}%)"


async def firebase_verify_password(
    email: str,
    password: str,
    *,
    api_key: str,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    if not api_key:
        return {"error": {"message": "FIREBASE_API_KEY_NOT_CONFIGURED"}}
    url = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={api_key}"

    async def request(http_session: aiohttp.ClientSession) -> dict[str, Any]:
        try:
            async with http_session.post(
                url,
                json={"email": email, "password": password, "returnSecureToken": True},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                try:
                    data = await response.json(content_type=None)
                except Exception:
                    return {"error": {"message": "SERVICE_UNAVAILABLE", "transient": True}}
                if response.status == 429 or response.status >= 500:
                    return {"error": {"message": "SERVICE_UNAVAILABLE", "transient": True}}
                return data
        except Exception:
            return {"error": {"message": "CONNECTION_ERROR", "transient": True}}

    if session is not None:
        return await request(session)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as own_session:
        return await request(own_session)


async def firebase_verify_cpm1_password(email: str, password: str) -> dict[str, Any]:
    """Authenticate a CPM1 account with both supported Firebase REST routes.

    Some older Firebase projects still use the v3 relying-party route, while
    newer projects use the v1 accounts:signInWithPassword route. Try the v1
    route first, then the legacy route for compatibility. This does not bypass
    Firebase authentication: if both routes reject the credentials, the bot
    returns the actual Firebase error rather than pretending login succeeded.
    """
    if not CPM1_API_KEY:
        return {"error": {"message": "FIREBASE_API_KEY_NOT_CONFIGURED"}}

    email = str(email or "").strip()
    if not email or not password:
        return {"error": {"message": "MISSING_EMAIL_OR_PASSWORD"}}

    urls = (
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={CPM1_API_KEY}",
        f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={CPM1_API_KEY}",
    )
    payload = {"email": email, "password": password, "returnSecureToken": True}
    timeout = aiohttp.ClientTimeout(total=12)
    last_error: dict[str, Any] = {"message": "CPM1_AUTH_FAILED"}

    async with aiohttp.ClientSession(timeout=timeout) as http_session:
        for url in urls:
            try:
                async with http_session.post(url, json=payload, timeout=timeout) as response:
                    try:
                        data = await response.json(content_type=None)
                    except Exception:
                        last_error = {"message": "CPM1_AUTH_INVALID_RESPONSE", "transient": True}
                        continue

                    if response.status == 429 or response.status >= 500:
                        last_error = {"message": "CPM1_AUTH_SERVICE_UNAVAILABLE", "transient": True}
                        continue

                    if isinstance(data, dict) and data.get("idToken") and data.get("localId"):
                        return data

                    err = data.get("error") if isinstance(data, dict) else None
                    if isinstance(err, dict):
                        message = str(err.get("message") or "CPM1_AUTH_FAILED")
                    else:
                        message = f"CPM1_AUTH_HTTP_{response.status}" if response.status >= 400 else "CPM1_AUTH_INVALID_RESPONSE"
                    last_error = {"message": message, "status": response.status}

                    # If Firebase says the key/project is invalid, trying the
                    # second URL with the same key cannot help; surface it clearly.
                    if message in {"API_KEY_INVALID", "PROJECT_NOT_FOUND", "OPERATION_NOT_ALLOWED"}:
                        break
            except (aiohttp.ClientError, asyncio.TimeoutError):
                last_error = {"message": "CPM1_AUTH_CONNECTION_ERROR", "transient": True}
                continue

    return {"error": last_error}


async def firebase_verify_cpm2_password(
    email: str,
    password: str,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    return await firebase_verify_password(email, password, api_key=CPM2_API_KEY, session=session)


def _cpm1_function_bases() -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for raw_base in (CPM1_API_BASE, *CPM1_FALLBACK_BASES):
        base = str(raw_base or "").strip().rstrip("/")
        if base and base not in seen:
            seen.add(base)
            result.append(base)
    return tuple(result)


def _derive_key_iv(local_id: str) -> tuple[bytes | None, bytes | None]:
    if not local_id:
        return None, None
    prefix = local_id[:8]
    raw = (prefix + "12345678").encode("utf-8")[:16]
    return raw, raw


def _encrypt_value(value: str, local_id: str) -> str | None:
    key, iv = _derive_key_iv(local_id)
    if not key or not iv:
        return None
    raw = value.encode("utf-8")
    padding = 16 - len(raw) % 16
    raw += bytes([padding]) * padding
    encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(raw)
    return base64.b64encode(encrypted).decode("utf-8")


def _json_unwrap(value: Any) -> Any:
    current = value
    for _ in range(4):
        if not isinstance(current, str):
            break
        try:
            current = json.loads(current)
        except (TypeError, ValueError):
            break
    return current


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _uint32_value(value: Any) -> int:
    return _int_value(value) & 0xFFFFFFFF


def _int64_value(value: Any) -> int:
    number = _int_value(value)
    if number > 0x7FFFFFFFFFFFFFFF:
        number -= 0x10000000000000000
    if number < -0x8000000000000000:
        number = -0x8000000000000000
    return number


def _memorypack_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if not encoded:
        return struct.pack("<i", 0)
    return struct.pack("<ii", ~len(encoded), len(value)) + encoded


def _vector3(value: Any) -> tuple[float, float, float]:
    if not isinstance(value, dict):
        return 0.0, 0.0, 0.0
    return (
        _float_value(value.get("x", value.get("X"))),
        _float_value(value.get("y", value.get("Y"))),
        _float_value(value.get("z", value.get("Z"))),
    )


def _serialize_vinyl_item(item: dict[str, Any]) -> bytes:
    position = _vector3(item.get("position"))
    scale_rotation = _vector3(item.get("scaleRotation", item.get("scale_rotation")))
    icon_position = _vector3(item.get("iconPosition", item.get("icon_position")))
    text = str(item.get("text") or "")
    color = _uint32_value(item.get("color"))
    packed_data = _int64_value(item.get("packedData"))
    return (
        b"\x06"
        + struct.pack("<9f", *position, *scale_rotation, *icon_position)
        + _memorypack_string(text)
        + struct.pack("<Iq", color, packed_data)
    )


def _serialize_vinyl_list(items: list[dict[str, Any]]) -> bytes:
    return struct.pack("<i", len(items)) + b"".join(_serialize_vinyl_item(item) for item in items)


def _extract_vinyl_items(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("allVynils"), list):
        return [item for item in value["allVynils"] if isinstance(item, dict)]
    if isinstance(value.get("oneVynil"), list):
        return [item for item in value["oneVynil"] if isinstance(item, dict)]
    if {"position", "scaleRotation", "iconPosition"} & set(value):
        return [value]
    return None


def _brotli_decompress(payload: bytes) -> bytes | None:
    if brotli is None:
        return None
    try:
        return brotli.decompress(payload)
    except Exception:
        return None


def _extract_vinyl_raw_candidate(payload: bytes) -> tuple[bytes, int] | None:
    direct = _read_memorypack_vinyl_list(payload, 0, len(payload))
    if direct is not None and direct[0] == len(payload):
        return payload, direct[1]
    if not payload:
        return None
    wrapped = _read_memorypack_vinyl_list(payload, 1, len(payload))
    if wrapped is None:
        return None
    remainder = len(payload) - wrapped[0]
    if remainder in (0, 4):
        return payload[1:wrapped[0]], wrapped[1]
    return None


def _normalize_cpm1_vinyl_field(value: Any) -> tuple[bytes, int] | None:
    items = _extract_vinyl_items(value)
    if items is not None:
        return _serialize_vinyl_list(items), len(items)
    if value in (None, "", []):
        return _serialize_vinyl_list([]), 0
    if not isinstance(value, str):
        return None
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception:
        return None
    for candidate in (decoded, _brotli_decompress(decoded)):
        if not isinstance(candidate, (bytes, bytearray)):
            continue
        parsed = _extract_vinyl_raw_candidate(bytes(candidate))
        if parsed is not None:
            return parsed
    return None


def _instance_id_from_car(car: dict[str, Any]) -> str:
    texts = car.get("texts")
    if isinstance(texts, list):
        for index in (2, 1, 0):
            if index < len(texts):
                value = str(texts[index] or "").strip()
                if value:
                    return value
    return ""


def _normalize_cpm1_car(raw_car: Any, index: int, names: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(raw_car, dict):
        return None
    car_id = _int_value(raw_car.get("CarID"))
    if car_id <= 0:
        return None
    vinyls = _normalize_cpm1_vinyl_field(raw_car.get("Vynils"))
    window = _normalize_cpm1_vinyl_field(raw_car.get("WindowVinyls"))
    supported = vinyls is not None and window is not None
    return {
        "id": car_id,
        "index": index,
        "name": names.get(str(car_id), f"Car {car_id}"),
        "instance_id": _instance_id_from_car(raw_car),
        "transferable": supported,
        "style_transferable": supported,
        "vinyls": vinyls[1] if vinyls is not None else -1,
        "window": window[1] if window is not None else -1,
        "vinyls_raw": vinyls[0] if vinyls is not None else None,
        "window_raw": window[0] if window is not None else None,
    }


def _memorypack_xor_key(local_id: str) -> bytes:
    chars = list(local_id or "")
    if len(chars) >= 7:
        chars[6], chars[4] = chars[4], chars[6]
    if len(chars) >= 9:
        chars.pop(8)
    if chars:
        chars.append(chars[0])
    return "".join(chars).encode("utf-8")


def _decode_current_memorypack(value: Any, local_id: str) -> bytes | None:
    """Decode the CPM2 response and log only non-sensitive diagnostic details."""
    if not isinstance(value, dict):
        logging.warning("CPM2 cars response has unexpected type: %s", type(value).__name__)
        return None
    if value.get("code") != 1 or not isinstance(value.get("data"), str):
        # Never log the response body: it may contain account or game data.
        logging.warning(
            "CPM2 cars response schema mismatch (code=%r, data_type=%s, keys=%s)",
            value.get("code"), type(value.get("data")).__name__, sorted(str(k) for k in value.keys()),
        )
        return None
    if brotli is None:
        logging.error("Cannot decode CPM2 MemoryPack response: Brotli dependency is missing; install 'brotli'.")
        return None
    try:
        encrypted = base64.b64decode(value["data"], validate=True)
        xor_key = _memorypack_xor_key(local_id)
        if not xor_key:
            logging.warning("Cannot decode CPM2 MemoryPack response: empty account-derived key.")
            return None
        packed = bytes(byte ^ xor_key[index % len(xor_key)] for index, byte in enumerate(encrypted))
        payload = brotli.decompress(packed)
        logging.info("CPM2 MemoryPack decoded successfully (%d bytes).", len(payload))
        return payload
    except Exception as exc:
        # Exception messages only; do not log credentials, tokens, or response data.
        logging.warning("CPM2 MemoryPack decoding failed (%s).", type(exc).__name__)
        return None


def _memorypack_car_offsets(payload: bytes) -> list[tuple[int, int]] | None:
    if len(payload) < 4:
        return None
    expected_count = struct.unpack_from("<i", payload, 0)[0]
    if expected_count == 0:
        return []
    if expected_count < 0 or expected_count > 5000:
        return None
    known_ids = {int(car_id) for car_id in _load_car_names() if str(car_id).isdigit()}
    known: list[tuple[int, int]] = []
    broad: list[tuple[int, int]] = []
    for offset in range(4, len(payload) - 5):
        if payload[offset] != 9 or payload[offset + 5] not in (10, 255):
            continue
        car_id = struct.unpack_from("<i", payload, offset + 1)[0]
        if 0 < car_id <= 5000:
            broad.append((offset, car_id))
            if car_id in known_ids:
                known.append((offset, car_id))
    if len(known) == expected_count:
        return known
    if len(broad) == expected_count:
        return broad
    confirmed: list[tuple[int, int]] = []
    for offset, car_id in broad:
        installed_end = _read_memorypack_installed_body_kits(payload, offset + 5, len(payload))
        if installed_end is None:
            continue
        if _read_memorypack_colors(payload, installed_end, len(payload)) is None:
            continue
        confirmed.append((offset, car_id))
    if len(confirmed) == expected_count:
        return confirmed
    return None


def _read_memorypack_string(payload: bytes, offset: int, end: int) -> int | None:
    if offset + 4 > end:
        return None
    marker = struct.unpack_from("<i", payload, offset)[0]
    offset += 4
    if marker == -1 or marker == 0:
        return offset
    if marker > 0:
        byte_count = marker * 2
    else:
        byte_count = ~marker
        if offset + 4 > end:
            return None
        offset += 4
    if byte_count < 0 or offset + byte_count > end:
        return None
    return offset + byte_count


def _decode_memorypack_string_at(payload: bytes, offset: int, end: int) -> tuple[int, str] | None:
    if offset + 4 > end:
        return None
    marker = struct.unpack_from("<i", payload, offset)[0]
    cursor = offset + 4
    if marker in (-1, 0):
        return cursor, ""
    if marker > 0:
        byte_count = marker * 2
        if cursor + byte_count > end:
            return None
        try:
            return cursor + byte_count, payload[cursor:cursor + byte_count].decode("utf-16-le")
        except UnicodeDecodeError:
            return None
    byte_count = ~marker
    if cursor + 4 + byte_count > end:
        return None
    char_count = struct.unpack_from("<i", payload, cursor)[0]
    cursor += 4
    try:
        value = payload[cursor:cursor + byte_count].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if char_count >= 0 and len(value) != char_count:
        return None
    return cursor + byte_count, value


def _read_memorypack_vinyl(payload: bytes, offset: int, end: int) -> int | None:
    if offset >= end:
        return None
    member_count = payload[offset]
    offset += 1
    if member_count == 255:
        return offset
    if member_count != 6 or offset + 36 > end:
        return None
    values = struct.unpack_from("<9f", payload, offset)
    if not all(math.isfinite(value) and abs(value) < 1_000_000 for value in values):
        return None
    offset += 36
    offset = _read_memorypack_string(payload, offset, end)
    if offset is None or offset + 12 > end:
        return None
    return offset + 12


def _read_memorypack_vinyl_list(payload: bytes, offset: int, end: int) -> tuple[int, int] | None:
    if offset + 4 > end:
        return None
    count = struct.unpack_from("<i", payload, offset)[0]
    offset += 4
    if count == -1:
        return offset, 0
    if count < 0 or count > 2000:
        return None
    for _ in range(count):
        offset = _read_memorypack_vinyl(payload, offset, end)
        if offset is None:
            return None
    return offset, count


def _read_memorypack_int_list(payload: bytes, offset: int, end: int) -> int | None:
    if offset + 4 > end:
        return None
    count = struct.unpack_from("<i", payload, offset)[0]
    offset += 4
    if count == -1:
        return offset
    if count < 0 or count > 1000 or offset + count * 4 > end:
        return None
    return offset + count * 4


def _read_memorypack_installed_body_kits(payload: bytes, offset: int, end: int) -> int | None:
    if offset >= end:
        return None
    member_count = payload[offset]
    offset += 1
    if member_count == 255:
        return offset
    if member_count != 10 or offset + 32 > end:
        return None
    offset += 32
    trims_start = offset
    offset = _read_memorypack_int_list(payload, offset, end)
    if offset is None:
        offset = _read_memorypack_string(payload, trims_start, end)
    if offset is None or offset + 4 > end:
        return None
    return offset + 4


def _read_memorypack_body_kit_colors(payload: bytes, offset: int, end: int) -> int | None:
    if offset >= end:
        return None
    member_count = payload[offset]
    offset += 1
    if member_count == 255:
        return offset
    if member_count != 1 or offset + 4 > end:
        return None
    count = struct.unpack_from("<i", payload, offset)[0]
    offset += 4
    if count == -1:
        return offset
    if count < 0 or count > 128:
        return None
    for _ in range(count):
        if offset >= end:
            return None
        item_members = payload[offset]
        offset += 1
        if item_members == 255:
            continue
        if item_members not in (2, 3) or offset + 12 > end:
            return None
        offset += 12
    return offset


def _read_memorypack_colors(payload: bytes, offset: int, end: int) -> int | None:
    if offset >= end:
        return None
    member_count = payload[offset]
    offset += 1
    if member_count == 255:
        return offset
    if member_count != 8 or offset + 32 > end:
        return None
    offset += 32
    return _read_memorypack_body_kit_colors(payload, offset, end)


def _read_memorypack_bought_body_kits(payload: bytes, offset: int, end: int) -> int | None:
    if offset >= end:
        return None
    member_count = payload[offset]
    offset += 1
    if member_count == 255:
        return offset
    if member_count != 10:
        return None
    for _ in range(10):
        offset = _read_memorypack_int_list(payload, offset, end)
        if offset is None:
            return None
    return offset


def _extract_memorypack_style_fields(
    payload: bytes,
    start: int,
    end: int,
    vinyl_offset: int,
    instance_raw: bytes,
) -> dict[int, bytes] | None:
    installed_start = start + 5
    installed_end = _read_memorypack_installed_body_kits(payload, installed_start, end)
    if installed_end is None:
        return None
    colors_start = installed_end
    colors_end = _read_memorypack_colors(payload, colors_start, end)
    if colors_end is None:
        return None
    instance_start = payload.find(instance_raw, colors_end, vinyl_offset)
    if instance_start < 0:
        return None
    instance_end = instance_start + len(instance_raw)
    bought_candidates = [
        offset
        for offset in range(instance_end, vinyl_offset)
        if _read_memorypack_bought_body_kits(payload, offset, vinyl_offset) == vinyl_offset
    ]
    if not bought_candidates:
        return None
    bought_start = max(bought_candidates)
    if not (colors_end < instance_start < instance_end < bought_start < vinyl_offset):
        return None
    return {
        2: payload[bought_start:vinyl_offset],
        3: payload[colors_start:colors_end],
        4: payload[instance_end:bought_start],
        5: payload[colors_end:instance_start],
        6: payload[installed_start:installed_end],
    }


def _find_memorypack_car_instance(payload: bytes, start: int, vinyl_offset: int) -> tuple[str, bytes] | None:
    strict = re.compile(r"^[A-Za-z]{2}\d{3,}_[A-Za-z]{2}\d{2,}_\d{2,}$")
    fallback: tuple[str, bytes] | None = None
    for offset in range(start + 5, max(start + 5, vinyl_offset - 3)):
        decoded = _decode_memorypack_string_at(payload, offset, vinyl_offset)
        if decoded is None:
            continue
        end, text = decoded
        if not (8 <= len(text) <= 80 and text.count("_") >= 2 and any(char.isdigit() for char in text)):
            continue
        raw = payload[offset:end]
        if strict.fullmatch(text):
            return text, raw
        if fallback is None and re.fullmatch(r"[A-Za-z0-9_-]+", text):
            fallback = (text, raw)
    return fallback


def _parse_memorypack_cloud_vinyls(value: Any, local_id: str) -> list[dict[str, Any]] | None:
    payload = _decode_current_memorypack(value, local_id)
    if payload is None:
        return None
    records = _memorypack_car_offsets(payload)
    if records is None:
        logging.warning(
            "CPM2 MemoryPack decoded, but car-record schema was not recognized (payload_bytes=%d).",
            len(payload),
        )
        return None
    logging.info("CPM2 MemoryPack car records recognized: %d.", len(records))
    result: list[dict[str, Any]] = []
    for index, (start, car_id) in enumerate(records):
        end = records[index + 1][0] if index + 1 < len(records) else len(payload)
        match: tuple[int, int, int, int] | None = None
        for offset in range(start + 5, max(start + 5, end - 7)):
            first = _read_memorypack_vinyl_list(payload, offset, end)
            if first is None:
                continue
            second = _read_memorypack_vinyl_list(payload, first[0], end)
            if second is not None and second[0] == end:
                candidate = (first[1], second[1], offset, first[0])
                if match is None or (candidate[0] + candidate[1], candidate[2]) > (match[0] + match[1], match[2]):
                    match = candidate
        car: dict[str, Any] = {
            "index": index,
            "id": car_id,
            "vinyls": match[0] if match is not None else -1,
            "window": match[1] if match is not None else -1,
            "transferable": False,
            "fingerprint": hashlib.sha256(payload[start:end]).hexdigest(),
        }
        if match is not None:
            instance = _find_memorypack_car_instance(payload, start, match[2])
            if instance is not None:
                instance_id, instance_raw = instance
                style_fields = _extract_memorypack_style_fields(payload, start, end, match[2], instance_raw)
                car.update(
                    {
                        "instance_id": instance_id,
                        "car_id_raw": payload[start + 1:start + 5],
                        "instance_raw": instance_raw,
                        "vinyls_raw": payload[match[2]:match[3]],
                        "window_raw": payload[match[3]:end],
                        "style_fields": style_fields,
                        "style_transferable": style_fields is not None,
                        "transferable": True,
                    }
                )
        result.append(car)
    return result


def _parse_cpm1_memorypack_vinyls(payload: bytes) -> list[dict[str, Any]] | None:
    records = _memorypack_car_offsets(payload)
    if records is None:
        return None
    names = _load_car_names()
    result: list[dict[str, Any]] = []
    for index, (start, car_id) in enumerate(records):
        end = records[index + 1][0] if index + 1 < len(records) else len(payload)
        match = None
        for offset in range(start + 5, end - 10):
            first = _read_memorypack_vinyl_list(payload, offset, end)
            if first is None:
                continue
            second = _read_memorypack_vinyl_list(payload, first[0], end)
            if second is not None:
                candidate = (first[1], second[1], offset, first[0], second[0])
                if match is None or (candidate[0] + candidate[1]) > (match[0] + match[1]):
                    match = candidate
        transferable = match is not None
        result.append(
            {
                "id": car_id,
                "index": index,
                "name": names.get(str(car_id), f"Car {car_id}"),
                "transferable": transferable,
                "style_transferable": transferable,
                "vinyls": match[0] if match else -1,
                "window": match[1] if match else -1,
                "vinyls_raw": payload[match[2]:match[3]] if match else None,
                "window_raw": payload[match[3]:match[4]] if match else None,
            }
        )
    return result


async def _call_cpm1_function(
    function_name: str,
    id_token: str,
    local_id: str,
    session: aiohttp.ClientSession,
) -> tuple[Any, str]:
    headers = {"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}
    encrypted_payload = _encrypt_value(json.dumps({}), local_id)
    if not encrypted_payload:
        return None, "CPM1_ENCRYPT_PAYLOAD_FAILED"
    last_error = ""
    for base in _cpm1_function_bases():
        try:
            async with session.post(
                f"{base}/{function_name}",
                json={"data": encrypted_payload},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                try:
                    body = await response.json(content_type=None)
                except Exception:
                    body = await response.text()
                if response.status != 200:
                    last_error = f"{function_name}@{base}:HTTP_{response.status}"
                    continue
                if not isinstance(body, dict) or "result" not in body:
                    last_error = f"{function_name}@{base}:BAD_BODY"
                    continue
                return _json_unwrap(body.get("result")), ""
        except Exception as exc:
            last_error = f"{function_name}@{base}:{type(exc).__name__}"
    return None, last_error or f"{function_name}_FAILED"


async def _read_cpm1_current_cloud(
    id_token: str,
    local_id: str,
    session: aiohttp.ClientSession,
) -> tuple[list[dict[str, Any]] | None, str]:
    raw_cars, error = await _call_cpm1_function(CPM1_CARS_FUNCTION, id_token, local_id, session)
    if error:
        return None, error
    if not isinstance(raw_cars, list):
        return None, "GET_ALL_CARS_INVALID_RESPONSE"
    names = _load_car_names()
    cars = [
        normalized
        for index, car in enumerate(raw_cars)
        if (normalized := _normalize_cpm1_car(car, index, names)) is not None
    ]
    if not cars:
        return None, "GET_ALL_CARS_EMPTY"
    if any(car.get("style_transferable") for car in cars):
        return cars, ""
    return None, "GET_ALL_CARS_NO_SUPPORTED_VINYLS"


async def _read_cpm1_rtdb(
    id_token: str,
    local_id: str,
    session: aiohttp.ClientSession,
) -> tuple[bytes | None, str]:
    headers = {"Authorization": f"Bearer {id_token}"}
    paths = [
        f"/users/{local_id}/OneCar.json",
        f"/OneCar/{local_id}.json",
        f"/users/{local_id}/cars.json",
        f"/users/{local_id}/garage.json",
        f"/cars/{local_id}.json",
    ]
    last_status = 0
    for path in paths:
        url = f"{CPM1_DATABASE_URL}{path}"
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                last_status = response.status
                text = await response.text()
                if response.status == 200 and text and text.strip() != "null":
                    try:
                        value = json.loads(text)
                    except Exception:
                        value = text.strip().strip('"')
                    if isinstance(value, str) and len(value) > 10:
                        try:
                            return base64.b64decode(value), ""
                        except Exception as exc:
                            return None, f"BASE64_DECODE_ERROR:{exc}"
                    if value and value != "null":
                        return None, f"UNEXPECTED_FORMAT:{type(value).__name__}"
                elif response.status == 401:
                    return None, "AUTH_EXPIRED"
        except Exception as exc:
            logging.warning("CPM1 RTDB path %s failed: %s", path, exc)
    return None, f"CARS_NOT_FOUND_IN_RTDB:last_status={last_status}"


async def open_cpm1_cloud_session(email: str, password: str) -> dict[str, Any]:
    result: dict[str, Any] = {"cars": None, "error": "", "email": email, "password": password, "auth_ok": False}
    auth = await firebase_verify_cpm1_password(email, password)
    if "error" in auth:
        result["error"] = str(auth["error"].get("message", "AUTH_ERROR"))
        return result
    id_token = auth.get("idToken")
    local_id = auth.get("localId")
    if not id_token or not local_id:
        result["error"] = "INVALID_AUTH_PAYLOAD"
        return result
    result["auth_ok"] = True
    result["local_id"] = local_id
    result["id_token"] = id_token
    timeout = aiohttp.ClientTimeout(total=25)
    diagnostics: list[str] = []
    async with aiohttp.ClientSession(timeout=timeout) as session:
        cars, callable_error = await _read_cpm1_current_cloud(id_token, local_id, session)
        if cars is not None:
            result["cars"] = cars
            result["supported_cars"] = sum(1 for car in cars if car.get("style_transferable"))
            result["cloud_source"] = "callable"
            return result
        if callable_error:
            diagnostics.append(f"callable:{callable_error}")
        raw_bytes, rtdb_error = await _read_cpm1_rtdb(id_token, local_id, session)
        if raw_bytes is not None:
            legacy_cars = _parse_cpm1_memorypack_vinyls(raw_bytes)
            if legacy_cars is not None:
                result["cars"] = legacy_cars
                result["raw_bytes"] = raw_bytes
                result["supported_cars"] = sum(1 for car in legacy_cars if car.get("style_transferable"))
                result["cloud_source"] = "rtdb"
                return result
            diagnostics.append("rtdb:MEMORYPACK_PARSE_FAILED")
        elif rtdb_error:
            diagnostics.append(f"rtdb:{rtdb_error}")
    result["error"] = CPM1_UNSUPPORTED_CLOUD_ERROR
    result["error_details"] = "; ".join(diagnostics) or "NO_SUPPORTED_CPM1_DATA"
    return result


async def _call_function(function_name: str, id_token: str, local_id: str) -> tuple[bool, Any]:
    encrypted_payload = _encrypt_value(json.dumps({}), local_id)
    if not encrypted_payload:
        return False, None
    headers = {"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}

    async def request(session: aiohttp.ClientSession) -> tuple[bool, Any]:
        async with session.post(
            f"{CPM2_API_BASE}/{function_name}",
            json={"data": encrypted_payload},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            try:
                body = await response.json(content_type=None)
            except Exception:
                return False, None
            if response.status != 200 or not isinstance(body, dict) or "result" not in body:
                return False, None
        result = body.get("result")
        return True, result

    shared_session = _balance_http_session.get()
    if shared_session is not None:
        ok, result = await request(shared_session)
    else:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as own_session:
            ok, result = await request(own_session)
    if not ok:
        return False, None
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            pass
    return True, result


async def _call_function_payload(
    function_name: str,
    id_token: str,
    payload: Any,
    session: aiohttp.ClientSession,
) -> tuple[bool, Any]:
    headers = {"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}
    try:
        async with session.post(
            f"{CPM2_API_BASE}/{function_name}",
            json={"data": payload},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            try:
                body = await response.json(content_type=None)
            except Exception:
                return False, None
            if response.status != 200 or not isinstance(body, dict) or "result" not in body:
                return False, body
            result = body.get("result")
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                except (TypeError, ValueError):
                    parsed = None
                if parsed is not None:
                    result = parsed
            if _function_result_error_code(result) is not None:
                return False, result
            return True, result
    except Exception:
        return False, None


def _function_result_error_code(result: Any) -> int | str | None:
    if isinstance(result, (int, float)) and not isinstance(result, bool):
        return None if result == 1 else int(result) if float(result).is_integer() else str(result)
    if isinstance(result, str) and result.strip().lstrip("-").isdigit():
        normalized = int(result.strip())
        return None if normalized == 1 else normalized
    if not isinstance(result, dict):
        return None
    code = result.get("code")
    if code is not None:
        try:
            normalized_code: int | str = int(code)
        except (TypeError, ValueError):
            normalized_code = str(code)
        if normalized_code != 1:
            return normalized_code
    if result.get("success") is False:
        return "success=false"
    if result.get("error"):
        return str(result["error"])
    return None


async def _read_raw_cars(id_token: str, local_id: str) -> Any:
    global _cars_function_name
    if _cars_function_name:
        try:
            ok, value = await _call_function(_cars_function_name, id_token, local_id)
        except Exception:
            ok, value = False, None
        if ok:
            return value
    async with _cars_function_lock:
        if _cars_function_name:
            try:
                ok, value = await _call_function(_cars_function_name, id_token, local_id)
            except Exception:
                ok, value = False, None
            if ok:
                return value
        checks = await asyncio.gather(
            *(_call_function(name, id_token, local_id) for name in CPM2_CARS_FUNCTION_CANDIDATES),
            return_exceptions=True,
        )
        for function_name, response in zip(CPM2_CARS_FUNCTION_CANDIDATES, checks):
            if isinstance(response, Exception):
                continue
            ok, value = response
            if ok:
                _cars_function_name = function_name
                return value
    return None


async def _authenticate_vinyl_account(
    email: str,
    password: str,
    session: aiohttp.ClientSession,
) -> tuple[str, str, str]:
    auth: dict[str, Any] = {}
    for attempt in range(3):
        auth = await firebase_verify_cpm2_password(email, password, session=session)
        error = auth.get("error") or {}
        error_message = str(error.get("message") or "")
        transient = bool(error.get("transient")) or any(
            marker in error_message.upper()
            for marker in ("SERVICE_UNAVAILABLE", "CONNECTION_ERROR", "TOO_MANY_ATTEMPTS", "TIMEOUT")
        )
        if not transient:
            break
        if attempt < 2:
            await asyncio.sleep(0.35 * (2 ** attempt))
    id_token = str(auth.get("idToken") or "")
    local_id = str(auth.get("localId") or "")
    error_code = str((auth.get("error") or {}).get("message") or "AUTH_FAILED")
    return id_token, local_id, "" if id_token and local_id else error_code


async def open_cloud_vinyl_session(email: str, password: str) -> dict[str, Any]:
    result: dict[str, Any] = {"cars": None, "error": "", "email": email, "password": password}
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            id_token, local_id, auth_error = await _authenticate_vinyl_account(email, password, session)
            if auth_error:
                result["error"] = auth_error
                return result
            token = set_balance_http_session(session)
            try:
                value = await _read_raw_cars(id_token, local_id)
            finally:
                reset_balance_http_session(token)
        if value is None:
            result["error"] = "CARS_UNAVAILABLE"
            return result
        cars = _parse_memorypack_cloud_vinyls(value, local_id)
        if cars is None:
            # Keep the user-facing error stable; diagnostics above identify the failed stage.
            result["error"] = "VINYL_SCHEMA_UNSUPPORTED"
            return result
        names = _load_car_names()
        result["cars"] = [{**car, "name": names.get(str(car["id"]), f"Car {car['id']}")} for car in cars]
    except Exception as exc:
        logging.warning("Could not inspect CPM2 cloud vinyls for %s: %s", email, exc)
        result["error"] = "CONNECTION_ERROR"
    return result


def _encode_save_car_fields(
    target: dict[str, Any],
    donor: dict[str, Any],
    local_id: str,
    *,
    mode: str = "vinyl",
) -> str:
    values: dict[int, bytes] = {
        0: bytes(target["car_id_raw"]),
        1: bytes(target["instance_raw"]),
        7: bytes(donor["vinyls_raw"]),
        8: bytes(donor["window_raw"]),
    }
    if mode == "style":
        style_fields = donor.get("style_fields")
        if not isinstance(style_fields, dict) or any(key not in style_fields for key in range(2, 7)):
            raise ValueError("STYLE_SCHEMA_UNSUPPORTED")
        values.update({key: bytes(style_fields[key]) for key in range(2, 7)})
    elif mode != "vinyl":
        raise ValueError("TRANSFER_MODE_INVALID")
    fields = tuple(sorted(values.items()))
    serialized = bytearray(struct.pack("<i", len(fields)))
    for key, field in fields:
        serialized.extend(struct.pack("<Hi", key, len(field)))
        serialized.extend(field)
    xor_key = _memorypack_xor_key(local_id)
    if brotli is None or not xor_key:
        raise ValueError("MEMORYPACK_UNAVAILABLE")
    packed = brotli.compress(bytes(serialized))
    encrypted = bytes(byte ^ xor_key[index % len(xor_key)] for index, byte in enumerate(packed))
    return base64.b64encode(encrypted).decode("ascii")


# ==========================================
# BATCH TRANSFER LOGIC WITH PROGRESS & REPORT
# ==========================================
async def execute_batch_transfer(
    transfer_type: str,  # "cpm1_cpm2" or "cpm2_cpm2"
    source_email: str,
    source_pass: str,
    target_email: str,
    target_pass: str,
    car_ids: list[int],
    chat_id: int,
    status_msg_id: int,
) -> None:
    total_cars = len(car_ids)
    
    # 1. Open Source Session
    if transfer_type == "cpm1_cpm2":
        source_snap = await open_cpm1_cloud_session(source_email, source_pass)
    else:
        source_snap = await open_cloud_vinyl_session(source_email, source_pass)

    if source_snap.get("error"):
        bot.send_message(chat_id, f"❌ <b>Source Account Error:</b> {source_snap['error']}")
        return

    # 2. Open Target Session
    target_snap = await open_cloud_vinyl_session(target_email, target_pass)
    if target_snap.get("error"):
        bot.send_message(chat_id, f"❌ <b>Target Account Error:</b> {target_snap['error']}")
        return

    source_cars = {int(c["id"]): c for c in (source_snap.get("cars") or []) if c.get("style_transferable") or c.get("transferable")}
    target_cars = target_snap.get("cars") or []

    timeout = aiohttp.ClientTimeout(total=30)
    results = []

    async with aiohttp.ClientSession(timeout=timeout) as session:
        id_token, local_id, auth_err = await _authenticate_vinyl_account(target_email, target_pass, session)
        if auth_err:
            bot.send_message(chat_id, f"❌ <b>Target Auth Failed:</b> {auth_err}")
            return

        token = set_balance_http_session(session)
        try:
            for idx, car_id in enumerate(car_ids, start=1):
                car_name = MOBIL_CARS.get(car_id, f"Car {car_id}")
                
                # Live Progress Update
                progress_msg = (
                    f"🚀 <b>Transfering Designs in Progress...</b>\n\n"
                    f"<b>Progress:</b> {make_progress_bar(idx - 1, total_cars)}\n"
                    f"<b>Currently Processing:</b> ID {car_id} - <i>{car_name}</i>"
                )
                try:
                    bot.edit_message_text(progress_msg, chat_id, status_msg_id, parse_mode="HTML")
                except Exception:
                    pass

                donor_car = source_cars.get(car_id)
                matching_targets = [c for c in target_cars if int(c.get("id", 0)) == car_id and c.get("transferable")]

                if not donor_car:
                    results.append({"id": car_id, "name": car_name, "status": False, "reason": "Not found/transferable in donor account"})
                    continue
                if not matching_targets:
                    results.append({"id": car_id, "name": car_name, "status": False, "reason": "Not found in target account"})
                    continue

                car_success = True
                fail_reason = ""
                for target in matching_targets:
                    try:
                        payload = _encode_save_car_fields(target, donor_car, local_id, mode="vinyl")
                        ok, save_res = await _call_function_payload(CPM2_SAVE_CAR_FUNCTION, id_token, payload, session)
                        if not ok:
                            car_success = False
                            fail_reason = f"Server rejected ({_function_result_error_code(save_res)})"
                            break
                    except Exception as e:
                        car_success = False
                        fail_reason = str(e)
                        break

                if car_success:
                    results.append({"id": car_id, "name": car_name, "status": True, "reason": "Success"})
                else:
                    results.append({"id": car_id, "name": car_name, "status": False, "reason": fail_reason})

            # Update Progress Bar to 100%
            final_progress = (
                f"✅ <b>Transfer Completed!</b>\n\n"
                f"<b>Progress:</b> {make_progress_bar(total_cars, total_cars)}"
            )
            try:
                bot.edit_message_text(final_progress, chat_id, status_msg_id, parse_mode="HTML")
            except Exception:
                pass

        finally:
            reset_balance_http_session(token)

    # 3. Final Summary Report
    successful_count = sum(1 for r in results if r["status"])
    failed_count = total_cars - successful_count

    report = (
        f"📊 <b>Transfer Summary Report</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Total Requested:</b> {total_cars}\n"
        f"<b>Successful:</b> {successful_count} ✅\n"
        f"<b>Failed:</b> {failed_count} ❌\n\n"
        f"<b>Details per Car:</b>\n"
    )
    for r in results:
        status_icon = "✅ Success" if r["status"] else f"❌ Failed ({r['reason']})"
        report += f"• <b>Car ID {r['id']}</b> ({r['name']}): {status_icon}\n"

    send_chunked_messages(chat_id, report)


# ==========================================
# BOT INTERFACE & MENUS
# ==========================================
def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💳 See my subscription", callback_data="see_sub"))
    markup.add(InlineKeyboardButton("🛠 Use tool", callback_data="use_tool"))
    markup.add(InlineKeyboardButton("👨‍💻 Contact admin", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"))
    return markup


def get_tools_menu_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚗 Check CPM1", callback_data="tool_check_cpm1"))
    markup.add(InlineKeyboardButton("🚙 Check CPM2", callback_data="tool_check_cpm2"))
    markup.add(InlineKeyboardButton("🔄 Transfer CPM1 to CPM2", callback_data="tool_cpm1_to_cpm2"))
    markup.add(InlineKeyboardButton("🔁 Transfer CPM2 to CPM2", callback_data="tool_cpm2_to_cpm2"))
    markup.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return markup


@bot.message_handler(commands=["start"])
def cmd_start(message):
    save_known_user(message.from_user.id)
    welcome_text = (
        f"<b>Welcome to the design transfer bot</b>\n"
        f"Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Admin: {ADMIN_USERNAME}\n\n"
        f"Please choose an option from the menu below:"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_main_menu_keyboard())


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎟 Give subscription", callback_data="admin_give_sub"))
    markup.add(InlineKeyboardButton("🗑 Remove subscription", callback_data="admin_remove_sub"))
    markup.add(InlineKeyboardButton("📋 List subscriptions", callback_data="admin_list_subs"))
    markup.add(InlineKeyboardButton("📊 Bot statistics", callback_data="admin_stats"))
    markup.add(InlineKeyboardButton("🔎 Find user / subscription", callback_data="admin_lookup_user"))
    markup.add(InlineKeyboardButton("📣 Broadcast message", callback_data="admin_broadcast"))
    return markup


@bot.message_handler(commands=["admin"])
def cmd_admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied. Admin only.")
        return
    bot.reply_to(
        message,
        "<b>👑 Admin Panel</b>\\nChoose an action:",
        reply_markup=get_admin_menu_keyboard(),
    )


# ==========================================
# ADMIN COMMANDS (/add, /remove, /subs)
# ==========================================
@bot.message_handler(commands=["add"])
def cmd_add_sub(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied. Admin command only.")
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Usage: `/add <user_id> <days>`\nExample: `/add 123456789 30`", parse_mode="Markdown")
            return
        target_user = int(parts[1])
        days = int(parts[2])
        new_expiry = add_subscription(target_user, days)
        bot.reply_to(
            message,
            f"✅ Subscription updated for user <code>{target_user}</code>!\n"
            f"Added {days} days. New expiration: <b>{new_expiry.strftime('%Y-%m-%d %H:%M UTC')}</b>"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")


@bot.message_handler(commands=["give"])
def cmd_give_sub(message):
    """Admin-only command to grant a subscription and notify the recipient."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied. Admin command only.")
        return

    try:
        parts = (message.text or "").split()
        if len(parts) != 3:
            bot.reply_to(
                message,
                "🎟️ <b>Give Subscription</b>\\n"
                "Usage: <code>/give USER_ID DAYS</code>\\n"
                "Example: <code>/give 123456789 30</code>",
            )
            return

        target_user = int(parts[1])
        days = int(parts[2])
        if target_user <= 0 or days <= 0:
            bot.reply_to(message, "❌ User ID and days must both be positive numbers.")
            return

        new_expiry = add_subscription(target_user, days)
        bot.reply_to(
            message,
            f"✅ Subscription granted to <code>{target_user}</code>!\\n"
            f"➕ Added: <b>{days} day(s)</b>\\n"
            f"📅 Expires: <b>{new_expiry.strftime('%Y-%m-%d %H:%M UTC')}</b>",
        )
        try:
            bot.send_message(
                target_user,
                "🎉 <b>Your subscription has been activated!</b>\\n\\n"
                f"⏳ Duration added: <b>{days} day(s)</b>\\n"
                f"📅 Valid until: <b>{new_expiry.strftime('%Y-%m-%d %H:%M UTC')}</b>\\n"
                "Use /start to open the bot menu.",
            )
        except Exception:
            bot.send_message(
                message.chat.id,
                "ℹ️ Subscription was saved, but I couldn't notify the user. "
                "They may need to open the bot and press /start first.",
            )
    except ValueError:
        bot.reply_to(message, "❌ Invalid input. Use: <code>/give USER_ID DAYS</code>")
    except Exception as e:
        logging.exception("Could not grant subscription")
        bot.reply_to(message, f"❌ Could not grant subscription: {e}")


@bot.message_handler(commands=["remove"])
def cmd_remove_sub(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied. Admin command only.")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage: `/remove <user_id>`", parse_mode="Markdown")
            return
        target_user = int(parts[1])
        if remove_subscription(target_user):
            bot.reply_to(message, f"✅ Subscription removed for user <code>{target_user}</code>.")
        else:
            bot.reply_to(message, f"⚠️ User <code>{target_user}</code> has no active subscription.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")


@bot.message_handler(commands=["subs"])
def cmd_list_subs(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied. Admin command only.")
        return
    subs = load_subscriptions()
    if not subs:
        bot.reply_to(message, "ℹ️ No active subscriptions found.")
        return

    msg = "📋 <b>Active User Subscriptions:</b>\n\n"
    now = datetime.now(timezone.utc)
    for uid, exp_str in subs.items():
        try:
            exp_date = datetime.fromisoformat(exp_str)
            status = "✅ Active" if exp_date > now else "❌ Expired"
            msg += f"• User <code>{uid}</code>: {exp_date.strftime('%Y-%m-%d %H:%M UTC')} ({status})\n"
        except Exception:
            msg += f"• User <code>{uid}</code>: {exp_str} (Invalid Format)\n"

    send_chunked_messages(message.chat.id, msg)


# ==========================================
# CALLBACK HANDLERS
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    if data == "admin_give_sub":
        bot.answer_callback_query(call.id)
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Access denied. Admin only.")
            return
        user_sessions[user_id] = {"state": "admin_wait_give_sub"}
        bot.send_message(chat_id, "Send user ID and duration in days: <code>USER_ID DAYS</code>\\nExample: <code>123456789 30</code>")
        return

    elif data == "admin_remove_sub":
        bot.answer_callback_query(call.id)
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Access denied. Admin only.")
            return
        user_sessions[user_id] = {"state": "admin_wait_remove_sub"}
        bot.send_message(chat_id, "Send the user ID whose subscription should be removed: <code>USER_ID</code>")
        return

    elif data == "admin_list_subs":
        bot.answer_callback_query(call.id)
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Access denied. Admin only.")
            return
        subs = load_subscriptions()
        if not subs:
            bot.send_message(chat_id, "ℹ️ No subscriptions found.")
            return
        now = datetime.now(timezone.utc)
        lines = ["<b>📋 User subscriptions</b>\\n"]
        for uid, expiry in subs.items():
            try:
                exp = datetime.fromisoformat(expiry)
                status = "Active" if exp > now else "Expired"
                lines.append(f"• <code>{uid}</code> — {exp.strftime('%Y-%m-%d %H:%M UTC')} ({status})")
            except Exception:
                lines.append(f"• <code>{uid}</code> — Invalid record")
        send_chunked_messages(chat_id, "\\n".join(lines))
        return

    elif data == "admin_stats":
        bot.answer_callback_query(call.id)
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Access denied. Admin only.")
            return
        known = load_known_users()
        subs = load_subscriptions()
        now = datetime.now(timezone.utc)
        active = 0
        expired = 0
        for expiry in subs.values():
            try:
                if datetime.fromisoformat(expiry) > now:
                    active += 1
                else:
                    expired += 1
            except (ValueError, TypeError):
                continue
        bot.send_message(chat_id,
            "<b>📊 Bot Statistics</b>\n"
            f"Known users: <b>{len(known)}</b>\n"
            f"Subscription records: <b>{len(subs)}</b>\n"
            f"Active subscriptions: <b>{active}</b>\n"
            f"Expired subscriptions: <b>{expired}</b>")
        return

    elif data == "admin_lookup_user":
        bot.answer_callback_query(call.id)
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Access denied. Admin only.")
            return
        user_sessions[user_id] = {"state": "admin_wait_lookup_user"}
        bot.send_message(chat_id, "Send the numeric Telegram user ID to look up: <code>USER_ID</code>")
        return

    elif data == "admin_broadcast":
        bot.answer_callback_query(call.id)
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Access denied. Admin only.")
            return
        user_sessions[user_id] = {"state": "admin_wait_broadcast"}
        bot.send_message(chat_id, "Send the broadcast text now. It will be sent to users who have pressed /start. Send /cancel to abort.")
        return

    if data == "see_sub":
        bot.answer_callback_query(call.id)
        has_sub, sub_info = check_subscription(user_id)
        bot.send_message(
            chat_id,
            f"💳 <b>Subscription Status:</b>\n"
            f"Status: {'Active' if has_sub else 'Inactive'}\n"
            f"Details: {sub_info}"
        )

    elif data == "use_tool":
        bot.answer_callback_query(call.id)
        has_sub, sub_info = check_subscription(user_id)
        if not has_sub:
            bot.send_message(
                chat_id,
                f"❌ <b>Access Denied</b>\n\n"
                f"You do not have an active subscription.\n"
                f"Please contact admin {ADMIN_USERNAME} to buy subscription."
            )
            return
        bot.edit_message_text(
            "<b>Tools Menu:</b>\nPlease select an action below:",
            chat_id,
            call.message.message_id,
            reply_markup=get_tools_menu_keyboard()
        )

    elif data == "back_to_main":
        bot.answer_callback_query(call.id)
        welcome_text = (
            f"<b>Welcome to the design transfer bot</b>\n"
            f"Telegram ID: <code>{user_id}</code>\n"
            f"Admin: {ADMIN_USERNAME}\n\n"
            f"Please choose an option from the menu below:"
        )
        bot.edit_message_text(
            welcome_text,
            chat_id,
            call.message.message_id,
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "tool_check_cpm1":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Please send CPM1 account credentials in format:\n`email:password`", parse_mode="Markdown")
        user_sessions[user_id] = {"state": "waiting_cpm1_inspect"}

    elif data == "tool_check_cpm2":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Please send CPM2 account credentials in format:\n`email:password`", parse_mode="Markdown")
        user_sessions[user_id] = {"state": "waiting_cpm2_inspect"}

    elif data == "tool_cpm1_to_cpm2":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "<b>Step 1/3:</b> Send source <b>CPM1</b> account credentials:\n`email:password`", parse_mode="Markdown")
        user_sessions[user_id] = {"state": "transfer_cpm1_to_cpm2_step1", "type": "cpm1_cpm2"}

    elif data == "tool_cpm2_to_cpm2":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "<b>Step 1/3:</b> Send source <b>CPM2</b> account credentials:\n`email:password`", parse_mode="Markdown")
        user_sessions[user_id] = {"state": "transfer_cpm2_to_cpm2_step1", "type": "cpm2_cpm2"}


# ==========================================
# USER INPUT STATE MACHINE
# ==========================================
@bot.message_handler(func=lambda message: message.from_user.id in user_sessions)
def handle_user_input(message):
    user_id = message.from_user.id
    state_data = user_sessions[user_id]
    state = state_data.get("state")
    text = message.text.strip()

    # --- ADMIN PANEL INPUTS ---
    if state == "admin_wait_lookup_user":
        if not is_admin(user_id):
            user_sessions.pop(user_id, None)
            bot.reply_to(message, "❌ Access denied.")
            return
        try:
            target_user = int(text)
            if target_user <= 0:
                raise ValueError
            has_sub, details = check_subscription(target_user)
            expiry = load_subscriptions().get(str(target_user), "Not recorded")
            known = target_user in load_known_users()
            bot.reply_to(message,
                "<b>🔎 User Lookup</b>\n"
                f"User ID: <code>{target_user}</code>\n"
                f"Known to bot: <b>{'Yes' if known else 'No'}</b>\n"
                f"Subscription: <b>{'Active' if has_sub else 'Inactive'}</b>\n"
                f"Details: {details}\n"
                f"Expiry record: <code>{expiry}</code>")
        except ValueError:
            bot.reply_to(message, "❌ Send a valid numeric user ID.")
        finally:
            user_sessions.pop(user_id, None)

    elif state == "admin_wait_broadcast":
        if not is_admin(user_id):
            user_sessions.pop(user_id, None)
            bot.reply_to(message, "❌ Access denied.")
            return
        if text.lower() == "/cancel":
            user_sessions.pop(user_id, None)
            bot.reply_to(message, "Broadcast cancelled.")
            return
        recipients = load_known_users()
        if not recipients:
            user_sessions.pop(user_id, None)
            bot.reply_to(message, "No known users yet. Users must press /start first.")
            return
        import html
        safe_text = html.escape(text)
        sent = 0
        failed = 0
        bot.reply_to(message, f"📣 Sending to {len(recipients)} user(s)...")
        for recipient in recipients:
            try:
                bot.send_message(recipient, safe_text)
                sent += 1
            except Exception:
                failed += 1
                logging.info("Broadcast failed for user %s", recipient)
        user_sessions.pop(user_id, None)
        bot.send_message(message.chat.id, f"<b>Broadcast finished</b>\nSent: {sent}\nFailed: {failed}")

    elif state == "admin_wait_give_sub":
        if not is_admin(user_id):
            user_sessions.pop(user_id, None)
            bot.reply_to(message, "❌ Access denied.")
            return
        try:
            parts = text.split()
            if len(parts) != 2:
                raise ValueError
            target_user, days = int(parts[0]), int(parts[1])
            if target_user <= 0 or days <= 0:
                raise ValueError
            expiry = add_subscription(target_user, days)
            bot.reply_to(message, f"✅ Subscription granted to <code>{target_user}</code> for {days} day(s).\\nExpires: <b>{expiry.strftime('%Y-%m-%d %H:%M UTC')}</b>")
            try:
                bot.send_message(target_user, f"🎉 <b>Your subscription has been activated!</b>\\nDuration: {days} day(s)\\nValid until: {expiry.strftime('%Y-%m-%d %H:%M UTC')}")
            except Exception:
                bot.send_message(message.chat.id, "ℹ️ Saved, but user could not be notified. They may need to press /start first.")
        except ValueError:
            bot.reply_to(message, "❌ Invalid format. Send: <code>USER_ID DAYS</code>")
        finally:
            user_sessions.pop(user_id, None)

    elif state == "admin_wait_remove_sub":
        if not is_admin(user_id):
            user_sessions.pop(user_id, None)
            bot.reply_to(message, "❌ Access denied.")
            return
        try:
            target_user = int(text)
            if target_user <= 0:
                raise ValueError
            if remove_subscription(target_user):
                bot.reply_to(message, f"✅ Subscription removed for <code>{target_user}</code>.")
            else:
                bot.reply_to(message, f"ℹ️ No subscription found for <code>{target_user}</code>.")
        except ValueError:
            bot.reply_to(message, "❌ Send a valid numeric user ID.")
        finally:
            user_sessions.pop(user_id, None)

    # --- CHECK CPM1 ---
    elif state == "waiting_cpm1_inspect":
        try:
            email, password = text.split(":", 1)
            bot.reply_to(message, "⏳ Inspecting CPM1 Account...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            snapshot = loop.run_until_complete(open_cpm1_cloud_session(email.strip(), password.strip()))
            loop.close()

            if snapshot.get("error"):
                bot.reply_to(message, f"❌ Error: {snapshot['error']}")
            else:
                cars = snapshot.get("cars") or []
                msg = f"<b>✅ CPM1 Account Inspected Successfully!</b>\nTotal Cars: {len(cars)}\n\n"
                for car in cars:
                    msg += f"• Car ID: <code>{car.get('id')}</code> | {car.get('name')}\n"
                send_chunked_messages(message.chat.id, msg)
        except Exception as e:
            bot.reply_to(message, f"❌ Format error: Please use `email:password` format. ({e})")
        finally:
            user_sessions.pop(user_id, None)

    # --- CHECK CPM2 ---
    elif state == "waiting_cpm2_inspect":
        try:
            email, password = text.split(":", 1)
            bot.reply_to(message, "⏳ Inspecting CPM2 Account...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            snapshot = loop.run_until_complete(open_cloud_vinyl_session(email.strip(), password.strip()))
            loop.close()

            if snapshot.get("error"):
                bot.reply_to(message, f"❌ Error: {snapshot['error']}")
            else:
                cars = snapshot.get("cars") or []
                msg = f"<b>✅ CPM2 Account Inspected Successfully!</b>\nTotal Cars: {len(cars)}\n\n"
                for car in cars:
                    msg += f"• Car ID: <code>{car.get('id')}</code> | {car.get('name')}\n"
                send_chunked_messages(message.chat.id, msg)
        except Exception as e:
            bot.reply_to(message, f"❌ Format error: Please use `email:password` format. ({e})")
        finally:
            user_sessions.pop(user_id, None)

    # --- TRANSFER STEP 1: SOURCE ACCOUNT ---
    elif state in ("transfer_cpm1_to_cpm2_step1", "transfer_cpm2_to_cpm2_step1"):
        try:
            email, password = text.split(":", 1)
            user_sessions[user_id]["src_email"] = email.strip()
            user_sessions[user_id]["src_pass"] = password.strip()

            bot.reply_to(message, "<b>Step 2/3:</b> Send target <b>CPM2</b> account credentials:\n`email:password`", parse_mode="Markdown")
            user_sessions[user_id]["state"] = "transfer_step2_target"
        except Exception:
            bot.reply_to(message, "❌ Invalid format. Please send as `email:password`.", parse_mode="Markdown")

    # --- TRANSFER STEP 2: TARGET ACCOUNT & COMMON CAR MATCHING ---
    elif state == "transfer_step2_target":
        try:
            email, password = text.split(":", 1)
            user_sessions[user_id]["tgt_email"] = email.strip()
            user_sessions[user_id]["tgt_pass"] = password.strip()

            bot.reply_to(message, "⏳ Fetching accounts and comparing common available cars...")

            src_email = user_sessions[user_id]["src_email"]
            src_pass = user_sessions[user_id]["src_pass"]
            transfer_type = user_sessions[user_id]["type"]

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            if transfer_type == "cpm1_cpm2":
                src_snap = loop.run_until_complete(open_cpm1_cloud_session(src_email, src_pass))
            else:
                src_snap = loop.run_until_complete(open_cloud_vinyl_session(src_email, src_pass))

            tgt_snap = loop.run_until_complete(open_cloud_vinyl_session(email.strip(), password.strip()))
            loop.close()

            if src_snap.get("error"):
                bot.reply_to(message, f"❌ Source Account Error: {src_snap['error']}")
                user_sessions.pop(user_id, None)
                return

            if tgt_snap.get("error"):
                bot.reply_to(message, f"❌ Target Account Error: {tgt_snap['error']}")
                user_sessions.pop(user_id, None)
                return

            src_cars = {int(c["id"]): c for c in (src_snap.get("cars") or []) if c.get("style_transferable") or c.get("transferable")}
            tgt_cars = {int(c["id"]): c for c in (tgt_snap.get("cars") or [])}

            # Find Common Cars
            common_car_ids = sorted(list(set(src_cars.keys()) & set(tgt_cars.keys())))

            if not common_car_ids:
                bot.reply_to(message, "❌ No common transferable cars found between source and target accounts.")
                user_sessions.pop(user_id, None)
                return

            user_sessions[user_id]["common_ids"] = common_car_ids

            msg = "<b>Step 3/3: Common Cars Found!</b>\nThe following cars are available in both accounts:\n\n"
            for cid in common_car_ids:
                car_name = MOBIL_CARS.get(cid, f"Car {cid}")
                msg += f"• Car ID: <code>{cid}</code> | {car_name}\n"

            msg += (
                "\n<b>Reply with the Car IDs you want to transfer.</b>\n"
                "You can specify a single ID or multiple IDs separated by commas.\n"
                "<i>Example format:</i> <code>2,4,16,177,98,100</code>"
            )

            user_sessions[user_id]["state"] = "transfer_step3_indices"
            send_chunked_messages(message.chat.id, msg)

        except Exception as e:
            bot.reply_to(message, f"❌ Connection Error: {e}")
            user_sessions.pop(user_id, None)

    # --- TRANSFER STEP 3: PROCESS SELECTION & EXECUTE WITH PROGRESS BAR ---
    elif state == "transfer_step3_indices":
        try:
            raw_ids = [s.strip() for s in text.split(",") if s.strip().isdigit()]
            selected_ids = [int(x) for x in raw_ids if int(x) in user_sessions[user_id]["common_ids"]]

            if not selected_ids:
                bot.reply_to(message, "❌ No valid matching Car IDs selected from the common list. Please try again.")
                return

            src_email = user_sessions[user_id]["src_email"]
            src_pass = user_sessions[user_id]["src_pass"]
            tgt_email = user_sessions[user_id]["tgt_email"]
            tgt_pass = user_sessions[user_id]["tgt_pass"]
            transfer_type = user_sessions[user_id]["type"]

            status_msg = bot.reply_to(
                message,
                f"🚀 <b>Starting Transfer Process...</b>\n\n"
                f"<b>Progress:</b> {make_progress_bar(0, len(selected_ids))}\n"
                f"<b>Currently Processing:</b> Initializing...",
                parse_mode="HTML"
            )

            # Run Batch Transfer Loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                execute_batch_transfer(
                    transfer_type=transfer_type,
                    source_email=src_email,
                    source_pass=src_pass,
                    target_email=tgt_email,
                    target_pass=tgt_pass,
                    car_ids=selected_ids,
                    chat_id=message.chat.id,
                    status_msg_id=status_msg.message_id,
                )
            )
            loop.close()

        except Exception as e:
            bot.reply_to(message, f"❌ Execution Error: {e}")
        finally:
            user_sessions.pop(user_id, None)


# ==========================================
# BOT POLLING MAIN ENTRY
# ==========================================
if __name__ == "__main__":
    print("Bot is starting up...")
    bot.infinity_polling()
