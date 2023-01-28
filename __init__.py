import enum
import itertools
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytz
from albert import Action, Item, Query, QueryHandler, setClipboardText  # pylint: disable=import-error


md_iid = '0.5'
md_version = '1.0'
md_name = 'DateTime Steven'
md_description = 'Convert between datetime strings and timestamps'
md_url = 'https://github.com/stevenxxiu/albert_datetime_steven'
md_maintainers = '@stevenxxiu'
md_lib_dependencies = ['pytz']

TRIGGER = 'dt'
ICON_PATH = str(Path(__file__).parent / 'icons/datetime.png')

UNITS = ['seconds', 'milliseconds', 'microseconds', 'nanoseconds']
UNITS_ABBREV = ['s', 'ms', 'us', 'ns']

UNIX_EPOCH = datetime.fromtimestamp(0, tz=timezone.utc)


class TimeStr(enum.IntEnum):
    DATE = enum.auto()
    NTFS_DATE = enum.auto()
    UNIX_TIMESTAMP = enum.auto()
    NTFS_TIMESTAMP = enum.auto()


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
        return f'{TRIGGER} '

    def synopsis(self) -> str:
        return '(NT|NTFS|LDAP) <v>|<v>[unit]|<%Y-%m-%d [%H:%M:%S:[%NS|%NTFS_TICKS]] [%z]>'

    @staticmethod
    def add_items(dt: datetime, nanoseconds: int, input_type: str, types: [TimeStr], query: Query) -> None:
        item_defs = []
        for timestamp_type in types:
            match timestamp_type:
                case TimeStr.DATE:
                    item_defs.extend(zip(format_unix_timestamp(dt, nanoseconds), itertools.repeat('Date')))
                case TimeStr.NTFS_DATE:
                    item_defs.extend(
                        zip(format_ntfs_timestamp(dt, nanoseconds // 100), itertools.repeat('NTFS/LDAP date'))
                    )
                case TimeStr.UNIX_TIMESTAMP:
                    item_defs.append((str(to_unix_timestamp(dt, nanoseconds)), 'Unix timestamp'))
                case TimeStr.NTFS_TIMESTAMP:
                    item_defs.append((str(to_ntfs_timestamp(dt, nanoseconds)), 'NTFS/LDAP timestamp'))

        for output_str, output_str_type in item_defs:
            query.add(
                Item(
                    id=f'{md_name}/{output_str}',
                    text=output_str,
                    subtext=f'{output_str_type} (input as {input_type})',
                    icon=[ICON_PATH],
                    actions=[Action(md_name, 'Copy', lambda value_=output_str: setClipboardText(value_))],
                )
            )

        # Copy all
        headings = [output_str_type for _output_str, output_str_type in item_defs]
        max_heading_len = max(len(heading) for heading in headings)
        all_output_str = (
            f'With input as {input_type}\n'
            + '\n'.join(
                [
                    f'{heading:<{max_heading_len}}    {output_str}'
                    for heading, (output_str, _output_str_type) in zip(headings, item_defs)
                ]
            )
            + '\n'
        )
        query.add(
            Item(
                id=f'{md_name}/copy_all',
                text='Copy All',
                icon=[ICON_PATH],
                actions=[Action(md_name, 'Copy', lambda: setClipboardText(all_output_str))],
            )
        )

    @classmethod
    def parse_epoch(cls, query_str: str, query: Query) -> bool:
        try:
            matches = re.match(r'(?:NT|NTFS|LDAP)\s+(\d+)$', query_str, re.IGNORECASE)
            if matches:
                (timestamp_str,) = matches.groups()
                timestamp = int(timestamp_str)
                dt, ticks = parse_ntfs_timestamp(timestamp)
                cls.add_items(
                    dt,
                    ticks * 100,
                    'NTFS time in 100 nanoseconds',
                    [TimeStr.NTFS_DATE, TimeStr.DATE, TimeStr.UNIX_TIMESTAMP],
                    query,
                )
                return True

            matches = re.match(r'(\d+)\s*(s|ms|us|ns)?$', query_str)
            if matches:
                timestamp_str, unit_abbrev = matches.groups()
                timestamp = int(timestamp_str)
                if unit_abbrev:
                    power = 3 * UNITS_ABBREV.index(unit_abbrev)
                else:
                    power = guess_unix_unit(timestamp)
                dt, nanoseconds, unit = parse_unix_timestamp(timestamp, power)
                cls.add_items(
                    dt,
                    nanoseconds,
                    f'Unix time in {unit}',
                    [TimeStr.DATE, TimeStr.NTFS_DATE, TimeStr.UNIX_TIMESTAMP, TimeStr.NTFS_TIMESTAMP],
                    query,
                )
                return True
        except (OverflowError, ValueError) as e:
            query.add(
                Item(
                    id=f'{md_name}/{e}',
                    text=str(e),
                    icon=[ICON_PATH],
                )
            )
            return True
        return False

    RE_DATETIME: re.Pattern = re.compile(
        # Date
        r'(?P<year>\d{1,4})-(?P<month>\d{2})-(?P<day>\d{2})'
        # Time
        r'(?:\s+'
        r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(:(?:(?P<nanosecond>\d{9})|(?P<ntfs_ticks>\d{7})))?'
        r')?'
        # Timezone
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

        nanoseconds = 0
        if matches_dict['nanosecond'] is not None:
            nanoseconds = int(matches_dict['nanosecond'])
        elif matches_dict['ntfs_ticks'] is not None:
            nanoseconds = int(matches_dict['ntfs_ticks']) * 100

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

        if matches_dict['ntfs_ticks'] is not None:
            cls.add_items(
                dt,
                nanoseconds,
                'date',
                [TimeStr.NTFS_TIMESTAMP, TimeStr.UNIX_TIMESTAMP, TimeStr.NTFS_DATE, TimeStr.DATE],
                query,
            )
        else:
            cls.add_items(
                dt,
                nanoseconds,
                'date',
                [TimeStr.UNIX_TIMESTAMP, TimeStr.NTFS_TIMESTAMP, TimeStr.DATE, TimeStr.NTFS_DATE],
                query,
            )
        return True

    def handleQuery(self, query: Query) -> None:
        query_str = query.string.strip()
        if self.parse_epoch(query_str, query):
            return
        if self.parse_datetime(query_str, query):
            return
