# TmpShare / ishare 技术说明

TmpShare 是短生命周期文件传输服务，当前同时保留 Cloudflare 生产实现和 Flask/VPS 实现，共用同一套 `ishare` 客户端协议。

## 目标与边界

- 上传后只在当次响应中返回高熵下载链接。
- 原始文件名不进入下载响应；服务端生成随机下载名并保留安全扩展名。
- 未下载文件默认 300 秒失效；首次成功下载后进入 60 秒重试窗口。
- 上传必须通过 Bearer 密钥，下载链接中的 192 位随机 token 即下载授权。
- 传输使用 HTTPS，但内容没有端到端加密；敏感文件应在客户端先加密。

## 公网 Cloudflare 架构

`ishare.up2sky.top` 使用以下资源：

- Worker `ishare`：鉴权、流式上传、下载和主页。
- KV `ishare-files`：短期文件内容，写入时设置 300 秒 TTL。
- D1 `ishare-metadata`：token、随机下载名、大小、首次下载和过期时间。
- Cron Trigger：每分钟最多清理 100 个到期记录和文件。
- Worker Secret `UPLOAD_TOKEN`：上传鉴权，不在配置或 Git 中出现。

R2 是大文件的优选方案，但账户当前未启用 R2，因此生产实例采用 KV。由 KV 平台硬限制决定，单文件上限固定为 25 MiB。KV 跨区域传播可能短暂延迟；文件暂不可见时服务返回 `503` 和 `Retry-After: 5`，不会误删 D1 元数据。

## Flask / VPS 架构

Flask 实现将文件写入 `data/files/`，SQLite 保存元数据，后台线程和请求入口都会清理到期文件。systemd 服务名为 `secure-drop`。该实现默认上限 100 MiB，可由 `TMPSHARE_MAX_CONTENT_LENGTH` 调整。

`http://127.0.0.1:8080` 仅用于本机开发：`127.0.0.1` 指当前电脑自身，外部设备无法通过它访问。目前 `ishare` 的代码默认值和本机配置都指向 Cloudflare 公网实例。

## 上传协议

### 流式协议（客户端和 Cloudflare）

```http
POST /api/upload
Authorization: Bearer <upload-token>
Content-Type: application/octet-stream
Content-Length: <bytes>
X-File-Name: <URL-encoded-name>
```

`ishare` 每次读取 1 MiB 并发送，不把整个文件载入客户端内存。Flask 实现也接受该协议。

### Flask 兼容协议

Flask 另外兼容 `multipart/form-data`，字段名为 `file`：

```bash
curl -H "Authorization: Bearer ${TMPSHARE_UPLOAD_TOKEN}" \
  -F "file=@./example.txt" http://127.0.0.1:8080/api/upload
```

上传成功返回 `download_url`、随机 `download_filename`、过期说明和 `curl_download`。

## 下载和过期状态

```text
upload
  -> 300 秒内无人领取：失效并清理
  -> 首次成功下载：写入 first_download_at 和 expire_at = now + 60
  -> 60 秒重试窗口结束：链接失效并清理
```

`GET /d/<token>` 无需上传密钥。无效、缺失或过期 token 返回 `302 Location: /`。Cloudflare 下载禁用缓存，并设置 `nosniff` 和 `no-referrer`。

## 密钥与客户端配置

配置优先级为：本次命令参数、自动化环境变量、本机配置、内置公网地址。上传密钥没有源码默认值，也不会出现在 `ishare config` 输出中。

- 本机：`~/.config/ishare/config.json`，目录 `700`、文件 `600`。
- Cloudflare：加密的 Worker Secret `UPLOAD_TOKEN`。
- Flask/VPS：`/etc/default/secure-drop` 的 `TMPSHARE_UPLOAD_TOKEN`。

下载方不传 Bearer 密钥；任何拿到完整下载 URL 的人都能在有效期内下载。

## 验证

```bash
pytest -q
ruff check .
black --check .
cd cloudflare
npm run check
npm run deploy:dry
```

Cloudflare 测试在 `workerd` 中使用隔离的本地 KV/D1，覆盖鉴权、上传/下载、首次下载计时、过期删除、定时清理和隐藏调试入口。
