#!/usr/bin/env python3

import os
import argparse
import time
import logging
from datetime import datetime as dt
from datetime import timedelta as td
from urllib.request import urlopen


from gpiozero import OutputDevice, Button
import icalendar
import recurring_ical_events
from dotenv import load_dotenv
import humanize
import pytz
from prometheus_client import start_http_server, Counter, Gauge


urllib_response = Counter('url_response', 'Responses from urllib', ['status'])
urllib_timeout = Counter('url_timeout', 'Timeouts from urllib')


def update_events(url=None):
    logging.debug("Executing update_events()")
    if not url:
        raise ValueError("updated_events() did not receive `url` (None)")

    sleep_time = int(os.getenv("ALARMCLOCK_REFRESH_FREQUENCY", 300))
    events = None

    while not events:
        start_date = dt.now()
        end_date = dt.now() + td(days=7)

        try:
            with urlopen(url, timeout=5) as r:
                ical_string = r.read()
                urllib_response.labels(status=r.status).inc()
        except TimeoutError:
            urllib_timeout.inc()
            logging.error(f"Timeout for url {url}")
            return None
        except urllib.error.HTTPError as e:
            urllib_response.labels(status=e.status).inc()
            logging.error(f"HTTP Error for url {url}: {e.status}")
            return None

        calendar = icalendar.Calendar.from_ical(ical_string)
        events = recurring_ical_events.of(calendar).between(start_date, end_date)
        events.sort(key=lambda date: date["DTSTART"].dt)

        if events:
            logging.debug(f"No events found. Sleeping for {sleep_time} seconds.")
            time.sleep(sleep_time)

    event_str = " ".join(
        [str(event["DTSTART"].dt) + str(event["DTEND"].dt) for event in events]
    )
    event_hash = hash(event_str)

    return calendar, events, event_hash


def show_summary(events=None):
    logging.debug("Executing show_summary()")
    if not events:
        logging.error("show_summary() did not receive `events` (None")

    now = dt.utcnow().replace(tzinfo=pytz.utc)

    for event in events:
        start = event["DTSTART"].dt
        end = event["DTEND"].dt
        duration = end - start
        p_start = humanize.precisedelta(now - start)
        p_end = humanize.precisedelta(now - end)
        summary = event["SUMMARY"]

        if start < now:
            logging.info(
                f"Alarm[{summary}] has been active since {start} | duration {duration} | ends: {p_end}"
            )
        else:
            logging.info(
                f"Alarm[{summary}] starts at {start} ({p_start}) | duration {duration}"
            )


if __name__ == "__main__":
    start_http_server(8000)
    load_dotenv()

    next_alarm = 0

    parser = argparse.ArgumentParser(
        "Trigger bed shaker from RPi based on ics calendar."
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Choose console loglevel. Select DEBUG for more verbose messages.",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument(
        "--log-format",
        default="[%(asctime)s] %(levelname)s: %(message)s",
        help="Format of console log messages. See https://docs.python.org/3.7/library/logging.html#formatter-objects "
        "and https://docs.python.org/3.7/library/logging.html#logrecord-attributes",
    )
    args = parser.parse_args()

    logging.basicConfig(format=args.log_format, level=args.log_level)
    logging.debug(f"args: {args}")

    if args.log_level == "DEBUG":
        for x in os.environ:
            logging.debug(f"{x}: {os.environ[x]}")

    if not os.getenv("ALARMCLOCK_URL"):
        raise SystemExit(
            "URL for ics file must be provided in environment variable ALARMCLOCK_URL"
        )

    url = os.getenv("ALARMCLOCK_URL")
    relay_pin = int(os.getenv("ALARMCLOCK_RELAY_PIN", 4))
    sensor_pin = int(os.getenv("ALARMCLOCK_SENSOR_PIN", 17))
    refresh_frequency = int(os.getenv("ALARMCLOCK_REFRESH_FREQUENCY", 300))

    # This is fine, but Python idiom would probably be to one-liner it:
    #    with_gpio = "ALARMCLOCK_NO_GPIO" not in os.environ
    if os.getenv("ALARMCLOCK_NO_GPIO"):
        with_gpio = False
    else:
        with_gpio = True

    logging.debug(f"ALARMCLOCK_URL: {url}")
    logging.debug(f"ALARMCLOCK_RELAY_PIN: {relay_pin}")
    logging.debug(f"ALARMCLOCK_SENSOR_PIN: {sensor_pin}")
    logging.debug(f"ALARMCLOCK_REFRESH_FREQUENCY: {refresh_frequency}")
    logging.debug(f"with_gpio (opposite ALARMCLOCK_NO_GPIO): {with_gpio}")

    # Set up relay to activate shaker.
    if with_gpio:
        relay = OutputDevice(relay_pin, active_high=True, initial_value=False)

        # Set up sensor to determine bed occupancy.
        sensor = Button(pin=sensor_pin, hold_time=1, hold_repeat=True)

    calendar, events, event_hash = update_events(url)
    last_update_time = time.time()

    show_summary(events)

    logging.debug("Starting loop")
    while True:
        if time.time() > (last_update_time + refresh_frequency):
            calendar, events, new_event_hash = update_events(url)
            last_update_time = time.time()
            if new_event_hash != event_hash:
                show_summary(events)
                event_hash = new_event_hash

        if recurring_ical_events.of(calendar).at(dt.now()):
            logging.info("Starting alarm")
            show_summary(events)
            while recurring_ical_events.of(calendar).at(dt.now()):
                if with_gpio:
                    if sensor.is_pressed:
                        logging.debug("relay.on()")
                        relay.on()
                        time.sleep(1)
                    if relay.is_active:
                        logging.debug("relay.off()")
                        relay.off()
                        time.sleep(3)
                else:
                    logging.debug("Triggering alarm")
                    # also here
                    while recurring_ical_events.of(calendar).at(dt.now()):
                        time.sleep(1)

            logging.info("Ending alarm")
            calendar, events, new_event_hash = update_events(url)
            last_update_time = time.time()

            if new_event_hash != event_hash:
                show_summary(events)
                event_hash = new_event_hash

        time.sleep(1)
