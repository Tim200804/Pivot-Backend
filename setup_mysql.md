# Pivot 本地 MySQL 安装与配置指南

> 本文档帮助你在本地 macOS 上安装 MySQL 8.0，创建数据库和用户，并配置项目连接。

---

## 预设数据库配置（推荐值）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **用户名** | `pivot_user` | 专门为 pivot 项目创建的 MySQL 用户 |
| **密码** | `PivotPass123!` | 示例密码，可自行修改 |
| **主机** | `localhost` | 本地 MySQL 服务 |
| **端口** | `3306` | MySQL 默认端口 |
| **数据库名** | `pivot_db` | 项目专用数据库 |

**对应的 DATABASE_URL：**
```
mysql+pymysql://pivot_user:PivotPass123!@localhost:3306/pivot_db
```

---

## 第一步：安装 MySQL 8.0

### 方式 A：Homebrew（推荐）

```bash
# 安装 MySQL 8.0
brew install mysql@8.0

# 添加到 PATH（如果安装后找不到 mysql 命令）
echo 'export PATH="/opt/homebrew/opt/mysql@8.0/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 验证安装
mysql --version
```

### 方式 B：官方 DMG 安装包

1. 访问 https://dev.mysql.com/downloads/mysql/
2. 下载 **macOS 14 (ARM, 64-bit), DMG Archive**（或对应你系统的版本）
3. 双击安装，按向导完成
4. 安装过程中会提示设置 **root 密码**，请牢记

---

## 第二步：启动 MySQL 服务

### Homebrew 方式

```bash
# 启动
brew services start mysql@8.0

# 查看状态
brew services list | grep mysql

# 开机自启（可选）
brew services start mysql@8.0
```

### 官方 DMG 方式

```bash
# 在系统偏好设置中点击 Start MySQL Server
# 或在终端执行
sudo mysql.server start
```

---

## 第三步：创建数据库和用户

打开终端，执行以下命令：

```bash
# 1. 以 root 身份登录（按提示输入 root 密码）
mysql -u root -p
```

进入 MySQL 命令行后，依次执行：

```sql
-- 2. 创建数据库
CREATE DATABASE IF NOT EXISTS pivot_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- 3. 创建专用用户（将 localhost 替换为 % 如需远程访问）
CREATE USER IF NOT EXISTS 'pivot_user'@'localhost'
    IDENTIFIED BY 'PivotPass123!';

-- 4. 授权
GRANT ALL PRIVILEGES ON pivot_db.* TO 'pivot_user'@'localhost';

-- 5. 刷新权限
FLUSH PRIVILEGES;

-- 6. 验证
SHOW DATABASES;
SELECT user, host FROM mysql.user WHERE user = 'pivot_user';

-- 7. 退出
EXIT;
```

---

## 第四步：测试连接

```bash
# 用 pivot_user 登录测试
mysql -u pivot_user -p

-- 输入密码 PivotPass123!
-- 然后执行
USE pivot_db;
SHOW TABLES;
EXIT;
```

如果成功进入且看到 `pivot_db` 数据库，说明配置正确。

---

## 第五步：配置项目

将项目 `.env` 文件中的 `DATABASE_URL` 修改为：

```env
DATABASE_URL=mysql+pymysql://pivot_user:PivotPass123!@localhost:3306/pivot_db
```

然后启动后端：

```bash
cd pivot-backend
python run.py
```

第一次启动时，程序会自动在 MySQL 中创建所有表。

---

## 常见问题

### Q1: root 密码忘了怎么办？

```bash
# 停止 MySQL
brew services stop mysql@8.0

# 以跳过权限方式启动
mysqld_safe --skip-grant-tables &

# 免密登录后重置密码
mysql -u root
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED BY '你的新密码';
EXIT;

# 重启正常模式
brew services restart mysql@8.0
```

### Q2: 连接报错 "Can't connect to MySQL server"

```bash
# 检查 MySQL 是否在运行
brew services list | grep mysql

# 或检查端口
lsof -i :3306

# 如果没运行，启动它
brew services start mysql@8.0
```

### Q3: 报错 "Access denied for user 'pivot_user'"

重新执行用户创建和授权步骤（第三步）。

### Q4: 使用 MySQL Workbench 图形化管理

1. 下载安装：https://dev.mysql.com/downloads/workbench/
2. 打开 Workbench → **+** 新建连接
3. 填写：
   - Connection Name: `pivot-local`
   - Hostname: `localhost`
   - Port: `3306`
   - Username: `pivot_user`
4. 点击 **Store in Keychain** 输入密码 `PivotPass123!`
5. 点击 **Test Connection** 测试
6. 连接后可图形化查看表结构、执行 SQL

---

## Railway 部署（生产环境）

Railway 会自动提供 MySQL 并注入 `DATABASE_URL`，格式类似：

```
mysql://root:xxxxxxxx@mysql.railway.internal:3306/railway
```

你**无需手动创建数据库/用户**，只需在 Railway 后台确认该环境变量已正确设置即可。

---

## 安全提醒

- **切勿将 `.env` 文件提交到 Git**，已配置 `.gitignore`
- **生产环境请使用强密码**，不要用示例密码
- **不要暴露 MySQL 端口到公网**，本地开发绑定 `localhost` 即可
