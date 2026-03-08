# Meso Options Analytics System

Meso Options Analytics System 是一个基于 Python、SQLite 和 React 的期权中观分析系统，目标是对 `symbol-day` 级别的期权与波动率状态做中观识别，输出方向偏置、波动偏置、结构置信度、持续性、象限标签和 shift 变化标记。

当前仓库已经具备一条最小可运行链路：

- FastAPI 查询接口
- SQLite 持久化与基础 repository
- 配置层、导入层、校验层、特征层、打分层、分类层、历史查询层
- React Dashboard 页面骨架，包含筛选栏、四象限气泡图、日期折叠侧栏和 symbol 明细抽屉

## 技术栈

- Backend: Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, pytest
- Database: SQLite
- Frontend: React 18, TypeScript, Vite, TanStack Query, ECharts
- Monorepo layout: `apps/` + `packages/`

## 仓库结构

```text
.
├── README.md
├── start.sh
├── apps
│   ├── api
│   │   ├── alembic
│   │   ├── app
│   │   │   ├── api
│   │   │   │   └── routes
│   │   │   ├── config
│   │   │   ├── core
│   │   │   ├── db
│   │   │   ├── repositories
│   │   │   ├── schemas
│   │   │   └── services
│   │   ├── data
│   │   ├── pyproject.toml
│   │   └── tests
│   └── web
│       ├── package.json
│       ├── src
│       │   ├── app
│       │   ├── components
│       │   ├── hooks
│       │   ├── pages
│       │   ├── services
│       │   ├── styles.css
│       │   └── types
│       ├── tsconfig.json
│       └── vite.config.ts
└── packages
    └── shared
```

## 环境前置

- Python `3.11+`
- Node.js `18+`
- npm

后端 Python 依赖建议安装到以下任一位置：

- 仓库根目录 `.venv`
- `apps/api/.venv`

前端依赖安装在 `apps/web/node_modules`

## 一键启动

根目录提供了 `start.sh`，会同时启动后端 API 和前端 Dashboard。

```bash
chmod +x start.sh
./start.sh
```

脚本会自动完成以下动作：

- 自动查找仓库根目录 `.venv` 或 `apps/api/.venv` 中的 Python
- 校验后端 `uvicorn` 是否已安装
- 在启动 API 前自动执行 `alembic upgrade head`，确保 SQLite schema 已初始化
- 如前端依赖不存在，则自动执行 `apps/web` 下的 `npm install --no-package-lock`
- 同时启动 FastAPI 和 Vite，并把日志写入根目录 `.run/`
- 按 `Ctrl+C` 时一并停止前后端进程

默认行为：

- 后端地址：`http://127.0.0.1:18000`
- 前端地址：`http://127.0.0.1:5174`
- 日志目录：`.run/`

启动后可以访问：

- Swagger: `http://127.0.0.1:18000/docs`
- Health: `http://127.0.0.1:18000/health`
- Dashboard: `http://127.0.0.1:5174`

可选环境变量：

```bash
API_HOST=127.0.0.1 API_PORT=18000 WEB_HOST=127.0.0.1 WEB_PORT=5174 ./start.sh
```

如果需要查看启动日志：

```bash
tail -f .run/api.log
tail -f .run/web.log
```

## 手动启动

### 后端

如果使用仓库根目录虚拟环境：

```bash
source .venv/bin/activate
cd apps/api
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

如果使用 `apps/api/.venv`：

```bash
cd apps/api
source .venv/bin/activate
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

### 前端

```bash
cd apps/web
npm install --no-package-lock
VITE_API_BASE_URL=http://127.0.0.1:18000 npm run dev
```

## 常用命令

后端测试：

```bash
cd /Users/bin/Github/MESO
PYTHONPATH=apps/api python3.11 -m pytest apps/api/tests
```

原始数据导入脚本：

```bash
cd /Users/bin/Github/MESO
python3 scripts/import_raw_data_to_new_db.py \
  --source-db apps/api/tests/fixtures/data/analysis_records.db \
  --target-db apps/api/data/raw_option_records.db
```

导入验证：

```bash
sqlite3 apps/api/data/raw_option_records.db "
SELECT COUNT(*) AS imported_rows
FROM raw_option_records;
"
```

```bash
sqlite3 apps/api/data/raw_option_records.db "
SELECT source_rowid, symbol, trade_date, imported_at
FROM raw_option_records
ORDER BY trade_date DESC, symbol ASC
LIMIT 5;
"
```

```bash
sqlite3 apps/api/data/raw_option_records.db "
SELECT COUNT(*) AS duplicate_source_rowids
FROM (
  SELECT source_rowid
  FROM raw_option_records
  GROUP BY source_rowid
  HAVING COUNT(*) > 1
);
"
```

生成 Dashboard 历史信号快照：

```bash
cd /Users/bin/Github/MESO
python3 scripts/sync_raw_option_records_to_app_db.py \
  --source-db apps/api/data/raw_option_records.db \
  --target-db apps/api/data/app.db
```

导入回传 JSON 到应用库：

```bash
cd /Users/bin/Github/MESO
python3 scripts/import_json_to_app_db.py \
  -d 2026-03-10 \
  -f /path/to/returned.json
```

前端构建检查：

```bash
cd apps/web
npm run build
```

## 主要 API

- `GET /health`
- `GET /api/v1/filters`
- `GET /api/v1/date-groups`
- `GET /api/v1/chart-points?trade_date=YYYY-MM-DD`
- `GET /api/v1/signals/{symbol}?trade_date=YYYY-MM-DD`
- `GET /api/v1/symbol-history/{symbol}?lookback_days=10`

## 当前边界

当前项目不包含：

- 自动交易
- 券商接口
- 实盘风控执行
- 用户权限系统
- 多租户系统

当前仍保留为最小可运行形态，不包含：

- 复杂设计系统
- 后台管理写操作
- 多页站点
- 额外的前端代理配置
