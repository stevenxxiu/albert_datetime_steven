import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytz
from albert import Action, Item, Query, QueryHandler, setClipboardText  # pylint: disable=import-error


md_iid = '0.5'
md_version = '1.0'
md_name = 'DateTime Steven'
md_description = 'Convert between datetime strings and timestamps.'
md_url = 'https://github.com/stevenxxiu/albert_datetime_steven'
md_maintainers = '@stevenxxiu'
md_lib_dependencies = ['pytz']

TRIGGER = 'dt'
ICON_PATH = str(Path(__file__).parent / 'icons/datetime.png')

UNITS = ['seconds', 'milliseconds', 'microseconds', 'nanoseconds']
UNITS_ABBREV = ['s', 'ms', 'us', 'ns']

UNIX_EPOCH = datetime.fromtimestamp(0, tz=timezone.utc)


def guess_unix_unit(timestamp: int, max_year: int = 9999) -> int:
    '''
    :param timestamp:
    :param max_year: Find the smallest resolution we can so `timestamp` is before this.
    :return: `power`
    '''
    max_dt = datetime(max_year, 12, 31, tzinfo=timezone.utc)
    for power in 0, 3, 6, 9:
        seconds = timestamp // 10**power
        try:
            dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
            if dt <= max_dt or power == 9:
                return power
        except (ValueError, OverflowError, OSError):
            continue
    raise ValueError('datetime value out of range')


def parse_unix_timestamp(timestamp: int, power: int) -> (datetime, int, str):
    seconds = timestamp // 10**power
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    nanoseconds = 10 ** (9 - power) * (timestamp % (10**power))
    unit = UNITS[power // 3]
    return dt, nanoseconds, unit


LOCAL_TZINFO = datetime.now().astimezone().tzinfo


def format_unix_timestamp(dt: datetime, nanoseconds: int) -> list[str]:
    fmt = f'%Y-%m-%d %H:%M:%S:{nanoseconds:09d} %z'
    return [
        dt.astimezone(LOCAL_TZINFO).strftime(fmt),
        dt.astimezone(timezone.utc).strftime(fmt),
    ]


def to_unix_timestamp(dt: datetime, nanoseconds: int) -> int:
    return int(dt.timestamp()) * 10**9 + nanoseconds


NFTS_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def parse_ntfs_timestamp(timestamp: int) -> (datetime, int):
    ticks = timestamp % 10**7
    seconds = timestamp // 10**7
    dt = NFTS_EPOCH + timedelta(seconds=seconds)
    return dt, ticks


def format_ntfs_timestamp(dt: datetime, ticks: int) -> list[str]:
    fmt = f'%Y-%m-%d %H:%M:%S:{ticks:07d} %z'
    return [
        dt.astimezone(LOCAL_TZINFO).strftime(fmt),
        dt.astimezone(timezone.utc).strftime(fmt),
    ]


def to_ntfs_timestamp(dt: datetime, nanoseconds: int) -> int:
    return int((dt - NFTS_EPOCH).total_seconds()) * 10**7 + nanoseconds // 100


class Plugin(QueryHandler):
    def id(self) -> str:
        return __name__

    def name(self) -> str:
        return md_name

    def description(self) -> str:
        return md_description

    def defaultTrigger(self) -> str:
        return TRIGGER

    def synopsis(self) -> str:
        return '(NT|NTFS|LDAP) <v>|<v>[unit]|<%Y-%m-%d [%H:%M:%S:[%NS]] [%z]>'

    @staticmethod
    def parse_epoch(query_str: str, query: Query) -> bool:
        dt_strs, unit = [], None

        try:
            matches = re.match(r'(?:NT|NTFS|LDAP)\s+(\d+)$', query_str, re.IGNORECASE)
            if matches:
                (timestamp_str,) = matches.groups()
                timestamp = int(timestamp_str)
                dt, ticks = parse_ntfs_timestamp(timestamp)
                dt_strs = format_ntfs_timestamp(dt, ticks)
                unit = '100 nanoseconds'

            matches = re.match(r'(\d+)\s*(s|ms|us|ns)?$', query_str)
            if matches:
                timestamp_str, unit_abbrev = matches.groups()
                timestamp = int(timestamp_str)
                if unit_abbrev:
                    power = 3 * UNITS_ABBREV.index(unit_abbrev)
                else:
                    power = guess_unix_unit(timestamp)
                dt, nanoseconds, unit = parse_unix_timestamp(timestamp, power)
                dt_strs = format_unix_timestamp(dt, nanoseconds)
        except (OverflowError, ValueError) as e:
            query.add(
                Item(
                    id=f'{md_name}/{e}',
                    text=str(e),
                    icon=[ICON_PATH],
                )
            )
            return True

        for dt_str in dt_strs:
            query.add(
                Item(
                    id=f'{md_name}/{dt_str}',
                    text=dt_str,
                    subtext=f'as {unit}',
                    icon=[ICON_PATH],
                    actions=[Action(md_name, 'Copy', lambda value_=dt_str: setClipboardText(value_))],
                )
            )
        return bool(dt_strs)

    RE_DATETIME: re.Pattern = re.compile(
        r'(?P<year>\d{1,4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})'
        r'(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2}):(?P<second>\d{1,2})(:(?P<nanosecond>\d{1,9}))?)?'
        r'(?:\s+(?:'
        r'((?P<tz_fixed_sign>[+-])(?P<tz_fixed_hours>\d{2}):?(?P<tz_fixed_minutes>\d{2}))|'
        fr'(?P<tz_named>{"|".join(timezone for timezone in pytz.all_timezones)})'
        r'))?',
        re.IGNORECASE,
    )

    @classmethod
    def parse_datetime(cls, query_str: str, query: Query) -> bool:
        matches = cls.RE_DATETIME.match(query_str)
        if not matches:
            return False
        matches_dict = matches.groupdict()
        dt = datetime(
            int(matches_dict['year']),
            int(matches_dict['month']),
            int(matches_dict['day']),
        )
        if matches_dict['hour'] is not None:
            dt = dt.replace(
                hour=int(matches_dict['hour']), minute=int(matches_dict['minute']), second=int(matches_dict['second'])
            )
        nanosecond = int(matches_dict['nanosecond'] or '0')
        if matches_dict['tz_fixed_sign'] is not None:
            input_timezone = timedelta(
                hours=int(matches_dict['tz_fixed_hours']), minutes=int(matches_dict['tz_fixed_minutes'])
            )
            if matches_dict['tz_fixed_sign'] == '-':
                input_timezone = -input_timezone
            dt = dt.astimezone(timezone(input_timezone))
        elif matches_dict['tz_named'] is not None:
            dt = pytz.timezone(matches_dict['tz_named']).localize(dt)
        else:
            dt = dt.replace(tzinfo=timezone.utc)

        timestamp_str = str(to_unix_timestamp(dt, nanosecond))
        query.add(
            Item(
                id=f'{md_name}/unix',
                text=timestamp_str,
                subtext='Unix',
                icon=[ICON_PATH],
                actions=[Action(md_name, 'Copy', lambda value_=timestamp_str: setClipboardText(value_))],
            )
        )

        timestamp_str = str(to_ntfs_timestamp(dt, nanosecond // 100))
        query.add(
            Item(
                id=f'{md_name}/ntfs',
                text=timestamp_str,
                subtext='NTFS/LDAP',
                icon=[ICON_PATH],
                actions=[Action(md_name, 'Copy', lambda value_=timestamp_str: setClipboardText(value_))],
            )
        )

        return True

    def handleQuery(self, query: Query) -> None:
        query_str = query.string.strip()
        if self.parse_epoch(query_str, query):
            return
        if self.parse_datetime(query_str, query):
            return
