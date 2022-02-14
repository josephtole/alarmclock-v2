#!/usr/bin/env python3

import os
import argparse
import time
import logging
from datetime import datetime as dt
from datetime import timedelta as td

from gpiozero import OutputDevice, Button
import icalendar
import recurring_ical_events
import urllib.request
from dotenv import load_dotenv
import humanize
import pytz

# overall: standard Python style is 4 spaces per indentation level, not 2 or tab
# Running your code through `black` (on PyPI) will generally do the right thing

def update_events(url=None):
  logging.debug('Executing update_events()')
  # Comparing against None with equality is frowned upon.
  # If you need to see if it is exactly the None object (which is a singleton),
  # use `if url is None`, and if you just want to see if it's set or not, use
  # `if not url`
  # Also, is failing to receive a URL expected/normal behaviour?
  # If not - if it's only checking for a bug condition etc - just throw an
  # exception instead of returning a different result signature
  if url == None:
    logging.error('updated_events() did not receive `url` (None)')
    return None

  sleep_time = int(os.getenv('ALARMCLOCK_REFRESH_FREQUENCY', 300))
  
  # events is reassigned below, not sure what recurring_ical_events.of()
  # returns, but assuming a possibly-empty list
  # If so, better to just set events to None here, and use `while not events`
  # In Python, None is much preferred as a signal value rather than an empty
  # string.  There's also another idiom if you need to distinguish between None
  # and no-value.
  events = ''

  while len(events) < 1:
    start_date = dt.now()
    end_date = dt.now() + td(days=7)

    try:
      ical_string = urllib.request.urlopen(url).read()
    except:
      pass

    # this will throw an unboundlocalerror or nameerror if the urllib
    # request above fails.
    # You might want to make the except clause just return instead of 
    # continuing
    calendar = icalendar.Calendar.from_ical(ical_string)
    events = recurring_ical_events.of(calendar).between(start_date, end_date)
    events.sort(key=lambda date: date["DTSTART"].dt)
    
    if len(events) < 1:
      logging.debug(f'No events found. Sleeping for {sleep_time} seconds.')
      time.sleep(sleep_time)

  # use `(string) var += "append text"` instead of var = var + ...
  # for bonus points do it as a list comprehension :)
  #     event_str = " ".join([
  #         str(event["DTSTART"].dt) + str(event["DTEND"].dt)
  #         for event in events
  #     ])
  event_str = ''
  for event in events:
    event_str = event_str + str(event["DTSTART"].dt) + str(event["DTEND"].dt)

  event_hash = hash(event_str)

  return calendar, events, event_hash


def show_summary(events=None):
  logging.debug('Executing show_summary()')
  # if not events:
  if events == None:
    logging.error('show_summary() did not receive `events` (None')

  now = dt.utcnow().replace(tzinfo=pytz.utc)

  for event in events:
    start = event["DTSTART"].dt
    end = event["DTEND"].dt
    duration = end - start
    p_start = humanize.precisedelta(now - start)
    p_end = humanize.precisedelta(now - end)
    summary = event["SUMMARY"]

    if start < now:
        logging.info(f"Alarm[{summary}] has been active since {start} | duration {duration} | ends: {p_end}")
    else:
        logging.info(f"Alarm[{summary}] starts at {start} ({p_start}) | duration {duration}")


if __name__ == "__main__":
  # Style: usually you would put all program logic in a function and
  # call it from here after doing arg-parsing and log setup etc.
  # Typically called main() or similar.
  # That allows you to import this module and call the program logic from another
  # script if you want, which is difficult if it's all in the `if name is __main__`
  # block.
  logging.debug("Starting core code...")

  load_dotenv()

  next_alarm = 0

  # argparse is fine, but if you want to do more complex argument/option handling,
  # there's a 3rd-party package called `click` (it's on PyPI) which is really 
  # good and looks like it might become part of the standard library in future
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

  # This seems to solve a bug
  # This is because you're executing logging.debug() above.  If there are no
  # handlers configured when the first log message is emitted, a default
  # handler/formatter is assigned.
  # If you wait to log until you've called logging.basicConfig() you won't
  # need this.
  for handler in logging.root.handlers[:]:
      logging.root.removeHandler(handler)

  logging.basicConfig(format=args.log_format, level=args.log_level)
  logging.debug(f"args: {args}")

  # This doesn't need to be conditional.  If handler level is set higher than
  # DEBUG, the messages won't be sent to the log.  It also fixes the case where
  # if the level is set *lower* than DEBUG, this won't emit these lines,
  # although that can't happen here as you don't have anything below DEBUG
  # in the choices for this option.
  if args.log_level == "DEBUG":
    for x in os.environ:
      logging.debug(f"{x}: {os.environ[x]}")

  # idiomatically:  if not os.getenv('ALARMCLOCK_URL'):
  if os.getenv('ALARMCLOCK_URL') == None:
      logging.error('URL for ics file must be provided in environment variable ALARMCLOCK_URL')
      # Another way to exit nonzero will automatically spit a message to stderr,
      # if you want that:
      #    raise SystemExit("error message")
      # If a True-ish value is supplied to SystemExit, it exits nonzero,
      # zero otherwise.
      exit(1)

  url = os.getenv('ALARMCLOCK_URL')
  relay_pin = os.getenv('ALARMCLOCK_RELAY_PIN', 4)
  sensor_pin = os.getenv('ALARMCLOCK_SENSOR_PIN', 17)
  refresh_frequency = os.getenv('ALARMCLOCK_REFRESH_FREQUENCY', 300)
  
  # This is fine, but Python idiom would probably be to one-liner it:
  #    with_gpio = "ALARMCLOCK_NO_GPIO" not in os.environ
  if os.getenv('ALARMCLOCK_NO_GPIO'):
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
    relay = OutputDevice(
        int(relay_pin), active_high=True, initial_value=False
    )

    # Set up sensor to determine bed occupancy.
    sensor = Button(
        pin=int(sensor_pin), hold_time=1, hold_repeat=True
    )

  calendar, events, event_hash = update_events(url)
  last_update_time = time.time()

  show_summary(events)

  logging.debug('Starting loop')
  while True:
    # You could do int(refresh_frequency) once above when you extract it from
    # the environment, and avoid doing it every loop here.
    # Also, time values are floats, and you could just leave them that way;
    # I don't think you're relying on them being ints anywhere.
    if int(time.time()) > (int(last_update_time) + int(refresh_frequency)):
      calendar, events, new_event_hash = update_events(url)
      last_update_time = time.time()
      if new_event_hash != event_hash:
        show_summary(events)
        event_hash = new_event_hash

    # taking len() of a list and then comparing to 0 is non-idiomatic
    # Standard Python style would just be:
    #    if recurring_ical_events.of(calendar).at(dt.now()):
    # That tests for a non-empty list
    if len(recurring_ical_events.of(calendar).at(dt.now())) > 0:
      logging.info('Starting alarm')
      show_summary(events)
      # again, `while <list>:` rather than taking len() and comparing against 0
      while len(recurring_ical_events.of(calendar).at(dt.now())) > 0:
        if with_gpio: 
          if sensor.is_pressed:
            logging.debug("relay.on()")
            relay.on()
            time.sleep(1)
          if relay.is_active:
            logging.debug('relay.off()')
            relay.off()
            time.sleep(3)
        else:
          logging.debug("Triggering alarm")
          # also here
          while len(recurring_ical_events.of(calendar).at(dt.now())) > 0:
            time.sleep(1)

      logging.info('Ending alarm')
      calendar, events, new_event_hash = update_events(url)
      last_update_time = time.time()
      # this ends up calling show_summary() here, plus right after this if block?
      # is that what you want?
      if new_event_hash != event_hash:
        show_summary(events)
        event_hash = new_event_hash

      show_summary(events)

    time.sleep(1)
