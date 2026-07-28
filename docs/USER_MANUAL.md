# TmpShare 用户手册

## 1. 产品说明

TmpShare 是一个临时文件分享服务，特点如下：

- 支持浏览器与 `curl` 上传下载。
- 上传后返回随机下载链接，其他人难以猜测。
- 下载文件名为随机名，不暴露原始文件名。
- 未下载文件默认在上传 5 分钟后自动过期并删除。
- 首次成功下载后，文件默认在 60 秒后自动过期并删除。
- 访问无效路径或过期链接，自动跳转到主页（ClickHouse 介绍页）。

## 2. 访问入口

- 主页：`http://<服务器IP>:8080/`
- 上传接口：`POST /api/upload`
- 下载接口：`GET /d/<token>`

## 2.1 部署与启动

在项目目录执行：

```bash
bash deploy/deploy.sh
```

服务会以 `secure-drop` 系统用户运行，并通过 `systemd` 托管。

可选配置文件：

```bash
/etc/default/secure-drop
```

常用变量：

- `TMPSHARE_EXPIRE_SECONDS`：首次下载后过期秒数
- `TMPSHARE_UNCLAIMED_EXPIRE_SECONDS`：未发生下载时的最长保留秒数
- `TMPSHARE_CLEANUP_INTERVAL_SECONDS`：后台清理周期
- `TMPSHARE_MAX_CONTENT_LENGTH`：上传大小上限（字节）
- `TMPSHARE_UPLOAD_TOKEN`：可选上传令牌；公网部署建议设置

## 3. 上传文件

### 3.1 使用 curl 上传

```bash
curl -F "file=@./example.txt" http://<服务器IP>:8080/api/upload
```

如果服务器启用了上传令牌：

```bash
curl -H "Authorization: Bearer ${TMPSHARE_UPLOAD_TOKEN}" \
  -F "file=@./example.txt" http://<服务器IP>:8080/api/upload
```

### 3.2 使用 TmpShare 命令上传

在项目根目录运行 `pipx install --editable .` 后：

```bash
export TMPSHARE_URL=http://<服务器IP>:8080
export TMPSHARE_UPLOAD_TOKEN='<服务器配置的令牌>' # 未启用鉴权时省略
tmpshare ./example.txt
```

从旧 `itoolbox` 迁移时，可以继续使用同功能别名 `krypton ./example.txt`。新命令不包含默认公网服务器地址或内置密码。

成功后会返回 JSON，例如：

```json
{
  "message": "upload ok",
  "download_url": "http://<服务器IP>:8080/d/<token>",
  "download_filename": "a1b2c3d4e5f6g7h8.txt",
  "curl_download": "curl -L 'http://<服务器IP>:8080/d/<token>' -o 'a1b2c3d4e5f6g7h8.txt'"
}
```

请妥善保存 `download_url` 或 `curl_download`，该信息不会再次展示。

## 4. 下载文件

### 4.1 使用 curl 下载

```bash
curl -L "http://<服务器IP>:8080/d/<token>" -o "downloaded.file"
```

建议直接使用上传响应中的 `curl_download` 命令，以保证文件名与服务端一致。

## 5. 过期与失效规则

- 文件上传后，如果没人下载，默认 5 分钟后清理。
- 第一次成功下载后，开始计时 60 秒。
- 60 秒后文件与元数据自动清理。
- 过期链接再次访问会重定向到主页。

## 6. 常见问题

### 6.1 上传失败，提示 missing file field

请确认请求使用了 `multipart/form-data`，并且字段名是 `file`。

### 6.2 下载链接打不开

可能原因：

- token 输入错误；
- 文件已过期；
- 服务未启动。

排查方式（服务器上）：

```bash
sudo systemctl status secure-drop
sudo journalctl -u secure-drop -n 100 --no-pager
```

### 6.3 如何重启服务

```bash
sudo systemctl restart secure-drop
```

## 7. 安全建议

- 建议通过 HTTPS（Nginx + TLS）对外提供服务。
- 建议在公网入口增加限流、防刷和访问日志审计。
- 公网入口应配置 `TMPSHARE_UPLOAD_TOKEN`；不要把令牌写入仓库。
- 若用于高敏感数据，应在客户端先加密；TmpShare 本身不提供端到端加密。
