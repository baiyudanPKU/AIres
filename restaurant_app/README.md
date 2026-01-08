# 餐厅管理系统

一个基于Flask的餐厅管理系统，支持餐厅管理、菜品管理、订单处理等功能。

## 功能特性

- **用户认证**：支持用户注册、登录和会话管理
- **餐厅管理**：用户可以创建和管理自己的餐厅
- **菜品管理**：添加、编辑和删除菜品，支持分类管理
- **订单处理**：处理用户订单并跟踪订单状态
- **聊天功能**：用户可以就菜品进行咨询，提供智能顾问功能
- **黑名单管理**：餐厅可以将用户加入黑名单

## 技术栈

- **后端框架**：Flask
- **数据库**：SQLAlchemy (支持多种数据库)
- **用户认证**：Flask-Login
- **数据库操作**：SQLAlchemy ORM
- **表单处理**：Flask-WTF
- **图片处理**：Pillow

## 数据模型

- **用户 (User)**：系统用户，可拥有多个餐厅
- **餐厅 (Restaurant)**：餐厅实体，包含Logo和管理者信息
- **分类 (Category)**：菜品分类（菜品/主食/甜品/饮品）
- **菜品 (Dish)**：具体菜品信息，包含名称、描述、价格和图片
- **订单 (Order)**：用户订单，包含多个订单项
- **订单项 (OrderItem)**：订单中的具体菜品及数量
- **黑名单 (Blacklist)**：餐厅对用户的黑名单管理
- **聊天记录 (ChatMessage)**：用户与餐厅的聊天记录

## 安装与部署

### 环境要求

- Python 3.8+
- 支持的数据库（SQLite默认，也支持MySQL等）

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <https://github.com/baiyudanPKU/AIres>
   cd restaurant_app
   ```

2. **创建虚拟环境并安装依赖**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

### 部署后快速启动
   使用便捷启动脚本：
   ```bash
   # 一键激活虚拟环境并运行run.py      # Windows PowerShell 脚本
   ./start
   ```

## 项目结构

```
restaurant_app/
├── app/                    # 应用主目录
│   ├── __init__.py         # 应用工厂
│   ├── models.py           # 数据模型
│   ├── config.py           # 配置文件
│   ├── blueprints/         # 蓝图路由
│   ├── templates/          # 模板文件
│   ├── static/             # 静态资源
│   └── utils/              # 工具函数
├── migrations/             # 数据库迁移文件
├── requirements.txt        # 依赖包列表
├── run.py                 # 应用启动文件
├── start.ps1              # Windows PowerShell 一键启动脚本
├── README.md              # 项目说明文档

```

## API接口

系统提供以下蓝图接口：

- `/auth/*` - 认证相关接口
- `/main/*` - 主页和公共接口
- `/manage/*` - 餐厅管理接口

- `/order/*` - 订单处理接口

## 更新日志
详细更新日志请查看 [更新日志.md](./更新日志.md)

## 开发与贡献

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

## 许可证

本项目采用 MIT 许可证。