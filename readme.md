# Albert Launcher Datetime Extension
Converts to and from *Unix*/*NTFS* epochs.

Automatically guesses the unit if this isn't supplied.

Usage examples:

- `dt 946771200`
- `dt 946771200000ms`
- `dt nt 125912448000000000`
- `dt 2000-01-02`
- `dt 2000-01-02 -0130`
- `dt 2000-01-02 -01:30`
- `dt 2000-01-02 +01:30`
- `dt 2000-01-02 03:04:05`
- `dt 2000-01-02 03:04:05:1234567`
- `dt 2000-01-02 03:04:05:1234567 australia/melbourne`
- `dt 2000-01-02 03:04:05:1234567 +1100`
- `dt 2000-01-02 03:04:05:1234567 +11:00`

## Install
To install, copy or symlink this directory to `~/.local/share/albert/python/plugins/datetime_steven/`.

## Development Setup
To setup the project for development, run:

    $ cd datetime_steven/
    $ pre-commit install --hook-type pre-commit --hook-type commit-msg

To lint and format files, run:

    $ pre-commit run --all-files
