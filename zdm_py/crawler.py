from __future__ import annotations

import os
import random
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Iterable

import requests

from . import db
from .constants import MAX_RETRY, WXPUSHER_URL, ZDM_DOMAIN, ZDM_URLS
from .models import Zdm
from .utils import (
    build_message,
    chunked,
    network_test,
    random_user_agent,
    read_words,
    str_number_format,
)


class CookieManager:
    def __init__(self) -> None:
        self.cookie_header: str | None = None
        self.expired_at: datetime | None = None
        self.driver = None

    def build_cookie_header(self) -> str:
        fixed_cookie = os.getenv("COOKIE") or os.getenv("cookie")
        if fixed_cookie:
            return fixed_cookie

        if self.cookie_header and self.expired_at and self.expired_at > datetime.now() + timedelta(seconds=30):
            return self.cookie_header

        self.clear()
        network_test(ZDM_DOMAIN, 443)
        self._ensure_driver()
        self.driver.get(ZDM_URLS[0] + "1")

        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(self.driver, 10).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )

        cookies: list[dict] = self.driver.get_cookies()
        values = {cookie.get("name"): cookie for cookie in cookies}

        parts = ["x-waf-captcha-referer="]
        if "__ckguid" in values:
            parts.append(f"__ckguid={values['__ckguid'].get('value', '')}")
        if "w_tsfp" in values:
            parts.append(f"w_tsfp={values['w_tsfp'].get('value', '')}")
            expiry = values["w_tsfp"].get("expiry")
            if expiry:
                self.expired_at = datetime.fromtimestamp(int(expiry))

        self.cookie_header = "; ".join(parts)
        return self.cookie_header

    def clear(self) -> None:
        self.cookie_header = None
        self.expired_at = None
        if self.driver:
            try:
                self.driver.delete_all_cookies()
            except Exception:
                pass

    def quit(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            finally:
                self.driver = None

    def _ensure_driver(self) -> None:
        if self.driver:
            return
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:
            raise RuntimeError("缺少 selenium，请先执行 pip install -r requirements.txt") from exc

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument(f"--user-agent={random_user_agent()}")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "load-extension"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option(
            "prefs",
            {
                "profile.managed_default_content_settings.images": 2,
            },
        )

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(20)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )


cookie_manager = CookieManager()


def env(name: str, default: str = "") -> str:
    return os.getenv(name, os.getenv(name.upper(), default))


def env_int(name: str, default: int) -> int:
    value = env(name, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def process_crawl(url: str, retry: int = MAX_RETRY) -> list[Zdm]:
    headers = {
        "User-Agent": random_user_agent(),
        "Referer": url,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive",
        "Cookie": cookie_manager.build_cookie_header(),
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError(f"接口返回不是列表: {data!r}")
        return [Zdm.from_api(item) for item in data]
    except Exception as exc:
        if retry > 0:
            minutes = MAX_RETRY - retry + 1
            print(f"接口调用失败,等待{minutes}分钟后进行重试,剩余重试次数:{retry}")
            time.sleep(minutes * 60)
            cookie_manager.clear()
            return process_crawl(url, retry - 1)
        raise RuntimeError("接口调用失败,程序终止") from exc


def normalize_item(item: Zdm) -> Zdm:
    item.comments = str_number_format(item.comments)
    item.voted = str_number_format(item.voted)
    if item.timesort:
        try:
            item.article_time = datetime.fromtimestamp(
                int(item.timesort), tz=timezone(timedelta(hours=8))
            ).replace(tzinfo=None).isoformat(timespec="seconds")
        except ValueError:
            item.article_time = datetime.now().isoformat(timespec="seconds")
    return item


def obtain_unpushed_articles(max_page_size: int) -> list[Zdm]:
    crawled: list[Zdm] = []
    for base_url in ZDM_URLS:
        interval = 1.0
        for page in range(1, max_page_size + 1):
            part = [normalize_item(item) for item in process_crawl(base_url + str(page))]
            crawled.extend(part)
            print(f"第{page}页数据获取成功, 当前页数据条数{len(part)}")
            time.sleep(random.uniform(interval, interval + 1.0))
            interval += page * 0.05

    all_items = crawled + db.unpush()
    all_items.sort(key=lambda x: int(str_number_format(x.comments)), reverse=True)

    deduped: list[Zdm] = []
    seen: set[str] = set()
    for item in all_items:
        if item.article_id and item.article_id not in seen:
            seen.add(item.article_id)
            deduped.append(item)
    return deduped


def process_filter(items: Iterable[Zdm], min_voted: int, min_comments: int, detail: bool) -> list[Zdm]:
    black_words = read_words("./black_words.txt")
    white_words = read_words("./white_words.txt")

    items = list(items)
    if white_words:
        if detail:
            print("whiteWords is not empty, running in whiteWords mode. whiteWords list:\n" + ",".join(sorted(white_words)))
        items = [item for item in items if any(word in item.title for word in white_words)]
    else:
        if detail:
            print("whiteWords is empty, running in blackWords mode. blackWords list:\n" + ",".join(sorted(black_words)))
        items = [item for item in items if not any(word in item.title for word in black_words)]

    pushed = db.pushed_ids()
    filtered = [
        item
        for item in items
        if int(str_number_format(item.voted)) > min_voted
        and int(str_number_format(item.comments)) > min_comments
        and "前" not in item.price
        and item.article_id not in pushed
    ]

    for item in filtered:
        item.pushed = False

    if detail:
        print("待推送的优惠信息:")
        for item in filtered:
            print(f"{item.article_id} | {item.title}")
    return filtered


def push_to_email(text: str, email_host: str, email_port: str, email_account: str, email_password: str) -> bool:
    if not all([email_host, email_port, email_account, email_password]):
        print("邮箱推送配置不完整,将尝试其他推送方式")
        return False

    msg = MIMEText(text, "html", "utf-8")
    msg["From"] = email_account
    msg["To"] = email_account
    msg["Subject"] = "zdm优惠信息汇总" + datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        with smtplib.SMTP_SSL(email_host, int(email_port), timeout=30) as smtp:
            smtp.login(email_account, email_password)
            smtp.sendmail(email_account, [email_account], msg.as_string())
        return True
    except Exception as exc:
        raise RuntimeError("邮件发送失败") from exc


def push_to_wx(text: str, spt: str) -> bool:
    if not spt:
        print("WxPusher推送配置不完整,将尝试其他推送方式")
        return False

    payload = {
        "content": text,
        "summary": "zdm优惠信息汇总",
        "contentType": "2",
        "spt": spt,
    }
    response = requests.post(WXPUSHER_URL, json=payload, timeout=30)
    print("WxPusher response:" + response.text)
    data = response.json()
    if str(data.get("code")) != "1000":
        raise RuntimeError("WxPusher推送失败:" + str(data.get("msg")))
    return True


def main() -> None:
    email_host = env("emailHost")
    email_port = env("emailPort", "465")
    email_account = env("emailAccount")
    email_password = env("emailPassword")
    spt = env("spt")

    max_page_size = env_int("maxPageSize", 10)
    min_voted = env_int("minVoted", 0)
    min_comments = env_int("minComments", 0)
    min_push_size = env_int("MIN_PUSH_SIZE", 0)
    detail = env_bool("detail", False)

    try:
        items = obtain_unpushed_articles(max_page_size)
        items = process_filter(items, min_voted, min_comments, detail)
        print(f"过滤后剩余数据条数{len(items)}")

        db.save_or_update_batch(items)
        if len(items) < min_push_size:
            return

        for part in chunked(items, 100):
            text = build_message(part)
            pushed_email = push_to_email(text, email_host, email_port, email_account, email_password)
            pushed_wx = push_to_wx(text, spt)
            if not pushed_email and not pushed_wx:
                raise RuntimeError("未匹配到推送方式,请检查配置")

            for item in part:
                item.pushed = True
            db.save_or_update_batch(part)
    finally:
        cookie_manager.quit()


if __name__ == "__main__":
    main()
