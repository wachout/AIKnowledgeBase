# 大模型聊天前端应用

## 环境配置

### 环境变量设置

1. 复制环境变量模板文件：
```bash
cp .env.example .env
```

2. 根据需要修改 `.env` 文件中的配置：
```bash
# API基础URL配置 - 修改为你的后端服务地址
VITE_API_BASE_URL=http://0.0.0.0:6199/api

# 开发环境配置
VITE_DEV_MODE=true
```

**重要说明**：
- `.env` 文件已被添加到 `.gitignore`，不会被提交到版本控制
- 如果需要不同的环境（如生产环境），可以创建 `.env.production` 等文件

## 安装和运行

### 方法1：使用启动脚本（推荐，解决 EPERM 错误）

```bash
cd app
chmod +x start.sh
./start.sh
```

启动脚本会自动：
- 检查并安装依赖
- 使用绝对路径调用 npm，避免 EPERM 错误
- 启动开发服务器

### 方法2：手动安装和启动

#### 1. 安装依赖

```bash
cd app
/usr/local/bin/npm install
```

**注意**：如果遇到 `EPERM` 错误，使用绝对路径 `/usr/local/bin/npm` 代替 `npm`

#### 2. 启动开发服务器

```bash
/usr/local/bin/npm run dev
```

或者如果 npm 正常工作：

```bash
npm run dev
```

### 方法3：使用 yarn（替代方案）

```bash
cd app
yarn install
yarn dev
```

应用将在以下地址启动：

- **本地访问**: `http://localhost:5173`
- **网络访问**: `http://<你的IP地址>:5173` （例如：`http://192.168.1.100:5173`）

**网络访问说明**：
- 确保防火墙允许5173端口的入站连接
- 在同一网络内的其他设备可以通过IP地址访问
- 如果无法通过IP访问，请检查：
  1. 防火墙设置
  2. 网络连接
  3. 服务器IP地址是否正确

### 3. 构建生产版本

```bash
pnpm build
```

## 功能说明

### 用户认证
- 登录：使用用户名和密码登录
- 注册：创建新账户
- 删除账户：删除当前账户

### 知识库管理
- 双击知识库名称：选择当前使用的知识库
- 右键点击知识库：删除知识库
- 未选择知识库时，默认不使用知识库

### 会话管理
- 点击"+"按钮：创建新会话
- 双击会话名称：加载该会话的历史消息
- 右键点击会话：删除会话
- 未选择会话时，聊天框无法输入

### 聊天功能
- 流式对话：支持实时流式响应
- 文件上传：支持上传文件
- 文件操作选项：
  - 共享权限存入知识库
  - 私有权限存入知识库
  - 分析文件

### 内容渲染
- 图片：自动识别并显示图片URL或base64
- HTML表格：支持HTML格式的表格渲染
- ECharts图表：支持ECharts配置的图表渲染

## API配置

后端API地址：`http://127.0.0.1:6199/api`

确保后端服务已启动并运行在指定端口。

## 常见问题

### EPERM 错误（Node.js v22.15.1 已知问题）

如果遇到 `EPERM: operation not permitted, uv_cwd` 错误：

**快速解决方案**：
```bash
# 使用启动脚本（推荐）
./start.sh

# 或使用绝对路径
/usr/local/bin/npm install
/usr/local/bin/npm run dev
```

**详细解决方案**：请查看 `FIX_EPERM.md` 文件

**其他方法**：
1. 使用启动脚本：`./start.sh`
2. 使用绝对路径：`/usr/local/bin/npm`
3. 降级 Node.js 到 20.x LTS 版本
4. 使用 yarn 代替 npm

### 端口占用
如果5173端口被占用，Vite会自动使用下一个可用端口。

### CORS错误
确保后端服务已正确配置CORS，允许来自前端的请求。

