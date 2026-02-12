# TmpShare

临时文件分享服务，支持 `curl` 上传/下载、随机不可猜下载链接、首次下载后 60 秒过期清理。

## 核心能力

- `POST /api/upload` 上传文件
- `GET /d/<token>` 下载文件
- 下载返回随机文件名
- 无效路径和过期链接自动跳转到主页（ClickHouse 介绍页）
- 配置可通过环境变量控制（过期时间、清理周期、上传大小）

## 工程规范

- `src` 包结构（应用工厂、配置、仓储、服务、路由分层）
- `pytest` 自动化测试
- `ruff` + `black` 代码规范
- GitHub Actions CI（lint + format-check + tests）

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
ruff check .
black --check .
python app.py
```

## 服务器部署

在项目根目录执行：

```bash
bash deploy/deploy.sh
```

环境变量默认文件（可选）：

```bash
sudo vim /etc/default/secure-drop
```

部署完成后访问：

```text
http://<server-ip>:8080/
```

## 项目结构

- `app.py`：主服务代码（Flask）
- `src/tmpshare/`：主应用包
- `tests/`：测试
- `pyproject.toml`：项目配置与工具配置
- `requirements.txt`：运行依赖
- `requirements-dev.txt`：开发依赖
- `CLICKHOUSE_HOME.html`：主页内容
- `TECH_DOC.md`：技术文档
- `deploy/deploy.sh`：一键部署脚本
- `deploy/secure-drop.service`：systemd 服务文件
- `deploy/secure-drop.env.example`：环境变量示例
- `docs/USER_MANUAL.md`：用户手册

## 运维命令

```bash
sudo systemctl status secure-drop
sudo systemctl restart secure-drop
sudo journalctl -u secure-drop -n 100 --no-pager
```
