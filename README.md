# alarmclock-v2
Complete rewrite of old alarm clock and init commit seems to solve all known problems while keeping code base simple, in comparison to original.

## Environment Variables

- ALARMCLOCK_URL: URL to pull ICS from.
- ALARMCLOCK_RELAY_PIN: The pi pin that will trigger the relay to activate the alarm (default: 4).
- ALARMCLOCK_SENSOR_PIN: The GPIO pin to check if the bed is occupied (default: 17).
- ALARMCLOCK_REFRESH_FREQUENCY: Frequency to check online ICS file for updates in seconds (default: 300).
- ALARMCLOCK_NO_GPIO: Used for testong on non embedded board. Does not try to read or set pins (default: False)

## The Environment

I attempted to use `Environment` in the unit file to set ALARMCLOCK_URL however google calendar was using the `%` character and this is reserved in systemd unit files can connot be escaped. The common recommendation is to use the `EnvironmentFile` systemd directive and place the variables in that file. That is an option but, because this is already using dotenv (was used for testing), the easiest solution seemed to be to put the variables in a file called `.env` in the same directory as the `alarmclock.py`.
