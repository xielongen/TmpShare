# TmpShare

临时文件分享服务，支持 `curl` 上传/下载、随机不可猜下载链接、首次下载后 60 秒过期清理。

## 功能

- `POST /api/upload` 上传文件
- `GET /d/<token>` 下载文件
- 下载返回随机文件名
- 无效路径和过期链接自动跳转到主页（ClickHouse 介绍页）

## 快速部署

在项目根目录执行：

```bash
bash deploy/deploy.sh
```

部署完成后访问：

```text
http://<server-ip>:8080/
```

## 项目结构

- `app.py`：主服务代码（Flask）
- `requirements.txt`：Python 依赖
- `CLICKHOUSE_HOME.html`：主页内容
- `TECH_DOC.md`：技术文档
- `deploy/deploy.sh`：一键部署脚本
- `deploy/secure-drop.service`：systemd 服务文件
- `docs/USER_MANUAL.md`：用户手册

## 运维命令

```bash
sudo systemctl status secure-drop
sudo systemctl restart secure-drop
sudo journalctl -u secure-drop -n 100 --no-pager
```
