# 模板任务与资料文件

2026-10-22 起，新生成的模板 Skill 保存在 `ai_platform.TEMPLATE_GENERATION`，不再创建 `skills/<名称>_<模板ID>/` 或维护 `skill_alll.json`。正文、Markdown、项目组/表字段来源及归属由数据库查询。用户明确选择旧文件模板暂不迁移，旧目录保留不动，但不作为新列表的数据来源。

`mbskills` 继续保存上传副本和异步任务：

```text
user/<用户ID>/jobs/<任务ID>/       # 个人上传、检查点、执行日志和生成文档快照
company/<公司ID>/jobs/<任务ID>/   # 公司模板提炼任务
user/<用户ID>/knowledge/         # 资料图谱与向量索引，保留原资料链路
company/<公司ID>/knowledge/      # 旧模板图谱数据保留，不再生成新模板图谱
```

`TEMPLATE_SKILL_ROOT` 可指定持久目录，默认与 main.py 同级。根目录 worker 锁及所有者写锁继续管理任务；`.template_*.lock`、`.template-deletions.json` 是删除协调记录。运行目录、上传内容、日志、模型检查点、生成文档、旧技能文件夹及汇总 JSON 不纳入 SVN 或镜像。

多节点部署必须共享同一任务目录并保证文件锁有效；数据库共享 Skill 正文不代表各电脑的上传副本/日志也共享。

模板删除二次确认后物理删除数据库记录及专属提炼任务。排队/执行中的模板不能删除；磁盘清理失败保留数据库 deleting 状态和重试入口。历史生成报告和其独立资料图谱不随模板删除。没有自动清理策略，部署方仍需安排任务/报告留存与备份。

其他环境需要先显式执行 `api/endpoints/skill/sql/sql.yaml` 的 `template_generation.create_table`，应用启动不自动 DDL。模板提炼只需要公司基础 LLM；业务资料建图和原文检索仍需要独立 LightRAG SDK 环境及公司 Embedding，不依赖本机演示网页服务。

调用契约见 [模板生成接口](../docs/template-skills-api.md)。
