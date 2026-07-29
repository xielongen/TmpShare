# ishare 用户手册

## 1. 直接使用

当前公网地址：

```text
https://ishare.up2sky.top
```

本机已经保存服务器地址和上传密钥后，日常命令只有一个：

```bash
ishare ./example.txt
```

输出的第一行是下载链接，第二行是可直接复制的 `curl` 下载命令。Cloudflare 公网实例的单文件上限为 25 MiB。

## 2. 新电脑首次配置

```bash
pipx install --editable .
ishare setup https://ishare.up2sky.top
```

根据隐藏提示输入上传密钥。配置保存在 `~/.config/ishare/config.json`，文件权限为 `600`。以后不需要记忆 `TMPSHARE_URL` 或 `TMPSHARE_UPLOAD_TOKEN`。

```bash
ishare config
```

该命令只显示 URL 和密钥是否已配置，不显示密钥内容。自动化脚本可用 `--token-file` 从受保护文件读取密钥。

## 3. 下载

下载方不需要上传密钥：

```bash
curl -L "https://ishare.up2sky.top/d/<token>" -o downloaded.file
```

完整下载链接本身就是临时凭证，拿到链接的人都能在有效期内下载，请勿发给无关人员。服务会返回随机文件名，不暴露上传时的原始名称。

## 4. 失效规则

- 上传后无人下载：5 分钟后失效。
- 第一次成功下载：开始 60 秒重试窗口。
- 窗口结束：文件和元数据自动清理。
- 无效或过期链接：跳回 ClickHouse 介绍主页。

Cloudflare KV 跨区域传播偶尔需要几秒。若下载返回 `503 file is propagating`，按响应中的 `Retry-After: 5` 等待后重试；这不表示文件已丢失。

## 5. 上传鉴权是什么

上传密钥只防止陌生人占用你的服务上传文件：

- `POST /api/upload` 必须携带 Bearer 密钥；
- `GET /d/<token>` 不携带该密钥；
- 下载授权来自随机且短期有效的完整 URL。

所以下载者只需要链接，不需要知道主页密码或上传密码。主页本身也没有登录页。

## 6. 本地/VPS 模式

仓库仍保留 Flask 服务用于本机开发或将来部署到容量充足的 VPS：

```bash
python app.py
ishare setup http://127.0.0.1:8080 --no-token
```

`127.0.0.1:8080` 只指当前电脑上的服务，不能作为公网分享地址。恢复公网配置时再次执行：

```bash
ishare setup https://ishare.up2sky.top
```

## 7. 常见问题

### 上传返回 401

本机没有配置密钥或密钥已轮换。重新执行 `ishare setup` 并通过隐藏提示输入当前密钥。

### 上传返回 413

文件超过 Cloudflare KV 的 25 MiB 限制。需要压缩/拆分文件，或在 Cloudflare 控制台启用 R2 后升级服务端。

### 下载跳回主页

token 错误、链接已过期，或文件已清理。临时链接无法恢复，需要重新上传。

### `ishare config` 仍显示本地地址

执行：

```bash
ishare setup https://ishare.up2sky.top
```

输入上传密钥后，本机将永久使用公网地址，除非被参数或环境变量临时覆盖。

## 8. 安全边界

- 服务使用 HTTPS，但不提供端到端内容加密；高敏感文件应先在客户端加密。
- 不要把上传密钥写进 Git、聊天记录或 shell 历史。
- 不要长期传播下载链接；它在有效期内等同于下载密码。
