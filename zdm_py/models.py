from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any


@dataclass(eq=False)
class Zdm:
    article_id: str
    title: str = ""
    url: str = ""
    pic_url: str = ""
    price: str = ""
    voted: str = "0"
    comments: str = "0"
    article_mall: str = ""
    timesort: str = ""
    article_time: str = ""
    pushed: bool = False

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "Zdm":
        return cls(
            article_id=str(item.get("article_id", "")),
            title=str(item.get("article_title", "")),
            url=str(item.get("article_url", "")),
            pic_url=str(item.get("article_pic_url", "")),
            price=str(item.get("article_price", "")),
            voted=str(item.get("article_rating", "0")),
            comments=str(item.get("article_comment", "0")),
            article_mall=str(item.get("article_mall", "")),
            timesort=str(item.get("timesort", "")),
        )

    @classmethod
    def from_db_row(cls, row: Any) -> "Zdm":
        return cls(
            article_id=row["article_id"],
            title=row["article_title"] or "",
            url=row["article_url"] or "",
            pic_url=row["article_pic_url"] or "",
            price=row["article_price"] or "",
            voted=row["voted"] or "0",
            comments=row["article_comment"] or "0",
            article_mall=row["article_mall"] or "",
            article_time=row["article_time"] or "",
            pushed=bool(row["pushed"]),
        )

    def to_html_tr(self) -> str:
        return (
            "<tr>"
            f"<td><img src='{escape(self.pic_url, quote=True)}'/></td>"
            f"<td><a target='_blank' href='{escape(self.url, quote=True)}'>{escape(self.title)}</a></td>"
            f"<td>{escape(self.price)}</td>"
            f"<td>{escape(self.voted)}/{escape(self.comments)}</td>"
            f"<td>{escape(self.article_mall)}</td>"
            "</tr>"
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Zdm) and self.article_id == other.article_id

    def __hash__(self) -> int:
        return hash(self.article_id)
