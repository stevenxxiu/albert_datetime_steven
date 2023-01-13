from datetime import datetime, timedelta, timezone
from typing import List

from albert import Action, Item, Query, QueryHandler, setClipboardText  # pylint: disable=import-error


md_iid = '0.5'
md_version = '1.0'
md_name = 'DateTime Steven'
md_description = 'Convert between datetime strings and timestamps.'
md_url = 'https://github.com/stevenxxiu/albert_datetime_steven'
md_maintainers = '@stevenxxiu'

TRIGGER = 'dt'
ICON_PATH = '/usr/share/icons/elementary/categories/64/preferences-system-time.svg'

UNITS = ['seconds', 'milliseconds', 'microseconds', 'nanoseconds']

UNIX_EPOCH = datetime.fromtimestamp(0, tz=timezone.utc)


def parse_unix_timestamp(timestamp: int, max_year: int = 9999) -> (datetime, int, str):
    '''
    :param timestamp:
    :param max_year: Find the smallest resolution we can so `timestamp` is before this.
    :return: `(dt, nanoseconds, unit)`
    '''
    max_dt = datetime(max_year, 12, 31, tzinfo=timezone.utc)
    for power in 0, 3, 6, 9:
        seconds = timestamp // 10**power
        nanoseconds = 10 ** (9 - power) * (timestamp % (10**power))
        try:
            dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
            if dt <= max_dt or power == 9:
                unit = UNITS[power // 3]
                return dt, nanoseconds, unit
        except (ValueError, OverflowError, OSError):
            continue
    raise ValueError('Timestamp is too large or too small')


LOCAL_TZINFO = datetime.now().astimezone().tzinfo


def format_unix_timestamp(dt: datetime, nanoseconds: int) -> List[str]:
    fmt = f'%Y-%m-%d %H:%M:%S:{nanoseconds:09d} %z'
    return [
        dt.astimezone(LOCAL_TZINFO).strftime(fmt),
        dt.astimezone(timezone.utc).strftime(fmt),
    ]


NFTS_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def parse_ntfs_timestamp(timestamp: int) -> (datetime, int):
    ticks = timestamp % 10**7
    seconds = timestamp // 10**7
    dt = NFTS_EPOCH + timedelta(seconds=seconds)
    return dt, ticks


def format_ntfs_timestamp(dt: datetime, ticks: int) -> List[str]:
    fmt = f'%Y-%m-%d %H:%M:%S:{ticks:07d} %z'
    return [
        dt.astimezone(LOCAL_TZINFO).strftime(fmt),
        dt.astimezone(timezone.utc).strftime(fmt),
    ]


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
        return '(NTFS|LDAP)? <epoch>'

    def handleQuery(self, query: Query) -> None:
        terms = query.string.strip().split()

        dt_strs, unit = [], ''

        try:
            if len(terms) == 2 and terms[0].upper() in ('NTFS', 'LDAP'):
                timestamp = int(terms[1])
                dt, ticks = parse_ntfs_timestamp(timestamp)
                dt_strs = format_ntfs_timestamp(dt, ticks)
                unit = '100 nanoseconds'
            elif len(terms) == 1:
                timestamp = int(query.string)
                dt, nanoseconds, unit = parse_unix_timestamp(timestamp)
                dt_strs = format_unix_timestamp(dt, nanoseconds)
        except ValueError as e:
            query.add(
                Item(
                    id=md_name,
                    text=str(e),
                    icon=[ICON_PATH],
                )
            )
            return

        for dt_str in dt_strs:
            query.add(
                Item(
                    id=md_name,
                    text=dt_str,
                    subtext=f'as {unit}',
                    icon=[ICON_PATH],
                    actions=[Action(md_name, 'Copy', lambda value_=dt_str: setClipboardText(value_))],
                )
            )
