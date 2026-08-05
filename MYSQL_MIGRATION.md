# Pivot Backend — SQLite → MySQL 迁移说明

## 改动摘要

已将数据库层从原生 `sqlite3` 切换为兼容 SQLite / MySQL 双模式，确保在 Railway 上部署时数据持久化。

## 修改的文件

| 文件 | 改动 |
|------|------|
| `models.py` | 重写数据库连接层，支持自动检测 `DATABASE_URL` 协议并适配 SQL 语法差异 |
| `requirements.txt` | 新增 `PyMySQL>=1.1.0` |
| `app.py` | 已回退到 Git HEAD（移除了未完成的 health/checkins/alerts 蓝图注册，避免启动崩溃） |

## 关键适配点

1. **自动数据库检测**：根据 `DATABASE_URL` 前缀自动选择 SQLite 或 MySQL 驱动
2. **占位符兼容**：SQLite `?` ↔ MySQL `%s` 自动转换（跳过字符串字面量）
3. **自增关键字**：`AUTOINCREMENT` ↔ `AUTO_INCREMENT`
4. **列类型适配**：MySQL 下将 `TEXT UNIQUE` / `TEXT DEFAULT` 改为 `VARCHAR` 以兼容约束
5. **Upsert 语法**：SQLite `ON CONFLICT ... DO UPDATE` ↔ MySQL `ON DUPLICATE KEY UPDATE`
6. **索引创建**：`CREATE INDEX IF NOT EXISTS` 在 MySQL 下改为先查 `information_schema.STATISTICS`
7. **建表顺序**：调整 `alert_rules` 在 `alerts` 之前创建（满足 MySQL 外键约束）

## Railway 部署步骤

### 1. 在 Railway 上添加 MySQL 服务

进入你的 Railway 项目 → **New** → **Database** → **MySQL**。

等待 MySQL 服务启动完成后，进入该服务的 **Connect** 标签页，复制 `DATABASE_URL`。

### 2. 设置环境变量

在后端服务的 **Variables** 中添加：

```
DATABASE_URL = mysql://用户名:密码@主机:端口/数据库名
```

Railway 通常会自动注入 `MYSQL_URL` 或 `DATABASE_URL` 到关联服务。如果已自动注入，请确保它的格式是 `mysql://...` 或 `mysql+pymysql://...`。

其他必需的环境变量（如果之前已设置则保持不变）：

```
JWT_SECRET_KEY = your-secret-key
MOONSHOT_API_KEY = your-moonshot-api-key
```

### 3. 重新部署

提交并推送代码到 GitHub（main 分支）：

```bash
git add models.py requirements.txt
git commit -m "feat: migrate database layer from SQLite to MySQL for Railway deploy"
git push origin main
```

GitHub Actions 会自动触发 Railway 部署。

### 4. 验证部署

部署完成后，访问：

```
GET https://your-railway-url/api/health
```

应返回 `{"status": "ok", "service": "pivot-backend"}`。

然后注册一个测试账户，确认数据能正常写入 MySQL。

## 本地开发（SQLite 模式）

本地开发无需任何改动，继续使用 `.env` 中的：

```env
DATABASE_URL=sqlite:///pivot.db
```

## 数据迁移（如需保留现有 SQLite 数据）

如果 `pivot.db` 中已有生产数据需要迁移到 MySQL：

```bash
# 1. 安装 sqlite3mysql 或手动导出
pip install sqlite3-to-mysql

# 2. 导出并导入（示例）
sqlite3mysql -f pivot.db -d pivot -u railway_user -p -h railway_host
```

或者使用 `mysqldump` + 手动转换 `INSERT` 语句的方式迁移。

## 注意事项

- **未完成的蓝图**：工作目录中有 `routes/health.py`、`routes/checkins.py`、`routes/alerts.py` 三个 untracked 文件，它们引用了 models 中的函数。这些蓝图当前未在 `app.py` 中注册（已回退到 Git HEAD）。如需启用，请确认这些路由的 models 函数已实现且测试通过，再在 `app.py` 中注册。
- **MySQL 版本**：适配基于 MySQL 8.0+（支持 `CHECK` 约束、`JSON` 可正常用 `VARCHAR` 存储）。
- **连接池**：当前使用简单连接（每次请求打开/关闭）。如需高并发，后续可引入 `SQLAlchemy` + `connection pooling`。
