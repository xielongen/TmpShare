# TmpShare / ishare

临时文件分享服务。当前公网实例已经部署到 Cloudflare：

```text
https://ishare.up2sky.top
```

日常只需执行：

```bash
ishare ./example.txt
```

上传成功后会输出临时下载链接和对应的 `curl` 下载命令。下载不需要额外密码；完整下载链接本身就是短期访问凭证。

## 当前公网行为

- 上传需要高熵 Bearer 密钥；密钥只存在于 Cloudflare Secret 和本机 `~/.config/ishare/config.json`。
- 本机配置文件权限为 `600`，`ishare config` 只显示是否已配置密钥，不会打印密钥。
- 未领取文件 5 分钟失效；首次成功下载后保留 60 秒供重试。
- 下载文件使用随机文件名，不公开原始文件名。
- Cloudflare 版本单文件上限为 25 MiB。
- 主页伪装为 ClickHouse 介绍页；无效或过期下载链接返回主页。

公网实例使用 Workers + KV（临时文件）+ D1（过期元数据），每分钟执行一次清理。原计划使用 R2，但当前 Cloudflare 账户尚未启用 R2；因此先采用可立即部署的 KV 方案。KV 的 25 MiB 限制和跨区域短暂传播延迟均已在客户端/服务端显式处理，启用 R2 后可再升级大文件能力。

## 客户端安装和配置

```bash
pipx install --editable .
ishare config
ishare ./example.txt
```

源码中的默认服务地址已经是上面的公网实例，因此无需记忆 `TMPSHARE_URL`。上传密钥不会硬编码进公开仓库；新电脑首次使用时执行一次：

```bash
ishare setup https://ishare.up2sky.top
# 根据隐藏提示输入上传密钥
```

自动化环境仍可用 `--url`、`--token`、`TMPSHARE_URL` 和 `TMPSHARE_UPLOAD_TOKEN` 临时覆盖本机配置。安全脚本可通过 `ishare setup <url> --token-file <path>` 避免把密钥放进进程参数。

## 两种服务端实现

### Cloudflare（当前生产环境）

```bash
cd cloudflare
npm ci
npm run check
npm run deploy:dry
```

资源、迁移、密钥部署和回滚说明见 [`cloudflare/README.md`](cloudflare/README.md)。

### VPS / 本地 Flask

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python app.py
```

本地测试时另开终端：

```bash
ishare setup http://127.0.0.1:8080 --no-token
ishare ./example.txt
```

这里的 `127.0.0.1:8080` 只表示当前电脑上的 Flask 开发服务，不是公网地址。VPS 可执行 `bash deploy/deploy.sh` 安装为 `secure-drop` systemd 服务；生产口令放在 `/etc/default/secure-drop`，不要写入 Git。

## API

- `POST /api/upload`：上传文件。
- `GET /d/<token>`：下载文件。
- Flask 实现兼容 `multipart/form-data` 和流式 `application/octet-stream`。
- Cloudflare 实现使用 `application/octet-stream`、`Content-Length` 和 URL 编码的 `X-File-Name`。

## 工程检查

```bash
pytest -q
ruff check .
black --check .
cd cloudflare && npm run check && npm run deploy:dry
```

GitHub Actions 同时检查 Python/Flask 和 Cloudflare Worker。

## 项目结构

- `src/tmpshare/`：Flask 服务和 `ishare` 客户端。
- `cloudflare/`：当前公网 Worker、KV/D1 配置、迁移和运行时测试。
- `deploy/`：VPS systemd 部署。
- `tests/`、`cloudflare/test/`：两套实现的自动化测试。
- `TECH_DOC.md`：协议、过期与安全设计。
- `docs/ITOOLBOX_MIGRATION.md`：旧 itoolbox 的迁移、删除与保留理由。
