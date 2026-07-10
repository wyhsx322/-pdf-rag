# FE-SET-0001｜模型、密钥与连接测试设置界面基线

## 需求

- 允许用户在不直接编辑文件的情况下配置模型服务。
- 密钥只保存在本地，并以掩码状态返回前端。

## 功能

- 查看各模型角色当前配置。
- 更新 API Key、模型名称和 Base URL。
- 选择预设模型并测试服务连接。

## 实现逻辑

- `features/settings/api.ts` 封装读取、更新和测试接口。
- `pages/settings/Settings.tsx` 管理表单、预设选择、保存和连接测试状态。
- 后端将 Key 写入 `.env`，将模型信息写入 `server/runtime_config.json`。

## 代码范围

- `frontend/src/pages/settings/`
- `frontend/src/features/settings/`
- `server/api/routes/settings.py`

## 依赖边界

- 前端不读取或保存真实密钥状态。
- 本地配置文件不得提交到 Git。
