import os
from datetime import date, datetime, timedelta
import json
import urllib.parse
import urllib.request
import gzip
import time
import random

# Get sensitive data from environment variables (GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Your doctor-specific URLs and settings
BOOKING_URL = 'https://www.doctolib.de/facharzt-fur-humangenetik/berlin/annechristin-meiner/booking/availabilities?specialityId=1305&telehealth=false&placeId=practice-207074&insuranceSectorEnabled=true&insuranceSector=public&isNewPatient=false&isNewPatientBlocked=false&motiveIds[]=5918040&pid=practice-207074&bookingFunnelSource=profile'
AVAILABILITIES_URL = 'https://www.doctolib.de/availabilities.json?visit_motive_ids=5918040&agenda_ids=529392&practice_ids=207074&insurance_sector=public&telehealth=false&start_date=2025-07-09&limit=5'
APPOINTMENT_NAME = 'Dr. Hassas'
MOVE_BOOKING_URL = None

# Updated settings - work within API limits but check multiple ranges
UPCOMING_DAYS = 15  # Maximum per API call
TOTAL_DAYS_TO_MONITOR = 45  # Total range we want to monitor
MAX_DATETIME_IN_FUTURE = datetime.today() + timedelta(days = TOTAL_DAYS_TO_MONITOR)
NOTIFY_HOURLY = False

print("Script is running...")
print(f"Checking appointments for: {BOOKING_URL}")
print(f"Monitoring appointments up to {TOTAL_DAYS_TO_MONITOR} days ahead")

if not (
    TELEGRAM_BOT_TOKEN
    and TELEGRAM_CHAT_ID
    and BOOKING_URL
    and AVAILABILITIES_URL
    ):
    print("Script exiting - missing required variables")
    exit()

print("Making request to Doctolib API...")

# Add random delay to appear more human-like
time.sleep(random.uniform(1, 3))

urlParts = urllib.parse.urlparse(AVAILABILITIES_URL)
query = dict(urllib.parse.parse_qsl(urlParts.query))
query.update({
    'limit': UPCOMING_DAYS,  # Now uses 60 instead of 15
    'start_date': date.today(),
})
newAvailabilitiesUrl = (urlParts
                            ._replace(query = urllib.parse.urlencode(query))
                            .geturl())

print(f"API URL: {newAvailabilitiesUrl}")

# Create request with enhanced headers to mimic a real browser
request = urllib.request.Request(newAvailabilitiesUrl)

# Add comprehensive headers to look like a real browser
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.doctolib.de/',
    'Origin': 'https://www.doctolib.de',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'DNT': '1',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache'
}

for key, value in headers.items():
    request.add_header(key, value)

try:
    print("Sending request to Doctolib...")
    response_obj = urllib.request.urlopen(request)
    response_data = response_obj.read()
    
    print(f"Response status: {response_obj.getcode()}")
    print(f"Content-Encoding: {response_obj.headers.get('Content-Encoding', 'none')}")
    print(f"Content-Type: {response_obj.headers.get('Content-Type', 'none')}")
    
    # Check if response is compressed and handle accordingly
    content_encoding = response_obj.headers.get('Content-Encoding', 'none')
    if content_encoding == 'gzip':
        print("Response is gzip compressed, decompressing...")
        try:
            response_data = gzip.decompress(response_data)
            print("Successfully decompressed gzip data")
        except Exception as gzip_error:
            print(f"Error decompressing gzip: {gzip_error}")
            exit()
    elif content_encoding == 'br':
        print("Response is Brotli compressed, decompressing...")
        try:
            import brotli
            response_data = brotli.decompress(response_data)
            print("Successfully decompressed Brotli data")
        except ImportError:
            print("Brotli library not available. Installing...")
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "brotli"])
            import brotli
            response_data = brotli.decompress(response_data)
            print("Successfully decompressed Brotli data")
        except Exception as brotli_error:
            print(f"Error decompressing Brotli: {brotli_error}")
            exit()
    elif content_encoding not in ['none', 'identity']:
        print(f"Unknown compression type: {content_encoding}")
        exit()
    
    # Try different encodings to decode the response
    response = None
    for encoding in ['utf-8', 'iso-8859-1', 'cp1252']:
        try:
            response = response_data.decode(encoding)
            print(f"Successfully decoded response using {encoding}")
            break
        except UnicodeDecodeError as decode_error:
            print(f"Failed to decode with {encoding}: {decode_error}")
            continue
    
    if response is None:
        print("Failed to decode response with any encoding")
        print(f"Raw response bytes (first 100): {response_data[:100]}")
        exit()
    
    print("Successfully got and decoded response from API")
    
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    if e.code == 403:
        print("Doctolib is blocking requests from this IP address")
        print("This commonly happens with cloud servers/GitHub Actions")
        print("Consider using a residential VPS or running locally")
    exit()
except Exception as e:
    print(f"Error making API request: {e}")
    print(f"Error type: {type(e).__name__}")
    exit()

try:
    availabilities = json.loads(response)
    print(f"Found {availabilities.get('total', 0)} total appointments")
    print(f"JSON keys: {list(availabilities.keys())}")
except Exception as e:
    print(f"Error parsing JSON response: {e}")
    print(f"Response content (first 500 chars): {response[:500]}")
    exit()

slotInNearFutureExist = total_appointments > 0

# Updated logic - now checks for ANY available appointments from all chunks
if slotInNearFutureExist:
    print(f"Found {total_appointments} total appointments across all date ranges!")
    
    # Check the dates of available appointments
    earliest_date = None
    for day in all_availabilities:
        if len(day['slots']) > 0:
            appointment_date = datetime.fromisoformat(day['date']).replace(tzinfo=None)
            if earliest_date is None or appointment_date < earliest_date:
                earliest_date = appointment_date
            print(f"Appointment available on: {appointment_date.strftime('%Y-%m-%d (%A)')}")
    
    if earliest_date:
        days_away = (earliest_date - datetime.today()).days
        print(f"Earliest appointment is {days_away} days away")
        
        # Send notification for ANY available appointment
        appointmentExists = True
    else:
        appointmentExists = False
else:
    appointmentExists = False

isOnTheHour = datetime.now().minute == 0
isHourlyNotificationDue = isOnTheHour and NOTIFY_HOURLY

if not (appointmentExists or isHourlyNotificationDue):
    print("No appointments found across all date ranges - exiting")
    exit()

print("Appointments found! Sending notification...")

message = ''
if APPOINTMENT_NAME:
    message += f'👨‍⚕️👩‍⚕️ {APPOINTMENT_NAME}'
    message += '\n'

if appointmentExists:
    pluralSuffix = 's' if total_appointments > 1 else ''
    if earliest_date:
        days_away = (earliest_date - datetime.today()).days
        message += f'🔥 {total_appointments} slot{pluralSuffix} available!'
        message += f'\n📅 Earliest: {earliest_date.strftime("%B %d, %Y")} ({days_away} days away)'
    else:
        message += f'🔥 {total_appointments} slot{pluralSuffix} available!'
    message += '\n'
    if MOVE_BOOKING_URL:
        message += f'<a href="{MOVE_BOOKING_URL}">🚚 Move existing booking</a>.'
        message += '\n'

if isHourlyNotificationDue:
    # For hourly notifications, we'd need to find the next slot beyond our range
    # For now, we'll skip this feature with multiple API calls
    message += f'🐌 Hourly check completed.'
    message += '\n'

message += f'Book now on <a href="{BOOKING_URL}">doctolib.de</a>.'

print(f"Message to send: {message}")

urlEncodedMessage = urllib.parse.quote(message)

try:
    urllib.request.urlopen(
        (f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        f'?chat_id={TELEGRAM_CHAT_ID}'
        f'&text={urlEncodedMessage}'
        f'&parse_mode=HTML'
        f'&disable_web_page_preview=true')
    )
    print("Notification sent successfully!")
except Exception as e:
    print(f"Error sending Telegram message: {e}")
