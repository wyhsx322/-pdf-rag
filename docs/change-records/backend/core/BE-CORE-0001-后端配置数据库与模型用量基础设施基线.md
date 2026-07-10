# BE-CORE-0001｜后端配置、数据库与模型用量基础设施基线

## 需求

- 集中管理配置、数据库连接和模型用量。
- 为所有后端业务模块提供稳定的底层能力。

## 功能

- 加载环境变量和运行时模型覆盖配置。
- 初始化 SQLite 表结构并提供连接。
- 记录 Token、模型、费用和知识库维度的调用统计。

## 实现逻辑

- `config.py` 定义路径、模型、切分、检索、超时等参数，并读取 `runtime_config.json`。
- `database.py` 统一创建 SQLite 连接和业务表。
- `usage.py` 在模型调用后记录输入输出 Token，并按价格表估算费用。

## 代码范围

- `server/core/config.py`
- `server/core/database.py`
- `server/core/usage.py`

## 依赖边界

- 不得导入 `server/api`、`server/rag`、`server/memory` 或 `server/writing`。
- 上层模块通过明确函数调用使用本模块。
