import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Query, Form, Header
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError
from sqlalchemy import text

from api.endpoints.skill.modular.skill import (
    ImportedSkillWrite,
    ImportedSkillDelete,
    PrivateSkillCreate,
    PrivateSkillDelete,
    PrivateSkillQuery,
    PrivateSkillShare,
    PrivateSkillShareTargetQuery,
    PrivateSubSkillOptionQuery,
    PrivateSkillUpdate,
    PublicSkillBatchDelete,
    PublicSkillCreate,
    PublicSkillDelete,
    PublicSkillQuery,
    PublicSkillUpdate,
    SkillShareAction,
    SkillShareQuery,
    SkillLibraryAction,
    SkillLibraryPublish,
    SkillLibraryQuery,
    TemplateDocumentOptions,
    TemplateTaskRetry,
    TemplateDelete,
    TemplateGraphQuery,
    TemplateSkillGraphQuery,
    TemplateAnswerAssessment,
    TemplateAnswerCreate,
    TemplateAccessUpdate,
    TemplateAccessSelection,
    SkillGroupWrite,
    SkillGroupSelection,
    SkillGroupConfirm,
    SkillExecutionWrite,
    PersonalSkillWrite,
)
from api.endpoints.skill import group_service
from api.endpoints.skill.template_service import TemplateSkillError
from api.endpoints.knowledge.graph_service import GraphError
from utils import template_skill_utils
from api.endpoints.organization.dependencies import (
    get_internal_organization_scope,
    get_organization_scope,
)
from utils.context import fill_audit_fields
from utils.mysqldb import db_client
from utils.response import bad_request, server_error, success
from api.endpoints.mcp.service import persist_skill_with_bindings, verify_skill_binding_identity
from api.endpoints.mcp.service import get_personal_identity


def require_active_skill_feature(request: Request):
    # 旧私有技能分享/技能库继续下架；个人 Markdown 导入使用独立 imported 接口。
    if '/skill/private' in request.url.path:
        raise HTTPException(410, '用户私有技能、技能分享和技能库已停用，请使用个人智能体')


router = APIRouter(dependencies=[Depends(require_active_skill_feature)])


async def _group_response(operation, message=None):
    try:
        return success(data=await operation, message=message)
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logging.getLogger(__name__).exception('技能组操作失败')
        return server_error('技能组操作失败，请刷新后重试；新环境请先执行技能组数据库升级')


@router.get('/groups', summary='分页管理当前公司的独立技能组')
async def query_skill_groups(keyword: str = Query('', max_length=100), pageNo: int = Query(1, ge=1),
        pageSize: int = Query(20, ge=1, le=100), scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.group_page(scope['orgId'], keyword, pageNo, pageSize))


@router.get('/groups/skill-options', summary='选择尚未归组的公共或项目组技能')
async def skill_group_options(keyword: str = Query('', max_length=100), pageNo: int = Query(1, ge=1),
        pageSize: int = Query(20, ge=1, le=100), scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.skill_page(scope['orgId'], keyword, pageNo, pageSize))


@router.get('/groups/resource-options', summary='技能可选模型、公司知识库和数据项目组')
async def skill_resource_options(scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.resource_options(scope['orgId']))


@router.get('/groups/table-options', summary='分页选择一个数据项目组中的已导入表')
async def skill_table_options(projectGroupId: int = Query(..., ge=1), keyword: str = Query('', max_length=100),
        pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.table_options(scope['orgId'], projectGroupId, keyword, pageNo, pageSize))


@router.get('/groups/usable', summary='用户当前用户组获授权的启用技能组')
async def usable_skill_groups(identity=Depends(get_personal_identity)):
    return await _group_response(group_service.usable_groups(identity))


@router.get('/groups/usable/{group_id}/skills', summary='查看当前用户组获授权技能组的技能')
async def usable_group_skills(group_id: int, keyword: str = Query('', max_length=100),
        pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), identity=Depends(get_personal_identity)):
    async def operation():
        allowed = await group_service.usable_groups(identity)
        if group_id not in {row['id'] for row in allowed['list']}:
            raise ValueError('技能组未授权给当前用户组或已停用')
        # 外部使用者只能读取启用技能；分页总数也必须采用相同条件。
        return await group_service.skill_page(identity['orgId'], keyword, pageNo, pageSize, group_id, active_only=True)
    return await _group_response(operation())


@router.post('/groups', summary='新增技能组并原子保存用户组授权')
async def create_skill_group(data: SkillGroupWrite, scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.save_group(scope, data), '技能组已创建')


@router.get('/personal/resource-options', summary='个人技能可用模型、授权数据表、知识库和本人子技能')
async def personal_skill_resources(identity=Depends(get_personal_identity)):
    return await _group_response(group_service.personal_resources(identity))


@router.get('/personal/skills', summary='分页查看我的技能，不包含公司或其他人的技能')
async def personal_skills(keyword:str=Query('',max_length=100),pageNo:int=Query(1,ge=1),
        pageSize:int=Query(10,ge=1,le=100),identity=Depends(get_personal_identity)):
    return await _group_response(group_service.personal_skill_page(identity,keyword,pageNo,pageSize))


@router.get('/personal/skills/{skill_id}', summary='查看本人技能与资源配置')
async def personal_skill_detail(skill_id:int,identity=Depends(get_personal_identity)):
    return await _group_response(group_service.personal_skill_detail(identity,skill_id))


@router.post('/personal/skills', summary='创建仅属于本人的技能与资源配置')
async def create_personal_skill(data:PersonalSkillWrite,identity=Depends(get_personal_identity)):
    return await _group_response(group_service.save_personal_skill(identity,data),'个人技能已创建')


@router.put('/personal/skills/{skill_id}', summary='原子编辑本人技能与资源配置')
async def edit_personal_skill(skill_id:int,data:PersonalSkillWrite,identity=Depends(get_personal_identity)):
    return await _group_response(group_service.save_personal_skill(identity,data,skill_id),'个人技能已保存')


@router.post('/personal/skills/{skill_id}/delete', summary='确认物理删除本人未被引用的技能')
async def remove_personal_skill(skill_id:int,data:SkillGroupConfirm,identity=Depends(get_personal_identity)):
    return await _group_response(group_service.delete_personal_skill(identity,skill_id),'个人技能已删除')


@router.put('/groups/{group_id}', summary='编辑技能组及用户组授权')
async def update_skill_group(group_id: int, data: SkillGroupWrite, scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.save_group(scope, data, group_id), '技能组已保存')


@router.post('/groups/{group_id}/delete', summary='确认后物理删除空技能组')
async def delete_skill_group(group_id: int, data: SkillGroupConfirm, scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.delete_group(scope['orgId'], group_id), '技能组已删除')


@router.get('/groups/{group_id}/skills', summary='分页查看技能组中的公共及项目组技能')
async def query_group_skills(group_id: int, keyword: str = Query('', max_length=100),
        pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.skill_page(scope['orgId'], keyword, pageNo, pageSize, group_id))


@router.post('/groups/{group_id}/skills', summary='将尚未归组的技能纳入技能组')
async def attach_group_skills(group_id: int, data: SkillGroupSelection, scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.change_group_skills(scope, group_id, data.skillIds), '技能已纳入技能组')


@router.post('/groups/{group_id}/skills/remove', summary='确认后移出技能，恢复其原有授权方式')
async def remove_group_skills(group_id: int, data: SkillGroupSelection, scope=Depends(get_internal_organization_scope)):
    if not data.confirm:
        return bad_request(message='请确认移出后恢复技能原有授权方式')
    return await _group_response(group_service.change_group_skills(scope, group_id, data.skillIds, remove=True), '技能已移出，原技能保留')


@router.post('/groups/{group_id}/skills/create', summary='在技能组中原子创建公共规则技能')
async def create_skill_in_group(group_id: int, data: SkillExecutionWrite, request: Request, scope=Depends(get_internal_organization_scope)):
    if data.mcpBindings is not None:
        await verify_skill_binding_identity(request, scope, 1)
    return await _group_response(group_service.create_group_skill(scope, group_id, data), '技能已创建并归组')


@router.get('/groups/{group_id}/skills/{skill_id}', summary='技能资源配置详情')
async def group_skill_detail(group_id: int, skill_id: int, scope=Depends(get_internal_organization_scope)):
    return await _group_response(group_service.execution_detail(scope['orgId'], group_id, skill_id))


@router.put('/groups/{group_id}/skills/{skill_id}', summary='原子保存技能规则、模型、MCP、数据表及知识库')
async def update_group_skill(group_id: int, skill_id: int, data: SkillExecutionWrite, request: Request,
        scope=Depends(get_internal_organization_scope)):
    if data.mcpBindings is not None:
        await verify_skill_binding_identity(request, scope, 1)
    return await _group_response(group_service.save_execution(scope, group_id, skill_id, data), '技能及资源配置已保存')


def _template_service(request: Request):
    name = 'company_template_skills' if '/skill/company/' in request.url.path else 'template_skills'
    service = getattr(request.app.state, name, None)
    if service is None:
        raise TemplateSkillError('模板服务未启动，请重启后端服务', 503, 'SERVICE_UNAVAILABLE')
    return service


def _template_error(exc: TemplateSkillError):
    response = bad_request(message=str(exc), data={'errorCode': exc.code})
    response.status_code = exc.status
    response.headers['Cache-Control'] = 'no-store'
    return response


def _company_identity(scope):
    return {**scope['identity'],'orgId':scope['orgId']}


@router.get('/company/templates/capabilities')
async def company_template_capabilities(request: Request, scope: dict = Depends(get_internal_organization_scope)):
    return await template_capabilities(request,_company_identity(scope))


@router.get('/company/templates/project-groups', summary='生成模板时可选的公司一级项目组')
async def company_template_project_groups(request: Request,scope: dict = Depends(get_internal_organization_scope)):
    return await template_project_groups(request,_company_identity(scope))


@router.get('/company/templates')
async def company_template_list(request: Request,keyword: str = Query(default='',max_length=100),
        pageNo: int = Query(default=1,ge=1),pageSize: int = Query(default=20,ge=1,le=100),
        scope: dict = Depends(get_internal_organization_scope)):
    return await template_list(request,keyword,pageNo,pageSize,_company_identity(scope))


@router.post('/company/templates')
async def company_template_create(request: Request,file: UploadFile = File(...),skillName: str = Form(default='',max_length=100),
        idempotency_key: str | None = Header(default=None,alias='Idempotency-Key',max_length=100),
        scope: dict = Depends(get_internal_organization_scope),projectGroupIds: list[int] = Form(default=[]),
        accessUserGroupIds: str = Form(default='[]',max_length=20000)):
    try:
        groups=json.loads(accessUserGroupIds)
        # 复用同一严格边界验证，布尔值、字符串ID、重复ID均不接受。
        groups=TemplateAccessSelection(userGroupIds=groups).userGroupIds
    except (ValueError,TypeError):
        await file.close()
        return _template_error(TemplateSkillError('用户组参数须为JSON数组或null'))
    request.state.template_access_groups=groups
    return await template_create(request,file,skillName,idempotency_key,_company_identity(scope),projectGroupIds)


@router.post('/company/templates/access', summary='原子修改一个或多个公司模板的用户组权限')
async def company_template_access(request: Request,body: TemplateAccessUpdate,
        scope: dict = Depends(get_internal_organization_scope)):
    try:
        result=await _template_service(request).update_access(_company_identity(scope),body.templateIds,body.userGroupIds)
        return success(result,'模板权限已保存')
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)
    except Exception as exc:
        logging.getLogger(__name__).error('模板权限保存失败：%s',type(exc).__name__)
        response=server_error('模板权限保存失败，未完成的批量修改已回滚，请重试')
        response.status_code=500
        return response


@router.get('/company/templates/{skill_id}')
async def company_template_detail(request: Request,skill_id: str,scope: dict = Depends(get_internal_organization_scope)):
    return await template_detail(request,skill_id,_company_identity(scope))


@router.get('/company/templates/{skill_id}/bindings')
async def company_template_bindings(request: Request,skill_id: str,pageNo: int = Query(default=1,ge=1),
        pageSize: int = Query(default=20,ge=1,le=100),scope: dict = Depends(get_internal_organization_scope)):
    return _template_error(TemplateSkillError('模板与技能绑定已停用',410,'FEATURE_REMOVED'))


@router.post('/company/templates/{skill_id}/delete', summary='确认后物理删除公司模板')
async def company_template_delete(request: Request,skill_id: str,body: TemplateDelete,
        scope: dict = Depends(get_internal_organization_scope)):
    return await template_delete(request,skill_id,body,_company_identity(scope))


@router.post('/templates/{skill_id}/delete', summary='确认后物理删除本人模板')
async def template_delete(request: Request,skill_id: str,body: TemplateDelete,
        identity: dict = Depends(get_personal_identity)):
    try:
        return success(await _template_service(request).delete_template(identity,skill_id),'模板已物理删除')
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/company/template-tasks/{task_id}')
async def company_template_task(request: Request,task_id: str,scope: dict = Depends(get_internal_organization_scope)):
    return await template_task(request,task_id,_company_identity(scope))


@router.post('/company/template-tasks/{task_id}/retry')
async def company_template_retry(request: Request,task_id: str,options: TemplateTaskRetry,scope: dict = Depends(get_internal_organization_scope)):
    return await template_task_retry(request,task_id,options,_company_identity(scope))


@router.get('/company/template-tasks/{task_id}/logs')
async def company_template_logs(request: Request,task_id: str,after: int = Query(default=0,ge=0),
        limit: int = Query(default=100,ge=1,le=500),scope: dict = Depends(get_internal_organization_scope)):
    return await template_task_logs(request,task_id,after,limit,_company_identity(scope))


@router.get('/company/templates/{skill_id}/graph')
async def company_template_graph(request: Request,skill_id: str,scope: dict = Depends(get_internal_organization_scope)):
    return await template_graph_view(request,skill_id,300,600,_company_identity(scope))


@router.post('/company/templates/{skill_id}/graph')
async def company_template_graph_create(request: Request,skill_id: str,scope: dict = Depends(get_internal_organization_scope)):
    return await template_graph_create(request,skill_id,_company_identity(scope))


@router.post('/company/templates/{skill_id}/graph/query', summary='按公司模板ID和query检索模板图谱')
async def company_template_graph_query(request: Request,skill_id: str,body: TemplateSkillGraphQuery,
        scope: dict = Depends(get_internal_organization_scope)):
    return await template_skill_graph_query(request,skill_id,body,_company_identity(scope))


@router.get('/company/template-tasks/{task_id}/graph/evidence/{evidence_id}')
async def company_template_graph_evidence(request: Request,task_id: str,evidence_id: str,scope: dict = Depends(get_internal_organization_scope)):
    return await template_graph_evidence(request,task_id,evidence_id,_company_identity(scope))


async def _template_uploads(request: Request, files: list[UploadFile], allowed_fields: set[str], *, allow_empty=False):
    """只接收声明的表单字段，身份/公司/存储路径永远不来自调用者。"""
    try:
        form = await request.form()
        if set(form.keys()) - allowed_fields:
            raise TemplateSkillError('上传表单包含不支持的字段')
        if any(len(form.getlist(key)) > 1 for key in form.keys() if key not in {'files', 'outputFormats','projectGroupIds'}):
            raise TemplateSkillError('单值表单字段不能重复提交')
        if not (0 if allow_empty else 1) <= len(files) <= 10:
            raise TemplateSkillError('每次上传1至10份资料')
        result = []
        for file in files:
            data = await file.read(template_skill_utils.MAX_FILE_BYTES + 1)
            if not 0 < len(data) <= template_skill_utils.MAX_FILE_BYTES:
                raise TemplateSkillError('每份文件须非空且不超过10MB')
            result.append((file.filename or '', data))
        return result
    finally:
        for file in files:
            await file.close()


@router.get('/templates/capabilities', summary='查询模板输入和文档导出能力')
async def template_capabilities(request: Request, identity: dict = Depends(get_personal_identity)):
    result=await asyncio.to_thread(template_skill_utils.office_capabilities)
    return success(result)


@router.get('/templates/project-groups', summary='生成模板时可选的已授权项目组')
async def template_project_groups(request: Request,identity: dict = Depends(get_personal_identity)):
    try:
        service = _template_service(request)
        if service.scope != 'company':
            raise TemplateSkillError('只有后台模板可以关联项目组', 403, 'PROJECT_GROUP_FORBIDDEN')
        return success({'list':await service.project_context(identity)})
    except TemplateSkillError as exc:
        return _template_error(exc)


@router.post('/templates', summary='上传模板并异步提炼个人Skill')
async def template_create(request: Request, file: UploadFile = File(...),
        skillName: str = Form(default='', max_length=100),
        idempotency_key: str | None = Header(default=None, alias='Idempotency-Key', max_length=100),
        identity: dict = Depends(get_personal_identity),projectGroupIds: list[int] = Form(default=[])):
    try:
        service = _template_service(request)
        if service.scope != 'company' and projectGroupIds:
            raise TemplateSkillError('只有后台模板可以关联项目组', 403, 'PROJECT_GROUP_FORBIDDEN')
        allowed={'file','skillName','projectGroupIds'}
        if service.scope=='company':allowed.add('accessUserGroupIds')
        files = await _template_uploads(request, [file], allowed)
        if len(projectGroupIds)>20 or len(set(projectGroupIds))!=len(projectGroupIds) or any(v<=0 for v in projectGroupIds):
            raise TemplateSkillError('最多选择20个不重复的项目组')
        if '\x00' in skillName:
            raise TemplateSkillError('技能名称不能包含空字符')
        await service.preflight(identity)
        task = await service.submit(identity, 'extract', files,
            skill_name=skillName.strip(), idempotency_key=idempotency_key,project_group_ids=projectGroupIds,
            access_user_group_ids=getattr(request.state,'template_access_groups',None) if service.scope=='company' else None)
        service.notify()
        return success(service.task_view(task), '模板任务已提交')
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/templates', summary='分页查询本人可用的模板Skill')
async def template_list(request: Request, keyword: str = Query(default='', max_length=100),
        pageNo: int = Query(default=1, ge=1), pageSize: int = Query(default=20, ge=1, le=100),
        identity: dict = Depends(get_personal_identity)):
    try:
        data = await _template_service(request).list_skills(identity, keyword.strip(), pageNo, pageSize)
        return success(data)
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.post('/templates/assess', summary='判断AI回答是否适合作为写作模板，不保存')
async def template_answer_assess(request: Request, body: TemplateAnswerAssessment,
        identity: dict = Depends(get_personal_identity)):
    try:
        return success(await _template_service(request).assess_answer(identity,body.answer,body.question))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.post('/templates/from-answer', summary='由用户主动将合适的AI回答提炼为个人模板')
async def template_answer_create(request: Request, body: TemplateAnswerCreate,
        idempotency_key: str | None = Header(default=None,alias='Idempotency-Key',min_length=8,max_length=100,pattern=r'^[A-Za-z0-9_.:-]+$'),
        identity: dict = Depends(get_personal_identity)):
    try:
        service = _template_service(request)
        if service.scope != 'company' and body.projectGroupIds:
            raise TemplateSkillError('只有后台模板可以关联项目组', 403, 'PROJECT_GROUP_FORBIDDEN')
        task = await service.save_answer(identity,body.answer,body.question,body.skillName,idempotency_key,body.projectGroupIds)
        service.notify()
        return success(service.task_view(task),'回答已提交模板提炼，请在模板管理查看进度')
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/templates/{skill_id}', summary='获取本人Skill的元数据与规范化写作规则')
async def template_detail(request: Request, skill_id: str, identity: dict = Depends(get_personal_identity)):
    try:
        meta, learned, markdown = await _template_service(request).skill(identity, skill_id)
        return success({'meta': meta, 'skill': learned, 'skillMarkdown': markdown})
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/templates/{skill_id}/files/skill', summary='下载本人的SKILL.md')
async def template_skill_download(request: Request, skill_id: str, identity: dict = Depends(get_personal_identity)):
    try:
        _, _, markdown = await _template_service(request).skill(identity, skill_id)
        return Response(markdown, media_type='text/markdown; charset=utf-8',
            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff','Content-Disposition':'attachment; filename="SKILL.md"'})
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.post('/templates/{skill_id}/documents', summary='使用本人Skill与本次资料异步生成文档')
async def template_document_create(request: Request, skill_id: str, files: list[UploadFile] | None = File(default=None),
        requirements: str = Form(default='', max_length=4000),
        outputFormats: list[str] = Form(default=['md', 'docx']),
        skillVersion: int | None = Form(default=None, ge=1), sessionId: str | None = Form(default=None, max_length=128),
        sourceTaskId: str | None = Form(default=None,max_length=24),
        idempotency_key: str | None = Header(default=None, alias='Idempotency-Key', max_length=100),
        identity: dict = Depends(get_personal_identity)):
    try:
        uploads = await _template_uploads(request, files or [], {'files', 'requirements', 'outputFormats', 'skillVersion', 'sessionId','sourceTaskId'},allow_empty=bool(sourceTaskId))
        try:
            options = TemplateDocumentOptions(requirements=requirements, outputFormats=outputFormats, skillVersion=skillVersion, sessionId=sessionId)
        except ValidationError:
            raise TemplateSkillError('生成参数不合法，格式仅支持md/docx/pdf且不能重复，文本不能包含空字符') from None
        service = _template_service(request)
        if sourceTaskId:
            if uploads:raise TemplateSkillError('上传新资料与选用已有资料只能选一种')
            uploads=await asyncio.to_thread(service.reusable_uploads,identity,sourceTaskId)
        # 先检查资源归属，再查公司模型配置，避免暴露其他人的Skill信息。
        await service.skill(identity, skill_id)
        await service.preflight(identity,needs_graph=True)
        task = await service.submit(identity, 'document', uploads, skill_id=skill_id,
            requirements=options.requirements, output_formats=options.outputFormats, skill_version=options.skillVersion,
            session_id=options.sessionId, idempotency_key=idempotency_key,source_task_id=sourceTaskId)
        service.notify()
        return success(service.task_view(task), '生成任务已提交')
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/template-tasks/{task_id}', summary='查询本人模板或文档任务进度')
async def template_task(request: Request, task_id: str, identity: dict = Depends(get_personal_identity)):
    try:
        service = _template_service(request)
        return success(service.task_view(await asyncio.to_thread(service.task, identity, task_id)))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/template-tasks/{task_id}/logs', summary='增量查询本人任务执行日志，不返回密钥或模型隐式思考')
async def template_task_logs(request: Request, task_id: str, after: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500), identity: dict = Depends(get_personal_identity)):
    try:
        return success(await asyncio.to_thread(_template_service(request).logs, identity, task_id, after, limit))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.post('/template-tasks/{task_id}/retry', summary='显式重试失败或中断的本人任务')
async def template_task_retry(request: Request, task_id: str, options: TemplateTaskRetry,
        identity: dict = Depends(get_personal_identity)):
    try:
        service = _template_service(request)
        existing=await asyncio.to_thread(service.task, identity, task_id)
        if existing['type']=='template_graph':
            raise TemplateSkillError('模板知识图谱功能已停用',410,'FEATURE_REMOVED')
        await service.preflight(identity,needs_graph=existing['type'] in {'document','knowledge'})
        task = await asyncio.to_thread(service.retry, identity, task_id, options.expectedAttempt)
        service.notify()
        return success(service.task_view(task))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/template-tasks/{task_id}/files/{file_format}', summary='下载本人已完成任务的MD、DOCX或PDF')
async def template_task_download(request: Request, task_id: str, file_format: str,
        identity: dict = Depends(get_personal_identity)):
    try:
        if file_format not in {'md', 'docx', 'pdf'}:
            raise TemplateSkillError('文件格式不存在', 404, 'NOT_FOUND')
        path = await asyncio.to_thread(_template_service(request).artifact, identity, task_id, file_format)
        media = {'md': 'text/markdown; charset=utf-8', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'pdf': 'application/pdf'}
        return FileResponse(path, media_type=media[file_format], filename='document_'+task_id+'.'+file_format,
            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/templates/{skill_id}/graph', summary='查看模板本身的知识图谱，不混入业务资料')
async def template_graph_view(request: Request, skill_id: str, maxNodes: int = Query(default=300,ge=1,le=1000),
        maxEdges: int = Query(default=600,ge=1,le=2000),identity: dict = Depends(get_personal_identity)):
    return _template_error(TemplateSkillError('模板知识图谱功能已停用，请查看模板写作规则',410,'FEATURE_REMOVED'))


@router.post('/templates/{skill_id}/graph', summary='为已有模板排队建立图谱，重复点击返回同一任务')
async def template_graph_create(request: Request, skill_id: str, identity: dict = Depends(get_personal_identity)):
    return _template_error(TemplateSkillError('模板知识图谱功能已停用，请查看模板写作规则',410,'FEATURE_REMOVED'))


@router.get('/template-tasks/{task_id}/graph', summary='查看本次资料的LightRAG知识图谱节点和关系')
async def template_graph(request: Request, task_id: str, maxNodes: int = Query(default=2000,ge=1,le=2000),
        maxEdges: int = Query(default=4000,ge=1,le=4000),identity: dict = Depends(get_personal_identity)):
    try:
        return success(await asyncio.to_thread(_template_service(request).graph,identity,task_id,maxNodes,maxEdges))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/template-sources', summary='分页选择本人已完成图谱处理的资料集合')
async def template_sources(request: Request,keyword: str = Query(default='',max_length=100),
        pageNo: int = Query(default=1,ge=1),pageSize: int = Query(default=20,ge=1,le=100),
        identity: dict = Depends(get_personal_identity)):
    try:
        return success(await asyncio.to_thread(_template_service(request).list_graph_sources,identity,keyword.strip(),pageNo,pageSize))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.post('/template-sources', summary='先上传资料异步建立LightRAG图谱，之后再选择模板')
async def template_source_create(request: Request, files: list[UploadFile] = File(...),
        sessionId: str | None = Form(default=None,max_length=128),
        idempotency_key: str | None = Header(default=None,alias='Idempotency-Key',max_length=100),
        identity: dict = Depends(get_personal_identity)):
    try:
        uploads=await _template_uploads(request,files,{'files','sessionId'})
        if sessionId and '\x00' in sessionId:raise TemplateSkillError('会话标识不能包含空字符')
        service=_template_service(request);await service.preflight(identity,needs_graph=True)
        task=await service.submit(identity,'knowledge',uploads,
            session_id=sessionId,idempotency_key=idempotency_key)
        service.notify()
        return success(service.task_view(task),'资料建图任务已提交')
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/template-tasks/{task_id}/sources', summary='读取本人图谱任务中的可复用资料清单')
async def template_source_files(request: Request,task_id: str,identity: dict = Depends(get_personal_identity)):
    try:
        return success(await asyncio.to_thread(_template_service(request).graph_sources,identity,task_id))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.get('/template-tasks/{task_id}/graph/evidence/{evidence_id}', summary='读取图谱节点或关系对应的原文块')
async def template_graph_evidence(request: Request, task_id: str, evidence_id: str,
        identity: dict = Depends(get_personal_identity)):
    try:
        return success(await asyncio.to_thread(_template_service(request).graph_evidence,identity,task_id,evidence_id))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.post('/templates/{skill_id}/graph/query', summary='按个人模板ID和query检索模板图谱')
async def template_skill_graph_query(request: Request,skill_id: str,body: TemplateSkillGraphQuery,
        identity: dict = Depends(get_personal_identity)):
    try:
        return success(await _template_service(request).query_template_graph(identity,skill_id,body.query))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)


@router.post('/template-tasks/graph/query', summary='从本次LightRAG索引检索实体、关系及原文供聊天使用')
async def template_graph_query(request: Request, task_id: str, body: TemplateGraphQuery,
        identity: dict = Depends(get_personal_identity)):
    try:
        return success(await _template_service(request).query_graph(identity,task_id,body.question,body.mode,body.topK,body.chunkTopK))
    except (TemplateSkillError,GraphError) as exc:
        return _template_error(exc)
logger = logging.getLogger(__name__)
SQL_CONFIG_PATH = Path(__file__).resolve().parents[1] / "sql" / "sql.yaml"


def _scope_org_id(scope: dict[str, Any]) -> int:
    return int(scope.get("orgId", 1)) if isinstance(scope, dict) else 1


def _scope_identity(scope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(scope, dict):
        return {"id": 1, "name": "admin", "userType": "internal"}
    return scope.get("identity", scope)


class PublicSkillBatchDeleteConflictError(RuntimeError):
    pass


def get_sql(key: str) -> str:
    with SQL_CONFIG_PATH.open("r", encoding="utf-8") as file:
        value: Any = yaml.safe_load(file) or {}
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"SQL key not found: {key}")
        value = value[part]
    if not isinstance(value, str):
        raise KeyError(f"SQL key does not point to a statement: {key}")
    return value


def markdown_import_document(filename: str, content: bytes) -> dict:
    """只解析文件内容和声明信息，不加载附件、脚本或外部地址。"""
    if not filename.lower().endswith('.md'):
        raise ValueError('仅支持 Markdown（.md）文件')
    if not content or len(content) > 262144:
        raise ValueError('Markdown 文件不能为空，且不能超过256KB')
    try:
        document = content.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    except UnicodeDecodeError:
        raise ValueError('请使用 UTF-8 编码的 Markdown 文件') from None
    if '\x00' in document or any(ord(char) < 32 and char not in '\n\t' for char in document):
        raise ValueError('文件包含非文本内容，请选择 Markdown 文本文件')
    metadata = {}
    lines = document.split('\n')
    if lines[0].strip() == '---':
        end = next((i for i in range(1, len(lines)) if lines[i].strip() in ('---', '...')), None)
        if end is None:
            raise ValueError('Markdown 头部信息未闭合，请补充结尾的 ---')
        header = '\n'.join(lines[1:end])
        if len(header.encode('utf-8')) > 16384:
            raise ValueError('Markdown 头部信息过长')
        try:
            metadata = yaml.safe_load(header) or {}
        except yaml.YAMLError:
            raise ValueError('Markdown 头部信息不是有效的 YAML 格式') from None
        if not isinstance(metadata, dict):
            raise ValueError('Markdown 头部信息必须是名称、描述等键值配置')
        document = '\n'.join(lines[end + 1:])
    name, description = metadata.get('name'), metadata.get('description', '')
    if (name is not None and not isinstance(name, str)) or not isinstance(description, str):
        raise ValueError('头部 name 和 description 必须是文本')
    if name is not None and (not name.strip() or len(name.strip()) > 100):
        raise ValueError('技能名称需要1—100个字符')
    if len(description.strip()) > 255:
        raise ValueError('技能描述不能超过255个字符')
    if not document.strip():
        raise ValueError('Markdown 正文不能为空')
    return {'skillName': name.strip() if name else '', 'skillDescription': description.strip(),
            'markdown': document, 'filename': filename.replace('\\', '/').rsplit('/', 1)[-1],
            'ignoredFields': [str(key) for key in metadata if key not in ('name', 'description')]}


def imported_rules_text(rows, expected_ids) -> str:
    if {int(row['id']) for row in rows} != set(expected_ids):
        raise ValueError('绑定的个人技能不存在、已停用或不属于技能组创建者，请重新选择')
    rules = '\n\n'.join(f"【个人技能：{row['skillName']}】\n{row['ruleContent']}" for row in rows)
    if len(rules.encode('utf-8')) > 60000:
        raise ValueError('绑定技能文本合计超过60000字节，请减少技能或缩短内容')
    return rules


async def load_imported_agent_rules(agent: dict, identity: dict | None) -> str:
    """调用者的技能组授权由聊天边界验证，技能文本按组创建者读取，工具权限独立校验。"""
    from api.endpoints.knowledge.access import parse_id_list
    if agent.get('agentType') != 2:
        return ''
    if not identity or identity.get('userType') != 'external' or identity['orgId'] != agent['orgId']:
        raise ValueError('请登录后使用个人技能组')
    ids = parse_id_list(agent.get('skillIds'))
    if len(ids) > 20:
        raise ValueError('一个技能组最多绑定20个个人技能')
    if not ids:
        return ''
    rows = await db_client.fetch_all(get_sql('imported.runtime_rules'),
        {'orgId': agent['orgId'], 'userId': agent['userId'], 'skillIds': ','.join(map(str, ids))})
    return imported_rules_text(rows, ids)


@router.post('/imported/preview', summary='解析个人 Markdown 技能，预览后再保存')
async def preview_imported_skill(file: UploadFile = File(...), identity=Depends(get_personal_identity)):
    try:
        contents = await file.read(262145)
        return success(data=markdown_import_document(file.filename or '', contents))
    except ValueError as exc:
        return bad_request(message=str(exc))
    finally:
        await file.close()


@router.get('/imported/querylist', summary='本人导入的文本技能；不包含后台技能')
async def imported_skill_list(keyword: str | None = Query(None, max_length=100),
    enabled: int | None = Query(None, ge=0, le=1), pageNo: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100), identity=Depends(get_personal_identity)):
    params = {'orgId': identity['orgId'], 'userId': identity['id'],
              'keyword': keyword.strip() or None if keyword else None, 'enabled': enabled}
    count = await db_client.fetch_one(get_sql('imported.count'), params)
    rows = await db_client.fetch_all(get_sql('imported.list'), {**params, 'limit': pageSize, 'offset': (pageNo - 1) * pageSize})
    return success(data={'list': rows, 'total': int(count['total']) if count else 0, 'pageNo': pageNo, 'pageSize': pageSize})


@router.get('/imported/options', summary='技能组选择本人启用技能，仅返回名称和ID')
async def imported_skill_options(pageNo: int = Query(1, ge=1), pageSize: int = Query(100, ge=1, le=100),
    identity=Depends(get_personal_identity)):
    params = {'orgId': identity['orgId'], 'userId': identity['id'], 'keyword': None, 'enabled': 1}
    count = await db_client.fetch_one(get_sql('imported.count'), params)
    rows = await db_client.fetch_all(get_sql('imported.options'), {**params, 'limit': pageSize, 'offset': (pageNo - 1) * pageSize})
    return success(data={'list': rows, 'total': int(count['total']) if count else 0, 'pageNo': pageNo, 'pageSize': pageSize})


@router.post('/imported/save', summary='保存本人导入的文本技能')
async def save_imported_skill(data: ImportedSkillWrite, identity=Depends(get_personal_identity)):
    params = {**data.model_dump(), 'orgId': identity['orgId'], 'userId': identity['id']}
    fill_audit_fields(params, identity, is_update=data.id is not None)
    try:
        async with db_client.engine.begin() as conn:
            if data.id and not (await conn.execute(text(get_sql('imported.lock')), params)).mappings().first():
                raise ValueError('只能编辑自己导入的技能')
            result = await conn.execute(text(get_sql('imported.update' if data.id else 'imported.insert')), params)
            skill_id = data.id or int(result.lastrowid)
        return success(data={'id': skill_id}, message='个人技能已保存')
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception('保存个人文本技能失败')
        return server_error('保存技能失败，请稍后重试')


@router.post('/imported/delete', summary='删除本人未被技能组引用的文本技能')
async def delete_imported_skill(data: ImportedSkillDelete, identity=Depends(get_personal_identity)):
    # 兼容旧导入客户端，同样保护新管理器建立的主子引用并清理旧工具绑定。
    return await _group_response(group_service.delete_personal_skill(identity,data.id),'个人技能已删除')


async def _execute_transaction(
    statements: list[tuple[str, dict[str, Any]]],
    *,
    required_positive_indexes: set[int] | None = None,
    cleanup_mcp: bool = False,
) -> list[int]:
    """在公共技能业务内部以一个事务执行多条物理删除。"""
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")

    row_counts: list[int] = []
    async with db_client.engine.begin() as connection:
        required_indexes = (
            set(range(len(statements)))
            if required_positive_indexes is None
            else required_positive_indexes
        )
        for index, (query, args) in enumerate(statements):
            logger.info("Executing public skill transactional SQL:\n%s", query)
            result = await connection.execute(text(query), args)
            if index in required_indexes and result.rowcount <= 0:
                raise PublicSkillBatchDeleteConflictError
            row_counts.append(result.rowcount)
        if cleanup_mcp:
            from api.endpoints.mcp.sql import get_mcp_sql
            await connection.execute(text(get_mcp_sql('binding.delete_orphans')), {'orgId': statements[0][1]['orgId']})
    return row_counts


def _serialize_skill_ids(skill_ids: list[int]) -> str | None:
    return ",".join(str(skill_id) for skill_id in skill_ids) or None


def _deserialize_skill_ids(value: Any) -> list[int]:
    if not value:
        return []
    result: list[int] = []
    for part in str(value).split(","):
        normalized = part.strip()
        if normalized.isdigit() and int(normalized) > 0:
            result.append(int(normalized))
    return result


def _hierarchy_cleanup_params(skill_id: int, identity: dict) -> dict[str, Any]:
    params: dict[str, Any] = {
        "removedSkillId": skill_id,
        "orgId": _scope_org_id(identity),
    }
    fill_audit_fields(params, _scope_identity(identity), is_update=True)
    return params


async def _validate_public_sub_skill_ids(
    sub_skill_ids: list[int],
    *,
    exclude_skill_id: int = 0,
    org_id: int = 1,
) -> str | None:
    if not sub_skill_ids:
        return None
    if exclude_skill_id and exclude_skill_id in sub_skill_ids:
        return "主技能不能绑定自己"
    rows = await db_client.fetch_all(
        get_sql("public_skill.list_sub_skill_options"), {"orgId": org_id}
    )
    available_ids = {int(row["id"]) for row in rows}
    if not set(sub_skill_ids).issubset(available_ids):
        return "所选子技能不是已启用的公共子技能"
    if len(_serialize_skill_ids(sub_skill_ids) or "") > 1000:
        return "所选子技能过多，超过数据库字段可保存长度"
    return None


async def _validate_private_sub_skill_ids(
    owner_id: int,
    sub_skill_ids: list[int],
    *,
    exclude_skill_id: int = 0,
    org_id: int = 1,
) -> str | None:
    if not sub_skill_ids:
        return None
    if exclude_skill_id and exclude_skill_id in sub_skill_ids:
        return "主技能不能绑定自己"
    rows = await db_client.fetch_all(
        get_sql("private_skill.list_sub_skill_options"),
        {"userId": owner_id, "orgId": org_id},
    )
    available_ids = {int(row["id"]) for row in rows}
    if not set(sub_skill_ids).issubset(available_ids):
        return "所选子技能不属于当前用户、已停用或已删除"
    if len(_serialize_skill_ids(sub_skill_ids) or "") > 1000:
        return "所选子技能过多，超过数据库字段可保存长度"
    return None


@router.get(
    "/public/sub-skill-options",
    response_model=dict,
    summary="查询公共子技能选项",
)
async def query_public_sub_skill_options(
    scope: dict[str, Any] = Depends(get_internal_organization_scope),
):
    try:
        rows = await db_client.fetch_all(
            get_sql("public_skill.list_sub_skill_options"),
            {"orgId": _scope_org_id(scope)},
        )
        return success(data={"list": rows, "total": len(rows)})
    except Exception:
        logger.exception("查询公共子技能选项失败")
        return server_error("公共子技能选项查询失败")


@router.post(
    "/public/querylist",
    response_model=dict,
    summary="分页查询公共技能",
)
async def query_public_skills(
    query: PublicSkillQuery,
    _user: Dict[str, Any] = Depends(get_internal_organization_scope),
):
    try:
        filters = {
            "orgId": _scope_org_id(_user),
            "keyword": query.keyword,
            "enabled": query.enabled,
            "skillLevelType": query.skillLevelType,
        }
        count_row = await db_client.fetch_one(get_sql("public_skill.count"), filters)
        records = await db_client.fetch_all(
            get_sql("public_skill.list"),
            {
                **filters,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        records = [
            {**record, "subSkillIds": _deserialize_skill_ids(record.get("subSkillIds"))}
            for record in records
        ]
        return success(
            data={
                "list": records,
                "total": int(count_row.get("total", 0)) if count_row else 0,
                "pageNo": query.pageNo,
                "pageSize": query.pageSize,
            }
        )
    except Exception:
        logger.exception("查询公共技能失败")
        return server_error("公共技能查询失败")


@router.post(
    "/public/insert",
    response_model=dict,
    summary="新增公共技能",
)
async def insert_public_skill(
    data: PublicSkillCreate,
    user: Dict[str, Any] = Depends(get_internal_organization_scope),
    request: Request = None,
):
    if data.mcpBindings is not None:
        await verify_skill_binding_identity(request, user, 1)
    try:
        hierarchy_error = await _validate_public_sub_skill_ids(
            data.subSkillIds, org_id=_scope_org_id(user)
        )
        if hierarchy_error:
            return bad_request(message=hierarchy_error)
        duplicate = await db_client.fetch_one(
            get_sql("public_skill.find_duplicate_name"),
            {
                "orgId": _scope_org_id(user),
                "skillName": data.skillName,
                "excludeId": 0,
            },
        )
        if duplicate:
            return bad_request(message="已存在同名公共技能")

        insert_values = {"orgId": _scope_org_id(user), **data.model_dump(exclude={"mcpBindings"})}
        insert_values["subSkillIds"] = _serialize_skill_ids(data.subSkillIds)
        insert_data = fill_audit_fields(
            insert_values,
            _scope_identity(user),
            is_update=False,
        )
        if data.mcpBindings is not None:
            inserted_id = await persist_skill_with_bindings(get_sql("public_skill.insert"), insert_data, data.mcpBindings, 1, insert=True)
        else:
            inserted_id = await db_client.execute_insert(get_sql("public_skill.insert"), insert_data)
        return success(data={"id": inserted_id}, message="公共技能新增成功")
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception("新增公共技能失败")
        return server_error("公共技能新增失败")


@router.post(
    "/public/update",
    response_model=dict,
    summary="修改公共技能",
)
async def update_public_skill(
    data: PublicSkillUpdate,
    user: Dict[str, Any] = Depends(get_internal_organization_scope),
    request: Request = None,
):
    if data.mcpBindings is not None:
        await verify_skill_binding_identity(request, user, 1)
    try:
        existing = await db_client.fetch_one(
            get_sql("public_skill.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(user)},
        )
        if not existing:
            return bad_request(message="公共技能不存在或已删除")
        if data.mcpBindings is None and existing.get('mcpBindingCount', 0):
            await verify_skill_binding_identity(request, user, 1)

        hierarchy_error = await _validate_public_sub_skill_ids(
            data.subSkillIds,
            exclude_skill_id=data.id,
            org_id=_scope_org_id(user),
        )
        if hierarchy_error:
            return bad_request(message=hierarchy_error)

        duplicate = await db_client.fetch_one(
            get_sql("public_skill.find_duplicate_name"),
            {
                "orgId": _scope_org_id(user),
                "skillName": data.skillName,
                "excludeId": data.id,
            },
        )
        if duplicate:
            return bad_request(message="已存在同名公共技能")

        update_values = {"orgId": _scope_org_id(user), **data.model_dump(exclude={"mcpBindings"}),
                         'updateTemplate':int('templateId' in data.model_fields_set)}
        update_values["subSkillIds"] = _serialize_skill_ids(data.subSkillIds)
        update_data = fill_audit_fields(
            update_values,
            _scope_identity(user),
            is_update=True,
        )
        existing_level = int(existing.get("skillLevelType") or 1)
        if data.mcpBindings is not None:
            before = [(get_sql("skill_hierarchy.remove_reference"), _hierarchy_cleanup_params(data.id, user))] if existing_level == 2 and data.skillLevelType == 1 else []
            await persist_skill_with_bindings(get_sql("public_skill.update"), update_data, data.mcpBindings, 1, before=before)
            affected = 1
        elif existing_level == 2 and data.skillLevelType == 1:
            row_counts = await _execute_transaction(
                [
                    (
                        get_sql("skill_hierarchy.remove_reference"),
                        _hierarchy_cleanup_params(data.id, user),
                    ),
                    (get_sql("public_skill.update"), update_data),
                ],
                required_positive_indexes={1},
            )
            affected = row_counts[1]
        else:
            affected = await db_client.execute(
                get_sql("public_skill.update"),
                update_data,
            )
        if affected <= 0:
            return server_error("公共技能修改失败")
        return success(data={"id": data.id}, message="公共技能修改成功")
    except HTTPException:
        raise
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception("修改公共技能失败")
        return server_error("公共技能修改失败")


@router.post(
    "/public/delete",
    response_model=dict,
    summary="物理删除公共技能",
)
async def delete_public_skill(
    data: PublicSkillDelete,
    user: Dict[str, Any] = Depends(get_internal_organization_scope),
):
    try:
        existing = await db_client.fetch_one(
            get_sql("public_skill.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(user)},
        )
        if not existing:
            return bad_request(message="公共技能不存在或已删除")

        row_counts = await _execute_transaction(
            [
                (
                    get_sql("skill_hierarchy.remove_reference"),
                    _hierarchy_cleanup_params(data.id, user),
                ),
                (
                    get_sql("public_skill.physical_delete"),
                    {"id": data.id, "orgId": _scope_org_id(user)},
                ),
            ],
            required_positive_indexes={1},
            cleanup_mcp=True,
        )
        affected = row_counts[1]
        if affected <= 0:
            return server_error("公共技能删除失败")
        return success(message="公共技能删除成功")
    except Exception:
        logger.exception("删除公共技能失败")
        return server_error("公共技能删除失败")


@router.post(
    "/public/batch-delete",
    response_model=dict,
    summary="批量物理删除公共技能",
)
async def batch_delete_public_skills(
    data: PublicSkillBatchDelete,
    user: Dict[str, Any] = Depends(get_internal_organization_scope),
):
    try:
        statements: list[tuple[str, dict[str, Any]]] = []
        delete_indexes: set[int] = set()
        for skill_id in data.ids:
            statements.append(
                (
                    get_sql("skill_hierarchy.remove_reference"),
                    _hierarchy_cleanup_params(skill_id, user),
                )
            )
            delete_indexes.add(len(statements))
            statements.append(
                (
                    get_sql("public_skill.physical_delete"),
                    {"id": skill_id, "orgId": _scope_org_id(user)},
                )
            )
        await _execute_transaction(
            statements,
            required_positive_indexes=delete_indexes,
            cleanup_mcp=True,
        )
        return success(
            data={"deletedCount": len(data.ids)},
            message=f"已删除 {len(data.ids)} 条公共技能",
        )
    except PublicSkillBatchDeleteConflictError:
        return bad_request(message="部分公共技能不存在或已删除，请刷新后重试")
    except Exception:
        logger.exception("批量删除公共技能失败")
        return server_error("公共技能批量删除失败")


class PrivateSkillConflictError(RuntimeError):
    pass


def _parse_sub_skill_snapshot(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        records = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError) as error:
        raise PrivateSkillConflictError("子技能快照损坏，无法复制") from error
    if not isinstance(records, list) or len(records) > 100:
        raise PrivateSkillConflictError("子技能快照格式错误")
    normalized: list[dict[str, Any]] = []
    source_ids: set[int] = set()
    names: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise PrivateSkillConflictError("子技能快照格式错误")
        source_id = int(record.get("sourceSkillId") or 0)
        name = str(record.get("skillName") or "").strip()
        rule_content = str(record.get("ruleContent") or "").strip()
        if source_id <= 0 or not name or not rule_content:
            raise PrivateSkillConflictError("子技能快照缺少必填内容")
        if source_id in source_ids or name in names:
            raise PrivateSkillConflictError("子技能快照存在重复记录")
        source_ids.add(source_id)
        names.add(name)
        normalized.append(
            {
                "sourceSkillId": source_id,
                "skillName": name,
                "skillDescription": str(record.get("skillDescription") or ""),
                "skillLevelType": 2,
                "ruleContent": rule_content,
                "enabled": 1 if int(record.get("enabled") or 0) == 1 else 0,
            }
        )
    return normalized


async def _build_private_skill_bundle_snapshot(
    source_skill: dict, org_id: int = 1
) -> str | None:
    sub_skill_ids = _deserialize_skill_ids(source_skill.get("subSkillIds"))
    if int(source_skill.get("skillLevelType") or 1) == 2:
        if sub_skill_ids:
            raise PrivateSkillConflictError("子技能不能绑定其他子技能")
        return None
    if not sub_skill_ids:
        return None
    rows = await db_client.fetch_all(
        get_sql("private_skill.list_bundle_children"),
        {
            "userId": int(source_skill["userId"]),
            "subSkillIds": _serialize_skill_ids(sub_skill_ids),
            "orgId": org_id,
        },
    )
    if [int(row["sourceSkillId"]) for row in rows] != sub_skill_ids:
        raise PrivateSkillConflictError("主技能关联的部分子技能已不存在或不属于当前用户")
    return json.dumps(rows, ensure_ascii=False)


async def _copy_private_skill_bundle(
    connection,
    *,
    source_record: Any,
    target_user_id: int,
    identity: dict,
    org_id: int = 1,
) -> int:
    child_records = _parse_sub_skill_snapshot(source_record.get("subSkillsJson"))
    skill_level_type = int(source_record.get("skillLevelType") or 1)
    if skill_level_type == 2 and child_records:
        raise PrivateSkillConflictError("子技能快照不能包含下级技能")

    existing_names_result = await connection.execute(
        text(get_sql("private_skill.list_names_by_user")),
        {"userId": target_user_id, "orgId": org_id},
    )
    existing_names = {
        str(row["skillName"])
        for row in existing_names_result.mappings().all()
    }
    bundle_names = [
        str(source_record["skillName"]),
        *(record["skillName"] for record in child_records),
    ]
    conflicts = sorted(set(bundle_names) & existing_names)
    if conflicts:
        raise PrivateSkillConflictError(
            f"已存在同名私有技能：{'、'.join(conflicts)}"
        )

    copied_child_ids: list[int] = []
    for child in child_records:
        child_params = {
            "orgId": org_id,
            "projectGroupId": None,
            "skillName": child["skillName"],
            "skillDescription": child["skillDescription"],
            "skillType": 3,
            "skillLevelType": 2,
            "ruleContent": child["ruleContent"],
            "tableIds": None,
            "subSkillIds": None,
            "userId": target_user_id,
            "enabled": child["enabled"],
        }
        fill_audit_fields(child_params, identity, is_update=False)
        child_result = await connection.execute(
            text(get_sql("private_skill.insert")),
            child_params,
        )
        if child_result.lastrowid is None:
            raise PrivateSkillConflictError("子技能复制失败")
        copied_child_ids.append(int(child_result.lastrowid))

    main_params = {
        "orgId": org_id,
        "projectGroupId": None,
        "skillName": source_record["skillName"],
        "skillDescription": source_record.get("skillDescription") or "",
        "skillType": 3,
        "skillLevelType": skill_level_type,
        "ruleContent": source_record["ruleContent"],
        "tableIds": None,
        "subSkillIds": _serialize_skill_ids(copied_child_ids),
        "userId": target_user_id,
        "enabled": source_record["enabled"],
    }
    fill_audit_fields(main_params, identity, is_update=False)
    main_result = await connection.execute(
        text(get_sql("private_skill.insert")),
        main_params,
    )
    if main_result.lastrowid is None:
        raise PrivateSkillConflictError("主技能复制失败")
    return int(main_result.lastrowid)


def _private_skill_owner_id(data_user_id: int | None, identity: dict) -> int | None:
    identity = _scope_identity(identity)
    if identity.get("userType") == "external":
        if data_user_id is not None and data_user_id != int(identity["id"]):
            return None
        return int(identity["id"])
    return int(data_user_id) if data_user_id else None


@router.post("/private/sub-skill-options", summary="查询当前用户的私有子技能选项")
async def query_private_sub_skill_options(
    query: PrivateSubSkillOptionQuery,
    identity: dict = Depends(get_organization_scope),
):
    owner_id = _private_skill_owner_id(query.userId, identity)
    if owner_id is None:
        return bad_request(message="必须先选择技能所属用户")
    try:
        owner = await db_client.fetch_one(
            get_sql("private_skill.find_active_user"),
            {"userId": owner_id, "orgId": _scope_org_id(identity)},
        )
        if not owner:
            return bad_request(message="技能所属用户不存在或已停用")
        rows = await db_client.fetch_all(
            get_sql("private_skill.list_sub_skill_options"),
            {"userId": owner_id, "orgId": _scope_org_id(identity)},
        )
        return success(data={"list": rows, "total": len(rows)})
    except Exception:
        logger.exception("查询私有子技能选项失败")
        return server_error("私有子技能选项查询失败")


@router.post("/private/querylist", summary="分页查询私有技能")
async def query_private_skills(
    query: PrivateSkillQuery,
    identity: dict = Depends(get_organization_scope),
):
    try:
        actor = _scope_identity(identity)
        scope_user_id = (
            int(actor["id"]) if actor.get("userType") == "external" else None
        )
        filters = {
            "orgId": _scope_org_id(identity),
            "scopeUserId": scope_user_id,
            "skillName": query.skillName,
            "userName": query.userName,
            "groupId": query.groupId,
            "account": query.account,
            "enabled": query.enabled,
            "skillLevelType": query.skillLevelType,
        }
        count_row = await db_client.fetch_one(get_sql("private_skill.count"), filters)
        rows = await db_client.fetch_all(
            get_sql("private_skill.list"),
            {
                **filters,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        rows = [
            {**row, "subSkillIds": _deserialize_skill_ids(row.get("subSkillIds"))}
            for row in rows
        ]
        return success(data={
            "list": rows,
            "total": int(count_row.get("total", 0)) if count_row else 0,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询私有技能失败")
        return server_error("私有技能查询失败")


@router.post("/private/insert", summary="新增私有技能")
async def create_private_skill(
    data: PrivateSkillCreate,
    identity: dict = Depends(get_organization_scope),
    request: Request = None,
):
    owner_id = _private_skill_owner_id(data.userId, identity)
    if owner_id is None:
        return bad_request(message="必须指定有效的技能所属用户")
    if data.mcpBindings is not None:
        await verify_skill_binding_identity(request, identity, 3, owner_id)
    try:
        owner = await db_client.fetch_one(
            get_sql("private_skill.find_active_user"),
            {"userId": owner_id, "orgId": _scope_org_id(identity)},
        )
        if not owner:
            return bad_request(message="技能所属用户不存在或已停用")
        duplicate = await db_client.fetch_one(
            get_sql("private_skill.find_duplicate_name"),
            {
                "orgId": _scope_org_id(identity),
                "userId": owner_id,
                "skillName": data.skillName,
                "excludeId": 0,
            },
        )
        if duplicate:
            return bad_request(message="该用户已存在同名私有技能")
        hierarchy_error = await _validate_private_sub_skill_ids(
            owner_id,
            data.subSkillIds,
            org_id=_scope_org_id(identity),
        )
        if hierarchy_error:
            return bad_request(message=hierarchy_error)
        params = {
            "orgId": _scope_org_id(identity),
            "projectGroupId": None,
            "skillName": data.skillName,
            "skillDescription": data.skillDescription,
            "skillType": 3,
            "skillLevelType": data.skillLevelType,
            "ruleContent": data.ruleContent,
            "tableIds": None,
            "subSkillIds": _serialize_skill_ids(data.subSkillIds),
            "userId": owner_id,
            "enabled": data.enabled,
        }
        fill_audit_fields(params, _scope_identity(identity), is_update=False)
        if data.mcpBindings is not None:
            inserted_id = await persist_skill_with_bindings(get_sql("private_skill.insert"), params, data.mcpBindings, 3, owner_id, insert=True)
        else:
            inserted_id = await db_client.execute_insert(get_sql("private_skill.insert"), params)
        return success(data={"id": int(inserted_id)}, message="私有技能新增成功")
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception("新增私有技能失败")
        return server_error("私有技能新增失败")


@router.post("/private/update", summary="修改私有技能")
async def update_private_skill(
    data: PrivateSkillUpdate,
    identity: dict = Depends(get_organization_scope),
    request: Request = None,
):
    try:
        actor = _scope_identity(identity)
        existing = await db_client.fetch_one(
            get_sql("private_skill.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if not existing:
            return bad_request(message="私有技能不存在")
        owner_id = int(existing["userId"])
        if actor.get("userType") == "external" and owner_id != int(actor["id"]):
            return bad_request(message="无权修改其他用户的私有技能")
        if data.userId is not None and data.userId != owner_id:
            return bad_request(message="私有技能不能转移给其他用户")
        if data.mcpBindings is not None or existing.get('mcpBindingCount', 0):
            await verify_skill_binding_identity(request, identity, 3, owner_id)
        duplicate = await db_client.fetch_one(
            get_sql("private_skill.find_duplicate_name"),
            {
                "orgId": _scope_org_id(identity),
                "userId": owner_id,
                "skillName": data.skillName,
                "excludeId": data.id,
            },
        )
        if duplicate:
            return bad_request(message="该用户已存在同名私有技能")
        hierarchy_error = await _validate_private_sub_skill_ids(
            owner_id,
            data.subSkillIds,
            exclude_skill_id=data.id,
            org_id=_scope_org_id(identity),
        )
        if hierarchy_error:
            return bad_request(message=hierarchy_error)
        params = {
            "id": data.id,
            "orgId": _scope_org_id(identity),
            "userId": owner_id,
            "skillName": data.skillName,
            "skillDescription": data.skillDescription,
            "skillLevelType": data.skillLevelType,
            "ruleContent": data.ruleContent,
            "subSkillIds": _serialize_skill_ids(data.subSkillIds),
            "enabled": data.enabled,
        }
        fill_audit_fields(params, actor, is_update=True)
        existing_level = int(existing.get("skillLevelType") or 1)
        if data.mcpBindings is not None:
            before = [(get_sql("skill_hierarchy.remove_reference"), _hierarchy_cleanup_params(data.id, identity))] if existing_level == 2 and data.skillLevelType == 1 else []
            await persist_skill_with_bindings(get_sql("private_skill.update"), params, data.mcpBindings, 3, owner_id, before=before)
            affected = 1
        elif existing_level == 2 and data.skillLevelType == 1:
            row_counts = await _execute_transaction(
                [
                    (
                        get_sql("skill_hierarchy.remove_reference"),
                        _hierarchy_cleanup_params(data.id, identity),
                    ),
                    (get_sql("private_skill.update"), params),
                ],
                required_positive_indexes={1},
            )
            affected = row_counts[1]
        else:
            affected = await db_client.execute(get_sql("private_skill.update"), params)
        if affected != 1:
            return server_error("私有技能修改失败")
        return success(data={"id": data.id}, message="私有技能修改成功")
    except HTTPException:
        raise
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception("修改私有技能失败")
        return server_error("私有技能修改失败")


async def _delete_private_skill_transaction(
    skill_id: int,
    owner_id: int,
    identity: dict,
    org_id: int = 1,
) -> dict[str, int]:
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")
    async with db_client.engine.begin() as connection:
        from api.endpoints.mcp.sql import get_mcp_sql
        await connection.execute(text(get_mcp_sql("binding.delete_skill")),
                                 {"orgId": org_id, "userId": owner_id, "skillId": skill_id})
        await connection.execute(
            text(get_sql("skill_hierarchy.remove_reference")),
            _hierarchy_cleanup_params(skill_id, identity),
        )
        share_result = await connection.execute(
            text(get_sql("skill_share.delete_pending_by_skill")),
            {"id": skill_id, "orgId": org_id},
        )
        skill_result = await connection.execute(
            text(get_sql("private_skill.physical_delete")),
            {"id": skill_id, "userId": owner_id, "orgId": org_id},
        )
        if skill_result.rowcount != 1:
            raise PrivateSkillConflictError("私有技能已发生变化")
    return {
        "deletedSkills": skill_result.rowcount,
        "deletedPendingShares": max(share_result.rowcount, 0),
    }


@router.post("/private/delete", summary="物理删除私有技能")
async def delete_private_skill(
    data: PrivateSkillDelete,
    identity: dict = Depends(get_organization_scope),
):
    try:
        actor = _scope_identity(identity)
        existing = await db_client.fetch_one(
            get_sql("private_skill.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if not existing:
            return bad_request(message="私有技能不存在")
        owner_id = int(existing["userId"])
        if actor.get("userType") == "external" and owner_id != int(actor["id"]):
            return bad_request(message="无权删除其他用户的私有技能")
        summary = await _delete_private_skill_transaction(
            data.id,
            owner_id,
            identity,
            _scope_org_id(identity),
        )
        return success(data=summary, message="私有技能删除成功")
    except PrivateSkillConflictError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("删除私有技能失败")
        return server_error("私有技能删除失败，已回滚")


async def _insert_skill_shares_transaction(
    source_skill: dict,
    target_user_ids: list[int],
    identity: dict,
    org_id: int = 1,
) -> int:
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")
    inserted = 0
    async with db_client.engine.begin() as connection:
        for target_user_id in target_user_ids:
            duplicate_result = await connection.execute(
                text(get_sql("skill_share.find_pending_duplicate")),
                {
                    "orgId": org_id,
                    "sourceSkillId": source_skill["id"],
                    "targetUserId": target_user_id,
                },
            )
            if duplicate_result.mappings().first():
                raise PrivateSkillConflictError("部分用户已存在待接收分享")
            params = {
                "orgId": org_id,
                "sourceSkillId": source_skill["id"],
                "sourceUserId": source_skill["userId"],
                "targetUserId": target_user_id,
                "skillName": source_skill["skillName"],
                "skillDescription": source_skill.get("skillDescription") or "",
                "skillLevelType": int(source_skill.get("skillLevelType") or 1),
                "subSkillsJson": source_skill.get("subSkillsJson"),
                "ruleContent": source_skill["ruleContent"],
                "enabled": source_skill["enabled"],
            }
            fill_audit_fields(params, _scope_identity(identity), is_update=False)
            result = await connection.execute(text(get_sql("skill_share.insert")), params)
            if result.rowcount != 1:
                raise PrivateSkillConflictError("技能分享写入失败")
            inserted += 1
    return inserted


@router.post("/private/share/targets", summary="分页查询私有技能分享接收人")
async def query_private_skill_share_targets(
    query: PrivateSkillShareTargetQuery,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    if actor.get("userType") != "external":
        return bad_request(message="只有外部用户可以选择分享接收人")
    filters = {
        "orgId": _scope_org_id(identity),
        "excludeUserId": int(actor["id"]),
        "keyword": query.keyword,
        "groupId": query.groupId,
    }
    try:
        count_row = await db_client.fetch_one(get_sql("share_target.count"), filters)
        rows = await db_client.fetch_all(
            get_sql("share_target.list"),
            {
                **filters,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        return success(data={
            "list": rows,
            "total": int(count_row.get("total", 0)) if count_row else 0,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询技能分享接收人失败")
        return server_error("分享接收人查询失败")


@router.post("/private/share", summary="分享私有技能给多个用户")
async def share_private_skill(
    data: PrivateSkillShare,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    if actor.get("userType") != "external":
        return bad_request(message="只有外部用户可以分享自己的私有技能")
    try:
        source_skill = await db_client.fetch_one(
            get_sql("private_skill.find_by_id"),
            {"id": data.skillId, "orgId": _scope_org_id(identity)},
        )
        if (
            not source_skill
            or int(source_skill["userId"]) != int(actor["id"])
            or int(source_skill["enabled"]) != 1
        ):
            return bad_request(message="私有技能不存在、已停用或不属于当前用户")
        if int(actor["id"]) in data.targetUserIds:
            return bad_request(message="不能把技能分享给自己")
        source_skill["subSkillsJson"] = await _build_private_skill_bundle_snapshot(
            source_skill, _scope_org_id(identity)
        )
        rows = await db_client.fetch_all(
            get_sql("private_skill.find_users_by_ids"),
            {
                "ids": ",".join(str(user_id) for user_id in data.targetUserIds),
                "orgId": _scope_org_id(identity),
            },
        )
        if {int(row["id"]) for row in rows} != set(data.targetUserIds):
            return bad_request(message="部分接收人不存在或已停用")
        inserted = await _insert_skill_shares_transaction(
            source_skill, data.targetUserIds, identity, _scope_org_id(identity)
        )
        return success(data={"sharedCount": inserted}, message=f"已分享给 {inserted} 名用户")
    except PrivateSkillConflictError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("分享私有技能失败")
        return server_error("私有技能分享失败，已回滚")


@router.post("/private/share/querylist", summary="分页查询私有技能分享")
async def query_private_skill_shares(
    query: SkillShareQuery,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    if actor.get("userType") == "external":
        source_user_id = int(actor["id"]) if query.direction == "outbox" else None
        target_user_id = int(actor["id"]) if query.direction != "outbox" else None
    else:
        source_user_id = None
        target_user_id = None
    filters = {
        "orgId": _scope_org_id(identity),
        "sourceUserId": source_user_id,
        "targetUserId": target_user_id,
        "receiveStatus": query.receiveStatus,
        "keyword": query.keyword,
    }
    try:
        count_row = await db_client.fetch_one(get_sql("skill_share.count"), filters)
        rows = await db_client.fetch_all(
            get_sql("skill_share.list"),
            {
                **filters,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        return success(data={
            "list": rows,
            "total": int(count_row.get("total", 0)) if count_row else 0,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询私有技能分享失败")
        return server_error("技能分享查询失败")


async def _accept_skill_share_transaction(
    *, share_id: int, target_user_id: int, identity: dict, org_id: int = 1
) -> dict[str, int]:
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")
    async with db_client.engine.begin() as connection:
        result = await connection.execute(
            text(get_sql("skill_share.find_for_update")),
            {"id": share_id, "orgId": org_id},
        )
        share_record = result.mappings().first()
        if not share_record or int(share_record["targetUserId"]) != target_user_id:
            raise PrivateSkillConflictError("分享记录不存在或不属于当前用户")
        if int(share_record["receiveStatus"]) != 0:
            raise PrivateSkillConflictError("分享记录已处理")
        accepted_skill_id = await _copy_private_skill_bundle(
            connection,
            source_record=share_record,
            target_user_id=target_user_id,
            identity=_scope_identity(identity),
            org_id=org_id,
        )
        update_params = fill_audit_fields(
            {
                "id": share_id,
                "orgId": org_id,
                "receiveStatus": 1,
                "acceptedSkillId": accepted_skill_id,
                "responseTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            _scope_identity(identity),
            is_update=True,
        )
        update_result = await connection.execute(
            text(get_sql("skill_share.update_status")), update_params
        )
        if update_result.rowcount != 1:
            raise PrivateSkillConflictError("分享记录已被其他操作处理")
    return {"shareId": share_id, "skillId": accepted_skill_id}


@router.post("/private/share/accept", summary="接收私有技能分享")
async def accept_private_skill_share(
    data: SkillShareAction,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    if actor.get("userType") != "external":
        return bad_request(message="只有外部用户可以接收技能分享")
    try:
        result = await _accept_skill_share_transaction(
            share_id=data.id,
            target_user_id=int(actor["id"]),
            identity=identity,
            org_id=_scope_org_id(identity),
        )
        return success(data=result, message="技能接收成功")
    except PrivateSkillConflictError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("接收私有技能分享失败")
        return server_error("技能接收失败，已回滚")


async def _change_share_status_transaction(
    *, share_id: int, actor_user_id: int, actor_role: str, status: int,
    identity: dict, org_id: int = 1
) -> None:
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")
    async with db_client.engine.begin() as connection:
        result = await connection.execute(
            text(get_sql("skill_share.find_for_update")),
            {"id": share_id, "orgId": org_id},
        )
        record = result.mappings().first()
        owner_field = "targetUserId" if actor_role == "target" else "sourceUserId"
        if not record or int(record[owner_field]) != actor_user_id:
            raise PrivateSkillConflictError("分享记录不存在或无权处理")
        if int(record["receiveStatus"]) != 0:
            raise PrivateSkillConflictError("分享记录已处理")
        params = fill_audit_fields(
            {
                "id": share_id,
                "orgId": org_id,
                "receiveStatus": status,
                "acceptedSkillId": None,
                "responseTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            _scope_identity(identity),
            is_update=True,
        )
        updated = await connection.execute(
            text(get_sql("skill_share.update_status")), params
        )
        if updated.rowcount != 1:
            raise PrivateSkillConflictError("分享记录已被其他操作处理")


@router.post("/private/share/reject", summary="拒绝私有技能分享")
async def reject_private_skill_share(
    data: SkillShareAction,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    if actor.get("userType") != "external":
        return bad_request(message="只有外部用户可以拒绝技能分享")
    try:
        await _change_share_status_transaction(
            share_id=data.id,
            actor_user_id=int(actor["id"]),
            actor_role="target",
            status=2,
            identity=identity,
            org_id=_scope_org_id(identity),
        )
        return success(message="已拒绝技能分享")
    except PrivateSkillConflictError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("拒绝私有技能分享失败")
        return server_error("拒绝分享失败，已回滚")


@router.post("/private/share/revoke", summary="撤回私有技能分享")
async def revoke_private_skill_share(
    data: SkillShareAction,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    if actor.get("userType") != "external":
        return bad_request(message="只有外部用户可以撤回技能分享")
    try:
        await _change_share_status_transaction(
            share_id=data.id,
            actor_user_id=int(actor["id"]),
            actor_role="source",
            status=3,
            identity=identity,
            org_id=_scope_org_id(identity),
        )
        return success(message="技能分享已撤回")
    except PrivateSkillConflictError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("撤回私有技能分享失败")
        return server_error("撤回分享失败，已回滚")


@router.post("/private/library/publish", summary="发布私有技能到本组技能库")
async def publish_private_skill_to_library(
    data: SkillLibraryPublish,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    if actor.get("userType") != "external":
        return bad_request(message="只有外部用户可以发布私有技能")
    try:
        source_skill = await db_client.fetch_one(
            get_sql("private_skill.find_by_id"),
            {"id": data.skillId, "orgId": _scope_org_id(identity)},
        )
        if (
            not source_skill
            or int(source_skill["userId"]) != int(actor["id"])
            or int(source_skill["enabled"]) != 1
        ):
            return bad_request(message="私有技能不存在、已停用或不属于当前用户")
        duplicate = await db_client.fetch_one(
            get_sql("skill_library.find_duplicate_source"),
            {
                "orgId": _scope_org_id(identity),
                "sourceSkillId": data.skillId,
                "groupId": actor["groupId"],
            },
        )
        if duplicate:
            return bad_request(message="该技能已经发布到本组技能库")
        sub_skills_json = await _build_private_skill_bundle_snapshot(
            source_skill, _scope_org_id(identity)
        )
        params = {
            "orgId": _scope_org_id(identity),
            "sourceSkillId": source_skill["id"],
            "publisherUserId": actor["id"],
            "groupId": actor["groupId"],
            "skillName": source_skill["skillName"],
            "skillDescription": source_skill.get("skillDescription") or "",
            "skillLevelType": int(source_skill.get("skillLevelType") or 1),
            "subSkillsJson": sub_skills_json,
            "ruleContent": source_skill["ruleContent"],
        }
        fill_audit_fields(params, actor, is_update=False)
        inserted_id = await db_client.execute_insert(
            get_sql("skill_library.insert"), params
        )
        return success(data={"id": int(inserted_id)}, message="技能已发布到本组技能库")
    except PrivateSkillConflictError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("发布组内技能失败")
        return server_error("组内技能发布失败")


@router.post("/private/library/querylist", summary="分页查询用户组技能库")
async def query_group_skill_library(
    query: SkillLibraryQuery,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    group_id = (
        int(actor["groupId"])
        if actor.get("userType") == "external"
        else query.groupId
    )
    filters = {
        "orgId": _scope_org_id(identity),
        "groupId": group_id,
        "keyword": query.keyword,
    }
    try:
        count_row = await db_client.fetch_one(get_sql("skill_library.count"), filters)
        rows = await db_client.fetch_all(
            get_sql("skill_library.list"),
            {
                **filters,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        return success(data={
            "list": rows,
            "total": int(count_row.get("total", 0)) if count_row else 0,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询组内技能库失败")
        return server_error("组内技能库查询失败")


async def _copy_library_skill_transaction(
    *, library_id: int, target_user_id: int, group_id: int,
    identity: dict, org_id: int = 1
) -> int:
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")
    async with db_client.engine.begin() as connection:
        result = await connection.execute(
            text(get_sql("skill_library.find_for_update")),
            {"id": library_id, "orgId": org_id},
        )
        record = result.mappings().first()
        if (
            not record
            or int(record["groupId"]) != group_id
            or int(record["enabled"]) != 1
        ):
            raise PrivateSkillConflictError("技能库记录不存在或不属于当前用户组")
        return await _copy_private_skill_bundle(
            connection,
            source_record=record,
            target_user_id=target_user_id,
            identity=_scope_identity(identity),
            org_id=org_id,
        )


@router.post("/private/library/add", summary="添加组内技能到我的私有技能")
async def add_group_library_skill_to_mine(
    data: SkillLibraryAction,
    identity: dict = Depends(get_organization_scope),
):
    actor = _scope_identity(identity)
    if actor.get("userType") != "external":
        return bad_request(message="只有外部用户可以添加组内技能")
    try:
        record = await db_client.fetch_one(
            get_sql("skill_library.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if not record or int(record["groupId"]) != int(actor["groupId"]):
            return bad_request(message="只能添加同一用户组的技能")
        skill_id = await _copy_library_skill_transaction(
            library_id=data.id,
            target_user_id=int(actor["id"]),
            group_id=int(actor["groupId"]),
            identity=identity,
            org_id=_scope_org_id(identity),
        )
        return success(data={"skillId": skill_id}, message="已添加到我的私有技能")
    except PrivateSkillConflictError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("添加组内技能失败")
        return server_error("添加组内技能失败，已回滚")


@router.post("/private/library/delete", summary="物理删除组内技能库记录")
async def delete_group_skill_library_record(
    data: SkillLibraryAction,
    identity: dict = Depends(get_organization_scope),
):
    try:
        actor = _scope_identity(identity)
        record = await db_client.fetch_one(
            get_sql("skill_library.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if not record:
            return bad_request(message="技能库记录不存在")
        if (
            actor.get("userType") == "external"
            and int(record["publisherUserId"]) != int(actor["id"])
        ):
            return bad_request(message="只能删除自己发布的技能")
        affected = await db_client.execute(
            get_sql("skill_library.physical_delete"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if affected != 1:
            return server_error("技能库记录删除失败")
        return success(data={"id": data.id}, message="技能库记录已删除")
    except Exception:
        logger.exception("删除组内技能库记录失败")
        return server_error("技能库记录删除失败")
