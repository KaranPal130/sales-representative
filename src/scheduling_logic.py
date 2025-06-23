from datetime import datetime, timedelta, time
import pytz # For timezone handling
import logging

# Setup basic logging for this module
logger = logging.getLogger(__name__)
if not logger.handlers: # Avoid duplicate handlers if already configured by another module
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# Placeholder for functions to be implemented
def find_available_slots(
    busy_slots: list[dict],
    start_date: datetime,
    end_date: datetime,
    business_hours_start: time,
    business_hours_end: time,
    business_days: list[int],
    meeting_duration_minutes: int,
    slots_to_propose: int,
    target_timezone_str: str
) -> list[datetime]: # Returns a list of aware datetime objects representing start times of available slots

    available_slots = []
    try:
        target_tz = pytz.timezone(target_timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown timezone string: {target_timezone_str}")
        return [] # Or raise an error

    # Ensure start_date and end_date are in the target timezone for iteration
    # If they are naive, localize them. If they are aware, convert them.
    if start_date.tzinfo is None:
        current_check_time = target_tz.localize(start_date)
    else:
        current_check_time = start_date.astimezone(target_tz)

    if end_date.tzinfo is None:
        final_check_date = target_tz.localize(end_date)
    else:
        final_check_date = end_date.astimezone(target_tz)


    # Convert busy_slots strings to datetime objects and ensure they are timezone-aware (UTC, as from Google Calendar)
    parsed_busy_slots = []
    for busy in busy_slots:
        try:
            # Google Calendar API returns 'Z' for UTC. fromisoformat handles this correctly if Python >= 3.11
            # For older Python, .replace('Z', '+00:00') is a good shim.
            # Let's assume datetime.fromisoformat can handle 'Z' or use the replace shim for wider compatibility.
            # Ensure we are creating offset-aware datetimes that can be reliably converted.
            busy_start_str = busy['start']
            busy_end_str = busy['end']

            if busy_start_str.endswith('Z'):
                busy_start = datetime.fromisoformat(busy_start_str[:-1] + '+00:00')
            else:
                busy_start = datetime.fromisoformat(busy_start_str) # Expects offset info if not Z

            if busy_end_str.endswith('Z'):
                busy_end = datetime.fromisoformat(busy_end_str[:-1] + '+00:00')
            else:
                busy_end = datetime.fromisoformat(busy_end_str)

            # Ensure they are UTC for consistent comparison base before converting to target_tz for logic
            parsed_busy_slots.append({'start': busy_start.astimezone(pytz.utc), 'end': busy_end.astimezone(pytz.utc)})
        except (ValueError, KeyError) as ve:
            logger.warning(f"Could not parse busy slot: {busy}. Error: {ve}. Skipping.")
            continue

    parsed_busy_slots.sort(key=lambda x: x['start'])

    logger.info(f"Starting slot search from {current_check_time.isoformat()} to {final_check_date.isoformat()} in {target_timezone_str}")
    logger.info(f"Business hours: {business_hours_start.strftime('%H:%M')} - {business_hours_end.strftime('%H:%M')}. Meeting duration: {meeting_duration_minutes} min.")
    logger.debug(f"Parsed busy slots (UTC): [{' | '.join([s['start'].isoformat() + ' - ' + s['end'].isoformat() for s in parsed_busy_slots])}]")

    # Loop through each day
    while current_check_time.date() <= final_check_date.date() and len(available_slots) < slots_to_propose:
        date_to_check = current_check_time.date()
        logger.debug(f"Processing date: {date_to_check.strftime('%Y-%m-%d')}")

        # Check if current_check_time's day is a business day
        if date_to_check.weekday() not in business_days:
            logger.debug(f"Date {date_to_check.strftime('%Y-%m-%d')} is not a business day (weekday: {date_to_check.weekday()}).")
            current_check_time = target_tz.localize(datetime.combine(date_to_check + timedelta(days=1), business_hours_start))
            continue

        # Define the day's working window in target_tz
        day_start_dt = target_tz.localize(datetime.combine(date_to_check, business_hours_start))
        day_end_dt = target_tz.localize(datetime.combine(date_to_check, business_hours_end))

        # If current_check_time is effectively earlier than day_start_dt (e.g., it's from previous day's iteration or before business hours)
        if current_check_time < day_start_dt:
            current_check_time = day_start_dt
            logger.debug(f"Adjusted current_check_time to start of business hours: {current_check_time.isoformat()}")

        # Iterate through potential slots for the current day
        while current_check_time < day_end_dt and len(available_slots) < slots_to_propose:
            potential_slot_start = current_check_time
            potential_slot_end = potential_slot_start + timedelta(minutes=meeting_duration_minutes)

            logger.debug(f"Testing potential slot: {potential_slot_start.isoformat()} to {potential_slot_end.isoformat()}")

            if potential_slot_end > day_end_dt:
                logger.debug(f"Potential slot end {potential_slot_end.isoformat()} is after day end {day_end_dt.isoformat()}. Breaking from day.")
                break # Slot extends beyond business hours for the day

            is_free = True
            # Convert potential slot times to UTC for comparison with busy_slots
            potential_slot_start_utc = potential_slot_start.astimezone(pytz.utc)
            potential_slot_end_utc = potential_slot_end.astimezone(pytz.utc)

            for busy_period in parsed_busy_slots:
                # Check for overlap: (StartA < EndB) and (EndA > StartB)
                if potential_slot_start_utc < busy_period['end'] and \
                   potential_slot_end_utc > busy_period['start']:
                    is_free = False
                    # Advance current_check_time to the end of this busy period, converted to target_tz
                    current_check_time = busy_period['end'].astimezone(target_tz)
                    logger.debug(f"Slot overlaps with busy period. Advanced current_check_time to: {current_check_time.isoformat()}")
                    break

            if is_free:
                logger.info(f"Found available slot: {potential_slot_start.isoformat()}")
                available_slots.append(potential_slot_start) # Store as aware datetime in target_tz
                current_check_time = potential_slot_end # Move to the end of this found slot to check for next one
            elif not is_free and current_check_time <= potential_slot_start :
                # If busy slot logic advanced current_check_time, it's fine.
                # If it didn't (e.g. busy slot was before potential_slot_start but code didn't advance), ensure we move forward.
                # This case should ideally be handled by the busy_period['end'] advancement.
                # Adding a small increment if no advancement happened to prevent infinite loop on tricky overlaps.
                # This is a safeguard; ideally, the busy slot logic should correctly advance current_check_time.
                current_check_time = potential_slot_start + timedelta(minutes=15) # Default increment if stuck.
                logger.debug(f"Slot was not free, and current_check_time did not advance significantly. Advancing by 15min to {current_check_time.isoformat()}")


        # Move to the start of the next day
        current_check_time = target_tz.localize(datetime.combine(date_to_check + timedelta(days=1), business_hours_start))
        logger.debug(f"Moving to check next day: {current_check_time.isoformat()}")

    return available_slots


def format_slot_for_proposal(slot_datetime: datetime, target_timezone_str: str) -> str:
    # slot_datetime is an aware datetime object
    try:
        target_tz = pytz.timezone(target_timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown timezone string for formatting: {target_timezone_str}")
        return slot_datetime.strftime("%Y-%m-%d %H:%M %Z") # Fallback to original timezone

    local_slot_time = slot_datetime.astimezone(target_tz)
    # Example: "Tuesday, May 21st at 2:00 PM EDT" or "Next Tuesday at 2:00 PM"
    # Using strftime for a clear format. More "natural" formatting can be complex.
    # %A for full weekday name, %B for full month name, %d for day, %I for 12-hour, %M for minute, %p for AM/PM, %Z for timezone name
    return local_slot_time.strftime("%A, %B %d at %I:%M %p %Z")

if __name__ == '__main__':
    logger.info("Running scheduling_logic.py tests...")

    # Sample data for testing
    test_busy_slots = [
        {'start': '2024-05-21T10:00:00Z', 'end': '2024-05-21T11:00:00Z'}, # Tue 10-11 UTC
        {'start': '2024-05-21T14:00:00Z', 'end': '2024-05-21T15:30:00Z'}, # Tue 14-15:30 UTC
        {'start': '2024-05-22T09:00:00Z', 'end': '2024-05-22T09:30:00Z'}, # Wed 9-9:30 UTC (early meeting in NY time)
        {'start': '2024-05-23T18:00:00Z', 'end': '2024-05-23T19:00:00Z'}, # Thu 18-19 UTC (late meeting in NY time)
    ]

    # Define scheduling parameters
    tz_str = "America/New_York"
    ny_tz = pytz.timezone(tz_str)

    # Start checking from tomorrow in NY time
    # Ensure start_datetime is aware for the function
    start_dt_naive = datetime.combine(datetime.now().date() + timedelta(days=1), time(0,0))
    start_dt_aware = ny_tz.localize(start_dt_naive)

    end_dt_aware = start_dt_aware + timedelta(days=7) # Check for the next 7 days

    bus_hours_start = time(9, 0)
    bus_hours_end = time(17, 0)
    bus_days = [0, 1, 2, 3, 4] # Mon-Fri
    meeting_mins = 30
    num_slots_to_propose = 5

    logger.info(f"Test: Finding {num_slots_to_propose} slots of {meeting_mins} min duration.")
    logger.info(f"Test: Timezone: {tz_str}")
    logger.info(f"Test: Checking from {start_dt_aware.strftime('%Y-%m-%d %H:%M %Z')} to {end_dt_aware.strftime('%Y-%m-%d %H:%M %Z')}")
    logger.info(f"Test: Business Hours: {bus_hours_start.strftime('%H:%M')} - {bus_hours_end.strftime('%H:%M')}")
    logger.info(f"Test: Business Days (0=Mon): {bus_days}")


    available_slots = find_available_slots(
        busy_slots=test_busy_slots,
        start_date=start_dt_aware,
        end_date=end_dt_aware,
        business_hours_start=bus_hours_start,
        business_hours_end=bus_hours_end,
        business_days=bus_days,
        meeting_duration_minutes=meeting_mins,
        slots_to_propose=num_slots_to_propose,
        target_timezone_str=tz_str
    )

    if available_slots:
        logger.info(f"\nFound {len(available_slots)} available slots:")
        for slot_start_time in available_slots:
            # The slot_start_time is already in target_tz from find_available_slots
            logger.info(f"  Raw: {slot_start_time.isoformat()} | Formatted: {format_slot_for_proposal(slot_start_time, tz_str)}")
    else:
        logger.info("\nNo available slots found for the given criteria.")

    # Test with no busy slots
    logger.info("\nTest: Finding slots with NO busy_slots:")
    available_slots_no_busy = find_available_slots(
        busy_slots=[],
        start_date=start_dt_aware,
        end_date=start_dt_aware + timedelta(days=2), # Shorter window for this test
        business_hours_start=bus_hours_start,
        business_hours_end=bus_hours_end,
        business_days=bus_days,
        meeting_duration_minutes=60, # 1 hour meetings
        slots_to_propose=5,
        target_timezone_str=tz_str
    )
    if available_slots_no_busy:
        logger.info(f"Found {len(available_slots_no_busy)} slots (no busy times):")
        for slot_start_time in available_slots_no_busy:
            logger.info(f"  Raw: {slot_start_time.isoformat()} | Formatted: {format_slot_for_proposal(slot_start_time, tz_str)}")
    else:
        logger.info("No available slots found (no busy times case).")

    # Test with a weekend start date
    logger.info("\nTest: Start date on a weekend")
    # Find a Saturday
    saturday_start_naive = datetime.combine(datetime.now().date(), time(9,0))
    while saturday_start_naive.weekday() != 5: # 5 is Saturday
        saturday_start_naive += timedelta(days=1)
    saturday_start_aware = ny_tz.localize(saturday_start_naive)

    available_slots_weekend_start = find_available_slots(
        busy_slots=[],
        start_date=saturday_start_aware,
        end_date=saturday_start_aware + timedelta(days=3),
        business_hours_start=bus_hours_start,
        business_hours_end=bus_hours_end,
        business_days=bus_days, # Mon-Fri
        meeting_duration_minutes=meeting_mins,
        slots_to_propose=2,
        target_timezone_str=tz_str
    )
    if available_slots_weekend_start:
        logger.info(f"Found {len(available_slots_weekend_start)} slots (weekend start):")
        for slot in available_slots_weekend_start:
            assert slot.weekday() in bus_days # Ensure slots are on business days
            logger.info(f"  Raw: {slot.isoformat()} | Formatted: {format_slot_for_proposal(slot, tz_str)}")
    else:
        logger.info("No slots found for weekend start test (as expected if next business day is full or out of range).")
