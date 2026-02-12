# TmpShare 用户手册

## 1. 产品说明

TmpShare 是一个临时文件分享服务，特点如下：

- 支持浏览器与 `curl` 上传下载。
- 上传后返回随机下载链接，其他人难以猜测。
- 下载文件名为随机名，不暴露原始文件名。
- 首次成功下载后，文件在 60 秒后自动过期并删除。
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
- `TMPSHARE_CLEANUP_INTERVAL_SECONDS`：后台清理周期
- `TMPSHARE_MAX_CONTENT_LENGTH`：上传大小上限（字节）

## 3. 上传文件

### 3.1 使用 curl 上传

```bash
curl -F "file=@./example.txt" http://<服务器IP>:8080/api/upload
```

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

- 文件上传后，如果没人下载，会一直保留。
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
- 若用于高敏感数据，建议增加上传鉴权与一次性下载策略。
