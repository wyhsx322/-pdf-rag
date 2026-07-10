# OPS-0002｜建立强制修改文档同步 Skill 与唯一 ID 索引机制

## 修改背景

项目要求每次修改需求、功能或缺陷时同步记录文档，并能在后续修改前按 ID 检索历史，避免重复实现和文档遗漏。

## 原始需求

- 将 `agents-all.md` 保持为仅包含分类标题和文档索引的精简文件。
- 使用全仓唯一 ID 作为主要检索键。
- 标题可以详细描述修改内容，供人工审查。
- 将编号、查重、文档内容和同步规则放入 Skill。
- 在项目中强制触发该 Skill。

## 历史与重复检查

- 已检查 `OPS-0001`，原有运行维护基线只覆盖安装、启动、配置和数据边界。
- 已检查 `agents-all.md`，此前没有正式安装的文档同步 Skill。
- 本次是在现有模块文档体系上增加强制执行机制，不重复创建第二套索引。

## 问题原因

仅依赖索引文件保存流程规则会导致索引冗长，不利于按 ID 快速检索；仅依赖 Skill 自动触发也无法保证项目级强制执行，因此需要 Skill 与 `AGENTS.md` 双重约束。

## 影响范围

- 用户级 Codex Skill：`sync-project-change-docs`
- 项目工作区指令
- 运行维护模块基线
- 修改文档总索引

## 实现逻辑

- Skill 保存修改前查询、ID 分配、文档结构、索引更新和完成检查流程。
- `AGENTS.md` 对需求、功能、Bug、重构、API、配置、数据和 UI 修改强制调用 Skill。
- 文档 ID 使用模块前缀和四位递增序号。
- `agents-all.md` 仅保留分类标题和 `ID｜详细标题` 链接。

## 变更文件

- 用户级 `sync-project-change-docs/SKILL.md`
- 用户级 `sync-project-change-docs/agents/openai.yaml`
- `AGENTS.md`
- `docs/change-records/agents-all.md`
- `docs/change-records/operations/OPS-0001-依赖安装服务启动本地配置与数据边界基线.md`
- `docs/change-records/operations/OPS-0002-建立强制修改文档同步Skill与唯一ID索引机制.md`

## 验证方式

- 使用 skill-creator 的 `quick_validate.py` 验证 Skill。
- 检查 `AGENTS.md` 是否包含强制触发规则。
- 检查文档 ID 唯一性、文件名与一级标题一致性。
- 检查索引仅包含标题和链接，且所有链接有效。

## 验证结果

- `quick_validate.py` 返回 `Skill is valid!`。
- `agents/openai.yaml` 已生成并包含显示名称、描述和默认提示。
- `AGENTS.md` 已包含强制调用和文档同步规则。
- 文档 ID、标题、索引覆盖和链接检查全部通过。

## 关联文档 ID

- `OPS-0001`
- `ARCH-0001`
