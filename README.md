# TmpShare

临时文件分享服务，支持命令行/`curl` 上传下载、随机不可猜下载链接、未领取超时清理，以及首次下载后的短暂重试窗口。

## 核心能力

- `POST /api/upload` 上传文件
- `GET /d/<token>` 下载文件
- `tmpshare <file>` 上传命令；兼容旧命令名 `krypton <file>`
- 下载返回随机文件名
- 未下载文件默认 5 分钟失效；首次下载后默认保留 60 秒供重试
- 可选 Bearer 上传令牌，源码中不包含默认密码
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

另开终端测试命令行上传：

```bash
TMPSHARE_URL=http://127.0.0.1:8080 tmpshare ./example.txt
```

也可以用 `pipx install --editable .` 安装 `tmpshare` 与旧名称兼容命令 `krypton`。

## 服务器部署

在项目根目录执行：

```bash
bash deploy/deploy.sh
```

环境变量默认文件（可选）：

```bash
sudo vim /etc/default/secure-drop
```

公网部署时建议设置独立的上传令牌：

```bash
TMPSHARE_UPLOAD_TOKEN='<long-random-token>'
```

客户端使用同名环境变量，不要把令牌写入源码或提交到 Git。

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
- `docs/ITOOLBOX_MIGRATION.md`：itoolbox 功能取舍与迁移记录

## 运维命令

```bash
sudo systemctl status secure-drop
sudo systemctl restart secure-drop
sudo journalctl -u secure-drop -n 100 --no-pager
```
