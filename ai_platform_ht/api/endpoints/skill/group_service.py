"""独立技能组与用户组授权；不改变项目组的表结构组织和资源权限。"""
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.endpoints.skill.sql import get_template_sql as sql
from utils.context import fill_audit_fields
from utils.mysqldb import db_client


async def _group(org_id, group_id, conn=None):
    params = {'orgId': org_id, 'id': group_id}
    row = ((await conn.execute(text(sql('skill_group.lock')), params)).mappings().first()
           if conn is not None else await db_client.fetch_one(sql('skill_group.find'), params))
    if not row:
        raise ValueError('技能组不存在或不属于当前公司')
    return row


def _page(keyword, page_no, page_size, org_id, **extra):
    keyword = keyword.strip()
    return {'orgId': org_id, 'keyword': keyword, 'pattern': f'%{keyword}%',
            'limit': page_size, 'offset': (page_no - 1) * page_size, **extra}


async def group_page(org_id, keyword, page_no, page_size):
    params = _page(keyword, page_no, page_size, org_id)
    count = await db_client.fetch_one(sql('skill_group.count'), params)
    rows = [dict(row) for row in await db_client.fetch_all(sql('skill_group.list'), params)]
    bindings = await db_client.fetch_all(sql('skill_group.bindings'), {
        'orgId': org_id, 'groupIds': ','.join(str(row['id']) for row in rows)}) if rows else []
    for row in rows:
        row['userGroups'] = [{key: value for key, value in item.items() if key != 'skillGroupId'}
                             for item in bindings if item['skillGroupId'] == row['id']]
        row['userGroupIds'] = [item['id'] for item in row['userGroups']]
    return {'list': rows, 'total': int((count or {}).get('total', 0)), 'pageNo': page_no, 'pageSize': page_size}


async def save_group(scope, data, group_id=None):
    org_id = scope['orgId']
    params = {'orgId': org_id, **data.model_dump(), 'excludeId': group_id or 0}
    fill_audit_fields(params, scope['identity'], is_update=group_id is not None)
    try:
        async with db_client.engine.begin() as conn:
            if not (await conn.execute(text(sql('skill_group.organization_lock')), params)).mappings().first():
                raise ValueError('当前公司不存在或已停用')
            if group_id is not None:
                await _group(org_id, group_id, conn)
            selected = (await conn.execute(text(sql('skill_group.user_group_choices')), {
                'orgId': org_id, 'userGroupIds': ','.join(map(str, data.userGroupIds))})).mappings().all()
            if {row['id'] for row in selected} != set(data.userGroupIds):
                raise ValueError('所选用户组不存在或不属于当前公司')
            if (await conn.execute(text(sql('skill_group.duplicate')), params)).mappings().first():
                raise ValueError('当前公司已存在同名技能组')
            if group_id is None:
                result = await conn.execute(text(sql('skill_group.insert')), params)
                group_id = int(result.lastrowid)
            else:
                await conn.execute(text(sql('skill_group.update')), {**params, 'id': group_id})
            binding_params = {'orgId': org_id, 'id': group_id}
            await conn.execute(text(sql('skill_group.clear_bindings')), binding_params)
            for user_group_id in sorted(data.userGroupIds):
                await conn.execute(text(sql('skill_group.insert_binding')), {**binding_params, 'userGroupId': user_group_id})
    except IntegrityError:
        raise ValueError('技能组名称或用户组关联已变化，请刷新后重试') from None
    return {'id': group_id}


async def delete_group(org_id, group_id):
    params = {'orgId': org_id, 'id': group_id}
    async with db_client.engine.begin() as conn:
        await _group(org_id, group_id, conn)
        if (await conn.execute(text(sql('skill_group.references')), params)).mappings().all():
            raise ValueError('技能组内仍有技能，请先移出或删除技能；停用技能也属于引用')
        await conn.execute(text(sql('skill_group.clear_bindings')), params)
        await conn.execute(text(sql('skill_group.delete')), params)
    return {'id': group_id}


async def skill_page(org_id, keyword, page_no, page_size, group_id=None, *, active_only=False):
    if group_id is not None:
        await _group(org_id, group_id)
    params = _page(keyword, page_no, page_size, org_id, id=group_id, activeOnly=int(active_only))
    count_key, list_key = ('skill_count', 'skill_list') if group_id is not None else ('option_count', 'options')
    count = await db_client.fetch_one(sql(f'skill_group.{count_key}'), params)
    rows = await db_client.fetch_all(sql(f'skill_group.{list_key}'), params)
    return {'list': rows, 'total': int((count or {}).get('total', 0)), 'pageNo': page_no, 'pageSize': page_size}


async def change_group_skills(scope, group_id, skill_ids, *, remove=False):
    params = {'orgId': scope['orgId'], 'id': group_id, 'skillIds': ','.join(map(str, sorted(skill_ids)))}
    fill_audit_fields(params, scope['identity'], is_update=True)
    async with db_client.engine.begin() as conn:
        await _group(scope['orgId'], group_id, conn)
        rows = (await conn.execute(text(sql('skill_group.skill_lock')), params)).mappings().all()
        if {row['id'] for row in rows} != set(skill_ids):
            raise ValueError('所选技能不存在、属于其他公司或是个人技能')
        if remove:
            if any(row['accessGroupId'] != group_id for row in rows):
                raise ValueError('所选技能归组已变化，请刷新后重试')
        elif any(row['accessGroupId'] not in (None, group_id) for row in rows):
            raise ValueError('技能已经属于其他技能组，请先从原组移出')
        await conn.execute(text(sql('skill_group.detach' if remove else 'skill_group.attach')), params)
    return {'id': group_id, 'skillIds': skill_ids}


async def validate_sub_skills(conn, org_id, group_id, data, skill_type, project_group_id, exclude_id=0):
    ids = list(data.subSkillIds or [])
    if data.skillLevelType == 2:
        return
    if not ids:
        return
    if exclude_id and exclude_id in ids:
        raise ValueError('主技能不能绑定自己')
    rows = (await conn.execute(text(sql('skill_execution.sub_skill_choices')), {
        'orgId': org_id, 'id': group_id, 'skillType': skill_type, 'projectGroupId': project_group_id, 'skillIds': csv_ids(ids)
    })).mappings().all()
    if {int(row['id']) for row in rows} != set(ids):
        raise ValueError('所选子技能必须是当前技能组中已启用的子技能')


async def create_group_skill(scope, group_id, data):
    params = {'orgId': scope['orgId'], 'id': group_id, 'excludeId': 0, **data.model_dump(exclude={'mcpBindings', 'updateHierarchy'})}
    params['subSkillIds'] = csv_ids(data.subSkillIds)
    fill_audit_fields(params, scope['identity'])
    async with db_client.engine.begin() as conn:
        if not (await conn.execute(text(sql('skill_group.organization_lock')), params)).mappings().first():
            raise ValueError('当前公司不存在或已停用')
        await _group(scope['orgId'], group_id, conn)
        await validate_resources(conn, scope['orgId'], data)
        await validate_sub_skills(conn, scope['orgId'], group_id, data, 1, None)
        if (await conn.execute(text(sql('public_skill.find_duplicate_name')), params)).mappings().first():
            raise ValueError('已存在同名公共技能')
        result = await conn.execute(text(sql('skill_group.create_skill')), params)
        skill_id = int(result.lastrowid)
        await _write_execution(conn, scope, group_id, skill_id, data, 1)
        return {'id': skill_id}


def csv_ids(values):
    return ','.join(map(str, values)) or None


def parse_ids(value):
    return [int(item) for item in str(value or '').split(',') if item.strip().isdigit() and int(item) > 0]


async def validate_resources(conn, org_id, data):
    """按「角色」校验技能四模型，并校验数据表/知识库资源归属。"""
    from api.endpoints.skill.modular.skill import SKILL_MODEL_ROLES

    choices = [(field, kind, label, getattr(data, field, None))
               for field, kind, label in SKILL_MODEL_ROLES if getattr(data, field, None) is not None]
    if choices:
        rows = (await conn.execute(text(sql('skill_execution.model_choice')), {
            'orgId': org_id, 'modelIds': ','.join(str(item[3]) for item in choices)})).mappings().all()
        models = {row['id']: row for row in rows}
        for field, kind, label, model_id in choices:
            if model_id not in models or int(models[model_id]['type']) != kind:
                raise ValueError(f'{label}必须选择当前公司已启用、已配置密钥且用途匹配的模型')
    for field, key, message in (
        ('tableIds', 'table_choices_lock', '所选数据表不存在、已停用、未绑定沙箱或不属于当前公司'),
        ('tenantIds', 'tenant_choices', '所选知识库不存在、已停用、是个人库或不属于当前公司'),
    ):
        ids = getattr(data, field, [])
        if ids:
            rows = (await conn.execute(text(sql(f'skill_execution.{key}')), {'orgId': org_id, field: csv_ids(ids)})).mappings().all()
            if {int(row['id']) for row in rows} != set(ids):
                raise ValueError(message)


async def _write_execution(conn, scope, group_id, skill_id, data, skill_type):
    params = {'orgId': scope['orgId'], 'id': group_id, 'skillId': skill_id,
        'skillName': data.skillName, 'skillDescription': data.skillDescription, 'ruleContent': data.ruleContent,
        'skillLevelType': data.skillLevelType, 'subSkillIds': csv_ids(data.subSkillIds),
        'enabled': data.enabled, 'temperature': getattr(data, 'temperature', None),
        'intentLlmId': getattr(data, 'intentLlmId', None), 'taskLlmId': getattr(data, 'taskLlmId', None),
        'executLlmId': getattr(data, 'executLlmId', None), 'summaryLlmId': getattr(data, 'summaryLlmId', None),
        'tableIds': csv_ids(getattr(data, 'tableIds', [])), 'tenantIds': csv_ids(getattr(data, 'tenantIds', []))}
    fill_audit_fields(params, scope['identity'], is_update=True)
    await conn.execute(text(sql('skill_execution.update')), params)
    if data.mcpBindings is not None:
        from api.endpoints.mcp.service import replace_skill_bindings
        await replace_skill_bindings(conn, scope['orgId'], skill_id, skill_type, 0, data.mcpBindings)


async def save_execution(scope, group_id, skill_id, data):
    async with db_client.engine.begin() as conn:
        await _group(scope['orgId'], group_id, conn)
        await validate_resources(conn, scope['orgId'], data)
        params = {'orgId': scope['orgId'], 'id': group_id, 'skillId': skill_id}
        row = (await conn.execute(text(sql('skill_execution.lock')), params)).mappings().first()
        if not row:
            raise ValueError('技能不存在、归组已变更或不属于当前公司')
        rows = (await conn.execute(text(sql('skill_execution.skills')), {**params, 'skillIds': str(skill_id)})).mappings().all()
        current = rows[0]
        if data.updateHierarchy:
            await validate_sub_skills(conn, scope['orgId'], group_id, data, int(current['skillType']), current.get('projectGroupId'), skill_id)
            if int(current.get('skillLevelType') or 1) == 2 and data.skillLevelType == 1:
                cleanup = {'removedSkillId': skill_id, 'orgId': scope['orgId']}
                fill_audit_fields(cleanup, scope['identity'], is_update=True)
                await conn.execute(text(sql('skill_hierarchy.remove_reference')), cleanup)
        else:
            data = data.model_copy(update={
                'skillLevelType': int(current.get('skillLevelType') or 1),
                'subSkillIds': parse_ids(current.get('subSkillIds')),
            })
        duplicate = (await conn.execute(text(sql('skill_execution.duplicate_name')), {
            **params, 'skillName': data.skillName, 'excludeId': skill_id, 'skillType': current['skillType'],
            'projectGroupId': current['projectGroupId']})).mappings().first()
        if duplicate:
            raise ValueError('原技能范围中已经存在同名技能')
        await _write_execution(conn, scope, group_id, skill_id, data, current['skillType'])
    return {'id': skill_id}


def execution_record(row):
    value = dict(row)
    value['tableIds'] = parse_ids(value.get('tableIds'))
    value['tenantIds'] = parse_ids(value.get('tenantIds'))
    if value.get('temperature') is not None:
        value['temperature'] = float(value['temperature'])
    return value


async def execution_detail(org_id, group_id, skill_id):
    await _group(org_id, group_id)
    rows = await db_client.fetch_all(sql('skill_execution.skills'), {'orgId': org_id, 'skillIds': str(skill_id)})
    if not rows or rows[0]['accessGroupId'] != group_id or rows[0]['removed']:
        raise ValueError('技能不存在或归组已变更')
    result = execution_record(rows[0])
    result['tables'] = await db_client.fetch_all(sql('skill_execution.tables'), {'orgId': org_id, 'tableIds': csv_ids(result['tableIds']) or ''}) if result['tableIds'] else []
    return result


async def resource_options(org_id):
    return {name: await db_client.fetch_all(sql('skill_execution.' + key), {'orgId': org_id})
            for name, key in [('models', 'models'), ('tenants', 'tenants'), ('projectGroups', 'project_groups')]}


async def table_options(org_id, project_group_id, keyword, page_no, page_size):
    params = _page(keyword, page_no, page_size, org_id, projectGroupId=project_group_id)
    count = await db_client.fetch_one(sql('skill_execution.table_option_count'), params)
    rows = await db_client.fetch_all(sql('skill_execution.table_options'), params)
    return {'list': rows, 'total': int((count or {}).get('total', 0)), 'pageNo': page_no, 'pageSize': page_size}


async def accessible_skill_ids(org_id, skill_ids, identity):
    if not skill_ids:
        return set()
    same_org = bool(identity and identity.get('orgId') == org_id)
    internal = bool(same_org and identity.get('userType') == 'internal')
    rows = await db_client.fetch_all(sql('skill_group.accessible_skill_ids'), {
        'orgId': org_id, 'skillIds': ','.join(map(str, set(skill_ids))),
        'internal': int(internal), 'userId': identity['id'] if same_org else 0})
    return {int(row['id']) for row in rows}


async def require_skill_access(org_id, skill_ids, identity):
    if set(skill_ids) != await accessible_skill_ids(org_id, skill_ids, identity):
        raise ValueError('技能或关联子技能未授权给当前用户组、已停用或权限已变更，请联系管理员')


async def usable_groups(identity):
    return {'list': await db_client.fetch_all(sql('skill_group.usable_groups'), {
        'orgId': identity['orgId'], 'userId': identity['id']})}


def personal_record(row):
    value=execution_record(row)
    value['subSkillIds']=parse_ids(value.get('subSkillIds'))
    return value


async def personal_resources(identity):
    from api.endpoints.knowledge.service import KnowledgeFolders
    params={'orgId':identity['orgId'],'userId':identity['id'],'userType':'external','groupId':identity.get('groupId') or 0}
    allowed=await db_client.fetch_all(KnowledgeFolders.sql('tenant.ids_all_usable'),params)
    params['tenantIds']=csv_ids([row['id'] for row in allowed]) or ''
    return {'models':await db_client.fetch_all(sql('skill_execution.models'),params),
        'tables':await db_client.fetch_all(sql('personal_skill.table_options'),params),
        'tenants':await db_client.fetch_all(sql('personal_skill.knowledge_options'),params),
        'subSkills':await db_client.fetch_all(sql('personal_skill.sub_choices'),params)}


async def personal_skill_page(identity,keyword,page_no,page_size):
    params=_page(keyword,page_no,page_size,identity['orgId'],userId=identity['id'])
    count=await db_client.fetch_one(sql('imported.count'),{**params,'keyword':keyword.strip() or None,'enabled':None})
    rows=await db_client.fetch_all(sql('personal_skill.list'),params)
    return {'list':[personal_record(row) for row in rows],'total':int((count or {}).get('total',0)),
        'pageNo':page_no,'pageSize':page_size}


async def personal_skill_detail(identity,skill_id):
    params={'orgId':identity['orgId'],'userId':identity['id'],'skillId':skill_id}
    row=await db_client.fetch_one(sql('personal_skill.detail'),params)
    if not row:raise ValueError('只能查看和管理自己的技能')
    return personal_record(row)


async def save_personal_skill(identity,data,skill_id=0):
    from api.endpoints.knowledge.service import KnowledgeFolders
    params={**data.model_dump(exclude={'mcpBindings','updateHierarchy'}),'orgId':identity['orgId'],
        'userId':identity['id'],'skillId':skill_id,'groupId':identity.get('groupId') or 0}
    for field in ('subSkillIds','tableIds','tenantIds'):params[field]=csv_ids(params[field])
    fill_audit_fields(params,identity,is_update=bool(skill_id))
    async with db_client.engine.begin() as conn:
        # 与保存、删除个人技能共享公司锁，保证重复名称与主子引用校验原子完成。
        if not (await conn.execute(text(sql('skill_group.organization_lock')),params)).mappings().first():raise ValueError('当前公司已停用')
        if skill_id and not (await conn.execute(text(sql('personal_skill.lock')),params)).mappings().first():
            raise ValueError('只能编辑自己的技能')
        if (await conn.execute(text(sql('personal_skill.duplicate')),params)).mappings().first():
            raise ValueError('我的技能中已经存在同名技能')
        await validate_resources(conn,identity['orgId'],data.model_copy(update={'tableIds':[],'tenantIds':[]}))
        allowed_tables=(await conn.execute(text(sql('personal_skill.table_options')),params)).mappings().all() if data.tableIds else []
        if not set(data.tableIds)<={row['id'] for row in allowed_tables}:
            raise ValueError('所选数据表未授权、已停用或已被移出授权技能组')
        if data.tenantIds:
            tenants=(await conn.execute(text(KnowledgeFolders.sql('tenant.ids_usable')),{**params,'userType':'external'})).mappings().all()
            if set(data.tenantIds)!={row['id'] for row in tenants}:raise ValueError('所选知识库未授权或已停用')
        children=(await conn.execute(text(sql('personal_skill.sub_choices')),params)).mappings().all() if data.subSkillIds else []
        if skill_id in data.subSkillIds or not set(data.subSkillIds)<={row['id'] for row in children}:
            raise ValueError('只能关联本人已启用的子技能，不能关联自身')
        if skill_id and data.skillLevelType==1 and (await conn.execute(text(sql('personal_skill.parents')),params)).mappings().first():
            raise ValueError('该子技能仍被主技能引用，请先解除关联再改为主技能')
        result=await conn.execute(text(sql('personal_skill.update' if skill_id else 'personal_skill.insert')),params)
        saved_id=skill_id or int(result.lastrowid)
    return {'id':saved_id}


async def delete_personal_skill(identity,skill_id):
    from api.endpoints.mcp.sql import get_mcp_sql
    params={'orgId':identity['orgId'],'userId':identity['id'],'id':skill_id,'skillId':skill_id}
    async with db_client.engine.begin() as conn:
        await conn.execute(text(sql('skill_group.organization_lock')),params)
        if not (await conn.execute(text(sql('personal_skill.lock')),params)).mappings().first():raise ValueError('只能删除自己的技能')
        if (await conn.execute(text(sql('personal_skill.parents')),params)).mappings().first():raise ValueError('技能仍被主技能关联，请先解除关联')
        if (await conn.execute(text(sql('imported.references')),params)).mappings().first():raise ValueError('技能仍被智能体引用，请先解除绑定')
        await conn.execute(text(get_mcp_sql('binding.delete_all_skill')),params)
        await conn.execute(text(sql('imported.delete')),params)
    return {'id':skill_id}
