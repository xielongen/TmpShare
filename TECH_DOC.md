# Secure Drop 技术说明

这是一个临时私密文件传输服务，支持浏览器与 `curl`。

## 设计目标

- 上传后仅上传者当次响应可见下载链接与命令。
- 下载链接为高熵随机令牌，难以猜测。
- 首次成功下载后开始计时，60 秒后文件自动失效并删除。
- 对未命中路由或过期链接，返回本技术文档（Markdown）。

## API

### 上传

- `POST /api/upload`
- `multipart/form-data`，字段名：`file`
- 成功返回 JSON（包含 `download_url` 与 `curl_download`）

示例：

```bash
curl -F "file=@./example.txt" http://<host>:8080/api/upload
```

### 下载

- `GET /d/<token>`
- 响应头 `Content-Disposition` 使用随机文件名

示例：

```bash
curl -L "http://<host>:8080/d/<token>" -o "<random_name>"
```

## 过期规则

- 上传后尚未下载：不会立刻过期。
- 首次成功下载时：设置 `expire_at = now + 60s`。
- 超时后：数据文件与元数据都会被清理。

## 安全建议

- 生产环境建议放在 HTTPS 反向代理后（如 Nginx + TLS）。
- 建议在公网入口增加速率限制与审计日志。
- 如需更强隔离，可增加上传令牌校验或一次性上传口令。
