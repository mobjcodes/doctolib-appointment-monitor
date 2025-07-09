import os
from datetime import date, datetime, timedelta
import json
import urllib.parse
import urllib.request
import time
import random

# Get sensitive data from environment variables (GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Your doctor-specific URLs and settings
BOOKING_URL = 'https://www.doctolib.de/facharzt-fur-humangenetik/berlin/annechristin-meiner/booking/availabilities?specialityId=1305&telehealth=false&placeId=practice-207074&insuranceSectorEnabled=true&insuranceSector=public&isNewPatient=false&isNewPatientBlocked=false&motiveIds[]=5918040&pid=practice-207074&bookingFunnelSource=profile'
AVAILABILITIES_URL = 'https://www.doctolib.de/availabilities.json?visit_motive_ids=5918040&agenda_ids=529392&practice_ids=207074&insurance_sector=public&telehealth=false&start_date=2025-07-09&limit=5'
APPOINTMENT_NAME = 'Dr. Meiner'
MOVE_BOOKING_URL = None
UPCOMING_DAYS = 15
MAX_DATETIME_IN_FUTURE = datetime.today() + timedelta(days = UPCOMING_DAYS)
NOTIFY_HOURLY = False

print("Script is running...")
print(f"Checking appointments for: {BOOKING_URL}")

if not (
    TELEGRAM_BOT_TOKEN
    and TELEGRAM_CHAT_ID
    and BOOKING_URL
    and AVAILABILITIES_URL
    ) or UPCOMING_DAYS > 15:
    print("Script exiting - missing required variables or UPCOMING_DAYS > 15")
    exit()

print("Making request to Doctolib API...")

# Add random delay to appear more human-like
time.sleep(random.uniform(1, 3))

urlParts = urllib.parse.urlparse(AVAILABILITIES_URL)
query = dict(urllib.parse.parse_qsl(urlParts.query))
query.update({
    'limit': UPCOMING_DAYS,
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
    response = urllib.request.urlopen(request).read().decode('utf-8')
    print("Successfully got response from API")
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    if e.code == 403:
        print("Doctolib is blocking requests from this IP address")
        print("This commonly happens with cloud servers/GitHub Actions")
        print("Consider using a residential VPS or running locally")
    exit()
except Exception as e:
    print(f"Error making API request: {e}")
    exit()

try:
    availabilities = json.loads(response)
    print(f"Found {availabilities.get('total', 0)} total appointments")
except Exception as e:
    print(f"Error parsing JSON response: {e}")
    exit()

slotsInNearFuture = availabilities['total']
slotInNearFutureExist = slotsInNearFuture > 0
earlierSlotExists = False

if slotInNearFutureExist:
    print("Checking for appointments within the specified timeframe...")
    for day in availabilities['availabilities']:
        if len(day['slots']) == 0:
            continue
        nextDatetimeIso8601 = day['date']
        nextDatetime = (datetime.fromisoformat(nextDatetimeIso8601)
                                .replace(tzinfo = None))
        if nextDatetime < MAX_DATETIME_IN_FUTURE:
            earlierSlotExists = True
            break

isOnTheHour = datetime.now().minute == 0
isHourlyNotificationDue = isOnTheHour and NOTIFY_HOURLY

if not (earlierSlotExists or isHourlyNotificationDue):
    print("No appointments found within criteria - exiting")
    exit()

print("Appointments found! Sending notification...")

message = ''
if APPOINTMENT_NAME:
    message += f'👨‍⚕️👩‍⚕️ {APPOINTMENT_NAME}'
    message += '\n'

if earlierSlotExists:
    pluralSuffix = 's' if slotsInNearFuture > 1 else ''
    message += f'🔥 {slotsInNearFuture} slot{pluralSuffix} within {UPCOMING_DAYS}d!'
    message += '\n'
    if MOVE_BOOKING_URL:
        message += f'<a href="{MOVE_BOOKING_URL}">🚚 Move existing booking</a>.'
        message += '\n'

if isHourlyNotificationDue:
    nextSlotDatetimeIso8601 = availabilities['next_slot']
    nextSlotDate = (datetime.fromisoformat(nextSlotDatetimeIso8601)
                                .strftime('%d %B %Y'))
    message += f'🐌 slot <i>{nextSlotDate}</i>.'
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

