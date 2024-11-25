""" 
MIT License

Copyright (c) 2024 Himangshu Saikia

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""



import datetime

from typing import Any, Iterable, Optional, Sequence


def format_duration(duration: int) -> str:
    minutes, seconds = divmod(duration / 1000, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
    else:
        return f"{int(minutes)}:{int(seconds):02d}"


def fix_url(self, url: str) -> str:
    return url.replace("<", "").replace(">", "")


def truncate_string(value, max_length=128, suffix="..."):
    string_value = str(value)
    string_truncated = string_value[
        : min(len(string_value), (max_length - len(suffix)))
    ]
    suffix = suffix if len(string_value) > max_length else ""
    return string_truncated + suffix


def format_seconds(seconds: float, *, friendly: bool = False) -> str:
    seconds = round(seconds)

    minute, second = divmod(seconds, 60)
    hour, minute = divmod(minute, 60)
    day, hour = divmod(hour, 24)

    days, hours, minutes, seconds = (
        round(day),
        round(hour),
        round(minute),
        round(second),
    )

    if friendly:
        day = f"{days}d " if days != 0 else ""
        hour = f"{hours}h " if hours != 0 or days != 0 else ""
        minsec = f"{minutes}m {seconds}s"
        return f"{day}{hour}{minsec}"
    day = f"{days:02d}:" if days != 0 else ""
    hour = f"{hours:02d}:" if hours != 0 or days != 0 else ""
    minsec = f"{minutes:02d}:{seconds:02d}"
    return f"{day}{hour}{minsec}"


class plural:

    def __init__(self, value: int):
        self.value: int = value

    def __format__(self, format_spec: str) -> str:

        v = self.value
        singular, sep, plural = format_spec.partition("|")
        plural = plural or f"{singular}s"
        if abs(v) != 1:
            return f"{v} {plural}"
        return f"{v} {singular}"


def human_join(seq: Sequence[str], delim: str = ", ", final: str = "or") -> str:
    size = len(seq)
    if size == 0:
        return ""

    if size == 1:
        return seq[0]

    if size == 2:
        return f"{seq[0]} {final} {seq[1]}"

    return delim.join(seq[:-1]) + f" {final} {seq[-1]}"


class TabularData:

    def __init__(self):
        self._widths: list[int] = []
        self._columns: list[str] = []
        self._rows: list[list[str]] = []

    def set_columns(self, columns: list[str]):
        self._columns = columns
        self._widths = [len(c) + 2 for c in columns]

    def add_row(self, row: Iterable[Any]) -> None:
        rows = [str(r) for r in row]
        self._rows.append(rows)
        for index, element in enumerate(rows):
            width = len(element) + 2
            if width > self._widths[index]:
                self._widths[index] = width

    def add_rows(self, rows: Iterable[Iterable[Any]]) -> None:
        for row in rows:
            self.add_row(row)

    def render(self) -> str:
        """Renders a table in rST format.

        Example:

        +------------+--------+
        |    Name    |  Age   |
        +------------+--------+
        |  Robo      |   2    |
        |  Himangshu |   17   |
        +------------+--------+
        """

        sep = "+".join("-" * w for w in self._widths)
        sep = f"+{sep}+"

        to_draw = [sep]

        def get_entry(d):
            elem = "|".join(f"{e:^{self._widths[i]}}" for i, e in enumerate(d))
            return f"|{elem}|"

        to_draw.append(get_entry(self._columns))
        to_draw.append(sep)

        for row in self._rows:
            to_draw.append(get_entry(row))

        to_draw.append(sep)
        return "\n".join(to_draw)


def format_dt(dt: datetime.datetime, style: Optional[str] = None) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    if style is None:
        return f"<t:{int(dt.timestamp())}>"
    return f"<t:{int(dt.timestamp())}:{style}>"


def tick(opt: Optional[bool], /) -> str:
    lookup = {
        True: "<:greentick:1172524936292741131>",
        False: "<:xsign:1172524698081427477>",
        None: "<:grey_tick:1310580954045218816>",
    }
    return lookup.get(opt, "<:xsign:1172524698081427477>")