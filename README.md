# TmpShare

临时文件分享服务，支持命令行/`curl` 上传下载、随机不可猜下载链接、未领取超时清理，以及首次下载后的短暂重试窗口。

## 核心能力

- `POST /api/upload` 上传文件
- `GET /d/<token>` 下载文件
- `tmpshare <file>` 上传命令；提供更易记的短命令 `ishare <file>`
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
pipx install --editable .
ishare setup http://127.0.0.1:8080 --no-token
ishare ./example.txt
```

`setup` 会把服务器地址和可选上传口令保存在 `~/.config/ishare/config.json`，
文件权限为 `600`。之后不需要记忆环境变量；`ishare config` 只显示配置状态，
不会输出口令。环境变量仍保留给 CI 等自动化场景临时覆盖配置。

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

服务器口令不要写入源码或提交到 Git。

日常客户端不需要记住变量名，只需配置一次：

```bash
ishare setup https://<你的服务地址>
# 根据隐藏提示输入与服务器相同的上传口令
ishare ./example.txt
```

上传口令只保护 `POST /api/upload`。下载不需要额外输入口令；随机下载链接本身
就是临时访问凭证，因此不要把链接发给无关人员。

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
