# Secure Drop 技术说明

这是一个临时私密文件传输服务，支持浏览器与 `curl`。

## 设计目标

- 上传后仅上传者当次响应可见下载链接与命令。
- 下载链接为高熵随机令牌，难以猜测。
- 未下载文件默认在上传 5 分钟后自动失效并删除。
- 首次成功下载后开始计时，默认 60 秒后文件自动失效并删除。
- 上传鉴权可通过环境变量启用，服务端代码不保存共享密码。
- 对未命中路由或过期链接，返回本技术文档（Markdown）。

## API

### 上传

- `POST /api/upload`
- `multipart/form-data`，字段名：`file`
- 成功返回 JSON（包含 `download_url` 与 `curl_download`）
- 设置 `TMPSHARE_UPLOAD_TOKEN` 后，请求必须携带 `Authorization: Bearer <token>`

示例：

```bash
curl -F "file=@./example.txt" http://<host>:8080/api/upload
```

启用上传令牌后：

```bash
curl -H "Authorization: Bearer ${TMPSHARE_UPLOAD_TOKEN}" \
  -F "file=@./example.txt" http://<host>:8080/api/upload
```

项目安装后也可以流式上传：

```bash
ishare setup http://<host>:8080
ishare ./example.txt
```

客户端配置保存在 `~/.config/ishare/config.json`（权限 `600`）。解析优先级为：
当次命令参数、自动化环境变量、本机配置、内置本地地址
`http://127.0.0.1:8080`。固定上传口令不会内置在源码中。

### 下载

- `GET /d/<token>`
- 响应头 `Content-Disposition` 使用随机文件名
- 上传 Bearer 口令不参与下载；路径中的高熵 token 就是下载授权

示例：

```bash
curl -L "http://<host>:8080/d/<token>" -o "<random_name>"
```

## 过期规则

- 上传后尚未下载：默认 300 秒后过期，由 `TMPSHARE_UNCLAIMED_EXPIRE_SECONDS` 控制。
- 首次成功下载时：设置 `expire_at = now + 60s`。
- 超时后：数据文件与元数据都会被清理。

## 安全建议

- 生产环境建议放在 HTTPS 反向代理后（如 Nginx + TLS）。
- 建议在公网入口增加速率限制与审计日志。
- 公网部署应设置 `TMPSHARE_UPLOAD_TOKEN`，并使用独立的高熵随机值。
- 本服务没有端到端内容加密；高敏感文件应在上传前由客户端自行加密。
