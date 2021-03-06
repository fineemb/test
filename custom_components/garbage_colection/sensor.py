"""Sensor platform for garbage_collection."""
from homeassistant.helpers.entity import Entity
import logging
from datetime import datetime, date, timedelta
from homeassistant.core import HomeAssistant, State

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)
THROTTLE_INTERVAL = timedelta(seconds=60)
ATTR_NEXT_DATE = "next_date"
ATTR_DAYS = "days"

from homeassistant.const import CONF_NAME, WEEKDAYS, CONF_ENTITIES
from .const import (
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    CONF_SENSOR,
    CONF_ENABLED,
    CONF_FREQUENCY,
    CONF_ICON_NORMAL,
    CONF_ICON_TODAY,
    CONF_ICON_TOMORROW,
    CONF_VERBOSE_STATE,
    CONF_FIRST_MONTH,
    CONF_LAST_MONTH,
    CONF_COLLECTION_DAYS,
    CONF_WEEKDAY_ORDER_NUMBER,
    CONF_DATE,
    CONF_EXCLUDE_DATES,
    CONF_INCLUDE_DATES,
    CONF_PERIOD,
    CONF_FIRST_WEEK,
    CONF_SENSORS,
    MONTH_OPTIONS,
    FREQUENCY_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):  # pylint: disable=unused-argument
    """Setup sensor platform."""
    async_add_entities([GarbageCollection(hass, discovery_info)], True)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup sensor platform."""
    async_add_devices([GarbageCollection(hass, config_entry.data)], True)


def nth_weekday_date(n, date_of_month, collection_day):
    first_of_month = datetime(date_of_month.year, date_of_month.month, 1).date()
    month_starts_on = first_of_month.weekday()
    # 1st of the month is before the day of collection
    # (so 1st collection week the week when month starts)
    if collection_day >= month_starts_on:
        return first_of_month + timedelta(
            days=collection_day - month_starts_on + (n - 1) * 7
        )
    else:  # Next week
        return first_of_month + timedelta(
            days=7 - month_starts_on + collection_day + (n - 1) * 7
        )


def to_dates(dates):
    # Convert list of text to dates, if not already dates
    converted = []
    for day in dates:
        if type(day) == date:
            converted.append(day)
        else:
            try:
                converted.append(datetime.strptime(day, "%Y-%m-%d").date())
            except ValueError:
                continue
    return converted


class GarbageCollection(Entity):
    """GarbageCollection Sensor class."""

    def __init__(self, hass, config):
        self.config = config
        self.__name = config.get(CONF_NAME)
        self.__frequency = config.get(CONF_FREQUENCY)
        self.__collection_days = config.get(CONF_COLLECTION_DAYS)
        first_month = config.get(CONF_FIRST_MONTH)
        if first_month in MONTH_OPTIONS:
            self.__first_month = MONTH_OPTIONS.index(first_month) + 1
        else:
            self.__first_month = 1
        last_month = config.get(CONF_LAST_MONTH)
        if last_month in MONTH_OPTIONS:
            self.__last_month = MONTH_OPTIONS.index(last_month) + 1
        else:
            self.__last_month = 12
        self.__monthly_day_order_numbers = config.get(CONF_WEEKDAY_ORDER_NUMBER)
        self.__include_dates = to_dates(config.get(CONF_INCLUDE_DATES, []))
        self.__exclude_dates = to_dates(config.get(CONF_EXCLUDE_DATES, []))
        self.__period = config.get(CONF_PERIOD)
        self.__first_week = config.get(CONF_FIRST_WEEK)
        self.__next_date = None
        self.__today = None
        self.__days = 0
        self.__date = config.get(CONF_DATE)
        self.__entities = config.get(CONF_ENTITIES)
        self.__verbose_state = config.get(CONF_VERBOSE_STATE)
        self.__state = "" if bool(self.__verbose_state) else 2
        self.__icon_normal = config.get(CONF_ICON_NORMAL)
        self.__icon_today = config.get(CONF_ICON_TODAY)
        self.__icon_tomorrow = config.get(CONF_ICON_TOMORROW)
        self.__icon = self.__icon_normal
        self.__today = "Today"
        self.__tomorrow = "Tomorrow"

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return self.config.get("unique_id", None)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config.get("unique_id", None))},
            "name": self.config.get("name"),
            "manufacturer": "Garbage Collection",
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.__name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.__state

    @property
    def icon(self):
        return self.__icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        res = {}
        res[ATTR_NEXT_DATE] = (
            None
            if self.__next_date is None
            else datetime(
                self.__next_date.year, self.__next_date.month, self.__next_date.day
            )
        )
        res[ATTR_DAYS] = self.__days
        return res

    def date_inside(self, dat):
        month = dat.month
        if self.__first_month <= self.__last_month:
            return bool(month >= self.__first_month and month <= self.__last_month)
        else:
            return bool(month <= self.__last_month or month >= self.__first_month)

    def find_candidate_date(self, day1):
        """Find the next possible date starting from day1,
        only based on calendar, not lookimg at include/exclude days"""
        week = day1.isocalendar()[1]
        weekday = day1.weekday()
        year = day1.year
        if self.__frequency in ["weekly", "even-weeks", "odd-weeks", "every-n-weeks"]:
            # Everything except montthly
            # convert to every-n-weeks
            if self.__frequency == "weekly":
                period = 1
                first_week = 1
            elif self.__frequency == "even-weeks":
                period = 2
                first_week = 2
            elif self.__frequency == "odd-weeks":
                period = 2
                first_week = 1
            else:
                period = self.__period
                first_week = self.__first_week
            offset = -1
            if (week - first_week) % period == 0:  # Collection this week
                for day_name in self.__collection_days:
                    day_index = WEEKDAYS.index(day_name)
                    if day_index >= weekday:  # Collection still did not happen
                        offset = day_index - weekday
                        break
            if offset == -1:  # look in following weeks
                in_weeks = period - (week - first_week) % period
                offset = (
                    7 * in_weeks - weekday + WEEKDAYS.index(self.__collection_days[0])
                )
            return day1 + timedelta(days=offset)
        elif self.__frequency == "monthly":
            # Monthly
            for monthly_day_order_number in self.__monthly_day_order_numbers:
                candidate_date = nth_weekday_date(
                    monthly_day_order_number,
                    day1,
                    WEEKDAYS.index(self.__collection_days[0]),
                )
                # date is today or in the future -> we have the date
                if candidate_date >= day1:
                    return candidate_date
            if day1.month == 12:
                next_collection_month = datetime(year + 1, 1, 1).date()
            else:
                next_collection_month = datetime(year, day1.month + 1, 1).date()
            return nth_weekday_date(
                self.__monthly_day_order_numbers[0],
                next_collection_month,
                WEEKDAYS.index(self.__collection_days[0]),
            )
        elif self.__frequency == "annual":
            # Annual
            if self.__date is None:
                _LOGGER.error(
                    "(%s) Please configure the date for annual collection frequency.",
                    self.__name,
                )
                return None
            conf_date = datetime.strptime(self.__date, "%m/%d").date()
            candidate_date = datetime(year, conf_date.month, conf_date.day).date()
            if candidate_date < day1:
                candidate_date = datetime(
                    year + 1, conf_date.month, conf_date.day
                ).date()
            return candidate_date
        elif self.__frequency == "group":
            if self.__entities is None:
                _LOGGER.error("(%s) Please add entities for the group.", self.__name)
                return None
            candidate_date = None
            for entity in self.__entities:
                d = self.hass.states.get(entity).attributes.get(ATTR_NEXT_DATE).date()
                if candidate_date is None or d < candidate_date:
                    candidate_date = d
            return candidate_date
        else:
            _LOGGER.debug(f"({self.__name}) Unknown frequency {self.__frequency}")
            return None

    def get_next_date(self, day1):
        """Find the next date starting from day1.
        Looks at include and exclude days"""
        first_day = day1
        i = 0
        while True:
            next_date = self.find_candidate_date(first_day)
            include_dates = list(
                filter(lambda date: date >= day1, self.__include_dates)
            )
            if len(include_dates) > 0 and include_dates[0] < next_date:
                next_date = include_dates[0]
            if next_date not in self.__exclude_dates:
                break
            else:
                first_day = next_date + timedelta(days=1)
            i += 1
            if i > 365:
                _LOGGER.error("(%s) Cannot find any suitable date", self.__name)
                next_date = None
                break
        return next_date

    async def async_update(self):
        """Get the latest data and updates the states."""
        today = datetime.now().date()
        if self.__today is not None and self.__today == today:
            # _LOGGER.debug(
            #     "(%s) Skipping the update, already did it today",
            #     self.__name)
            return
        _LOGGER.debug("(%s) Calling update", self.__name)
        today = datetime.now().date()
        year = today.year
        month = today.month
        self.__today = today
        if self.date_inside(today):
            next_date = self.get_next_date(today)
            if next_date is not None:
                next_date_year = next_date.year
                if not self.date_inside(next_date):
                    if self.__first_month <= self.__last_month:
                        next_year = datetime(
                            next_date_year + 1, self.__first_month, 1
                        ).date()
                        next_date = self.get_next_date(next_year)
                        _LOGGER.debug(
                            "(%s) Did not find the date this year, "
                            "lookig at next year",
                            self.__name,
                        )
                    else:
                        next_year = datetime(
                            next_date_year, self.__first_month, 1
                        ).date()
                        next_date = self.get_next_date(next_year)
                        _LOGGER.debug(
                            "(%s) Arrived to the end of date range, "
                            "starting at first month",
                            self.__name,
                        )
        else:
            if self.__first_month <= self.__last_month and month > self.__last_month:
                next_year = datetime(year + 1, self.__first_month, 1).date()
                next_date = self.get_next_date(next_year)
                _LOGGER.debug(
                    "(%s) Date outside range, lookig at next year", self.__name
                )
            else:
                next_year = datetime(year, self.__first_month, 1).date()
                next_date = self.get_next_date(next_year)
                _LOGGER.debug(
                    "(%s) Current date is outside of the range, "
                    "starting from first month",
                    self.__name,
                )
        self.__next_date = next_date
        if next_date is not None:
            self.__days = (self.__next_date - today).days
            next_date_txt = self.__next_date.strftime("%d-%b-%Y")
            _LOGGER.debug(
                "(%s) Found next date: %s, that is in %d days",
                self.__name,
                next_date_txt,
                self.__days,
            )
            if self.__days > 1:
                if bool(self.__verbose_state):
                    self.__state = f"on {next_date_txt}, in {self.__days} days"
                else:
                    self.__state = 2
                self.__icon = self.__icon_normal
            else:
                if self.__days == 0:
                    if bool(self.__verbose_state):
                        self.__state = self.__today
                    else:
                        self.__state = self.__days
                    self.__icon = self.__icon_today
                elif self.__days == 1:
                    if bool(self.__verbose_state):
                        self.__state = self.__tomorrow
                    else:
                        self.__state = self.__days
                    self.__icon = self.__icon_tomorrow
        else:
            self.__days = None
