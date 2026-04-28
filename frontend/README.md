# LawBot Frontend

Next.js 15 + Shadcn/ui 法律咨询系统前端

## 技术栈

- **Framework**: Next.js 15 (App Router)
- **UI**: Shadcn/ui + Radix UI
- **Styling**: Tailwind CSS
- **Icons**: Lucide React

## 快速开始

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build
```

## 项目结构

```
frontend/
├── app/                    # Next.js App Router
│   ├── api/               # API 路由
│   ├── layout.tsx         # 根布局
│   ├── page.tsx           # 主页面
│   └── globals.css         # 全局样式
├── components/
│   ├── ui/                # Shadcn UI 组件
│   ├── chat/              # 聊天组件
│   └── sidebar/           # 侧边栏组件
├── lib/
│   ├── api.ts            # API 客户端
│   └── utils.ts          # 工具函数
├── hooks/                # 自定义 Hooks
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

## 功能特性

- 💬 聊天界面
  - 消息气泡展示
  - Markdown 支持
  - 代码高亮
  - 来源引用展示

- 📚 会话管理
  - 新建对话
  - 历史会话
  - 会话搜索

- 🛠️ 工具管理
  - 启用/禁用工具
  - 添加/删除工具
  - 工具类型图标

- 📝 技能管理
  - 启用/禁用技能
  - 添加/删除技能
  - 提示词配置

- ⚙️ 系统设置
  - 深色/浅色主题
  - API 配置

## 环境变量

创建 `.env.local` 文件：

```env
NEXT_PUBLIC_API_URL=http://localhost:8002
```

## 开发

```bash
# 启动后端服务 (需要先启动)
# http://localhost:8002

# 启动前端
npm run dev
# 访问 http://localhost:3000
```
