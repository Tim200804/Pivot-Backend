# Pivot Backend — Railway 部署指南

> 本文档指导你如何将 Pivot 后端部署到 Railway 云平台。

---

## 当前状态

本地代码已整理完毕并提交（commit `d567e73`），包含以下更新：

- MySQL 支持（PyMySQL 适配）
- 新增 alerts / checkins / health 路由
- 数据种子脚本（seed_real_data.py, seed_messages.py）
- MySQL 安装与迁移文档
- 更新后的依赖列表（requirements.txt）

**你只需执行 `git push`，即可触发自动部署。**

---

## 方式一：GitHub Actions 自动部署（推荐）

### 第 1 步：推送代码到 GitHub

在你的本地终端执行：

```bash
cd pivot-backend
git push origin main
```

### 第 2 步：配置 Railway Token（首次部署）

1. 访问 [Railway Dashboard](https://railway.app/dashboard)
2. 进入你的 Pivot 项目
3. 点击 **Settings → Tokens → Create Project Token**
4. 复制生成的 Token
5. 打开 GitHub 仓库页面：`https://github.com/Tim200804/Pivot-Backend`
6. 进入 **Settings → Secrets and variables → Actions**
7. 点击 **New repository secret**
   - Name: `RAILWAY_TOKEN`
   - Secret: 粘贴刚才复制的 Token
8. 再次点击 **New repository secret**（可选，但推荐）
   - Name: `RAILWAY_PROJECT_ID`
   - Secret: 在 Railway 项目设置中复制 Project ID

### 第 3 步：触发部署

- 如果已设置 Token，推送代码后会**自动触发部署**
- 也可手动触发：GitHub 仓库 → **Actions** 标签 → 选择 **Deploy to Railway** → **Run workflow**

---

## 方式二：Railway CLI 手动部署

如果你不想用 GitHub Actions，可以直接用 Railway CLI：

```bash
# 1. 安装 Railway CLI
npm install -g @railway/cli

# 2. 登录（浏览器会弹出授权页面）
railway login

# 3. 进入项目目录
cd pivot-backend

# 4. 链接到 Railway 项目（首次）
railway link
# 按提示选择你的 Pivot 项目

# 5. 部署
railway up --detach
```

---

## 方式三：Railway 面板 GitHub 集成（最简单）

1. 访问 [Railway Dashboard](https://railway.app/dashboard)
2. 点击 **New Project**
3. 选择 **Deploy from GitHub repo**
4. 选择 `Tim200804/Pivot-Backend`
5. Railway 会自动检测 `railway.toml` 和 `Procfile` 进行部署

---

## 部署后配置

### 添加 MySQL 数据库

无论哪种部署方式，部署后都需要添加数据库：

1. 在 Railway 项目面板中，点击 **New**
2. 选择 **Database → Add MySQL**
3. Railway 会自动创建数据库并注入 `DATABASE_URL` 环境变量

### 验证环境变量

确保以下环境变量已正确设置：

| 变量名 | 来源 | 说明 |
|--------|------|------|
| `DATABASE_URL` | Railway 自动注入（添加 MySQL 后） | MySQL 连接字符串 |
| `JWT_SECRET_KEY` | 手动设置 | 建议设置一个强随机字符串 |
| `MOONSHOT_API_KEY` | 手动设置 | Moonshot AI API Key |
| `FLASK_ENV` | 手动设置 | 设置为 `production` |

**设置方式：** Railway 面板 → 你的服务 → **Variables** → **New Variable**

### 初始化数据库

部署成功后，数据库表会自动创建（代码中已包含 `init_db()` 自动初始化逻辑）。

如果需要手动执行种子脚本填充数据：

```bash
# 在 Railway 面板中，点击服务的 "Shell" 标签
# 或使用 Railway CLI
railway run python seed_real_data.py
```

---

## 部署验证

部署完成后，访问你的 Railway 服务域名：

```
https://your-service-name.railway.app/api/health
```

应返回：
```json
{"status": "ok", "service": "pivot-backend"}
```

---

## 故障排查

### 部署失败：找不到 gunicorn
确保 `requirements.txt` 中包含 `gunicorn==23.0.0`（已包含）。

### 数据库连接失败
检查 Railway 的 MySQL 插件是否已添加，且 `DATABASE_URL` 是否已自动注入。

### 端口冲突
Railway 自动提供 `$PORT` 环境变量，`railway.toml` 中已正确配置使用它。

### 日志查看
Railway 面板 → 你的服务 → **Deployments** → 点击最新部署 → **View Logs**

---

## 前端连接配置

部署成功后，将前端项目中的 API 基础地址更新为 Railway 域名：

```javascript
// pivot-platform/src/config.js 或类似文件
const API_BASE_URL = 'https://your-service-name.railway.app';
```
