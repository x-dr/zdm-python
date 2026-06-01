from __future__ import annotations

import random
import re
import socket
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence, TypeVar

from .constants import USER_AGENTS

T = TypeVar("T")


def build_message(items: Sequence) -> str:
    body = ["<table border='1'>"]
    body.append(
        "<tr>"
        "<th width='20%'>图</th>"
        "<th width='45%'>标题</th>"
        "<th width='15%'>价格</th>"
        "<th width='10%'>赞/评</th>"
        "<th width='10%'>平台</th>"
        "</tr>"
    )
    body.extend(item.to_html_tr() for item in items)
    body.append("</table>")
    return "".join(body)


def read_words(path: str) -> set[str]:
    file = Path(path)
    if not file.exists():
        file.write_text("", encoding="utf-8")
    return {line.strip() for line in file.read_text(encoding="utf-8").splitlines() if line.strip()}


def str_number_format(number: str | int | None) -> str:
    if number is None:
        return "0"
    text = str(number).strip().lower().replace(",", "").replace("+", "")
    if not text:
        return "0"

    multiplier = Decimal(1)
    if text.endswith("k"):
        multiplier = Decimal(1000)
        text = text[:-1]
    elif text.endswith("w") or text.endswith("万"):
        multiplier = Decimal(10000)
        text = text[:-1]

    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return "0"
    try:
        value = Decimal(match.group(0)) * multiplier
    except InvalidOperation:
        return "0"
    return str(int(value))


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def network_test(domain: str, port: int) -> None:
    print("正在检测网络连通性...")
    try:
        with socket.create_connection((domain, port), timeout=10):
            print("网络连通性检测结果: 成功")
    except OSError as exc:
        print(f"网络连通性检测异常: {exc}")
        raise RuntimeError("接口调用失败,程序终止") from exc


def chunked(items: Sequence[T], size: int) -> Iterable[list[T]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])
