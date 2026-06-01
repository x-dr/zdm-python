# zdm-python

这是 `lx1169732264/zdm` 的 Python 版本：从什么值得买好价排行榜接口抓取优惠信息，按黑白名单、值数、评论数过滤，然后推送到邮箱或 WxPusher，并用 SQLite `database.db` 记录已推送数据，避免重复推送。

## 功能

- 抓取两个什么值得买好价分页接口
- Selenium 无头 Chrome 自动获取 `__ckguid` / `w_tsfp` Cookie
- SQLite 记录已推送/待推送优惠
- 支持 `white_words.txt` 白名单和 `black_words.txt` 黑名单
- 支持 SMTP SSL 邮箱推送
- 支持 WxPusher 极简推送
- 支持 GitHub Actions 定时运行

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

本地需要已安装 Chrome。如果服务器没有 Chrome，可以参考 GitHub Actions 里的 `browser-actions/setup-chrome` 安装方式。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `maxPageSize` | `10` | 每个排行榜接口最大翻页数 |
| `minVoted` | `0` | 值数大于该值才推送 |
| `minComments` | `0` | 评论数大于该值才推送 |
| `MIN_PUSH_SIZE` | `0` | 待推送数量达到该值才推送 |
| `detail` | `false` | 是否打印详细过滤日志 |
| `emailHost` | 空 | SMTP 服务器，例如 `smtp.qq.com` |
| `emailPort` | `465` | SMTP SSL 端口 |
| `emailAccount` | 空 | 接收推送的邮箱，也是发件邮箱 |
| `emailPassword` | 空 | 邮箱授权码 |
| `spt` | 空 | WxPusher 极简推送 SPT |
| `COOKIE` | 空 | 可选，手动指定 Cookie；不填则 Selenium 自动获取 |

> 代码同时兼容大写变量名，例如 `EMAILACCOUNT`、`EMAILPASSWORD`、`SPT`。

## 黑白名单

- `white_words.txt` 不为空：只推送标题包含白名单关键词的商品。
- `white_words.txt` 为空：启用 `black_words.txt` 黑名单，过滤标题包含黑名单关键词的商品。
- 每个关键词一行。

## GitHub Actions

已提供 `.github/workflows/zdm_crawler_python.yml`，默认支持手动触发。需要定时运行时，取消 schedule 注释即可。

需要配置的 Secrets：

- `emailAccount`
- `emailPassword`
- `spt`
- `GIT_TOKEN`

只用邮箱推送可以不填 `spt`，只用 WxPusher 可以不填邮箱相关变量。
