# alarmclock-v2
Complete rewrite of old alarm clock and init commit seems to solve all known problems while keeping code base simple, in comparison to original.

## Environment variables

- ALARMCLOCK_URL: URL to pull ICS from.
- ALARMCLOCK_RELAY_PIN: The pi pin that will trigger the relay to activate the alarm (default: 4).
- ALARMCLOCK_SENSOR_PIN: The GPIO pin to check if the bed is occupied (default: 17).
- ALARMCLOCK_REFRESH_FREQUENCY: Frequency to check online ICS file for updates in seconds (default: 300).
- ALARMCLOCK_NO_GPIO: Used for testong on non embedded board. Does not try to read or set pins (default: False).
