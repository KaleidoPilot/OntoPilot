from fastapi import APIRouter, Depends, UploadFile, File, Response
from sqlalchemy import select, func, desc, insert, update, delete
from utils.response import success, server_error
from utils.mysqldb import db_client
from utils.context import get_current_user, fill_audit_fields
from pydantic import BaseModel
from typing import Dict, Any, List
import pandas as pd
import io
from urllib.parse import quote
from datetime import datetime

from api.endpoints.modelconfig.modular.modelconfig import (
    Modelconfig, ModelconfigResponse, ModelconfigQueryRequest, ModelconfigCreate, ModelconfigUpdate
)
from api.endpoints.modelconfig.sql.tables import modelconfig_table
from api.endpoints.user.dependencies import get_super_administrator

router = APIRouter(dependencies=[Depends(get_super_administrator)])

# 字段映射配置，用于导入导出和模板下载
MODELCONFIG_FIELD_MAP = {
    "model": "模型标识",
    "apiKey": "模型服务API密钥（由应用层加密后存储）",
    "baseUrl": "模型服务基础地址",
    "type": "模型类型：1意图，2任务分解模型，3执行模型（代码），4总结模型",
    "enabled": "是否启用：1启用，0禁用",
    "removed": "是否删除：1已删除，0未删除",
    "createUserId": "创建人ID",
    "createUserName": "创建人姓名",
    "createTime": "创建时间",
    "updateUserId": "更新人ID",
    "updateUserName": "更新人姓名",
    "updateTime": "更新时间"
}

class DeleteRequest(BaseModel):
    id: int


@router.post("/querylist", response_model=dict, summary="查询列表")
async def query_modelconfig_list(query: ModelconfigQueryRequest):
    try:
        base_query = select(modelconfig_table)
        
        # 默认过滤逻辑删除和无效数据
        if hasattr(modelconfig_table.c, 'removed'):
            base_query = base_query.where(modelconfig_table.c.removed == 0)
        if hasattr(modelconfig_table.c, 'enabled'):
            base_query = base_query.where(modelconfig_table.c.enabled == 1)
            
        filter_data = query.model_dump(exclude={"pageNo", "pageSize"}, exclude_unset=True, exclude_none=True)
        
        for field, value in filter_data.items():
            if value is not None and value != "":
                column = getattr(modelconfig_table.c, field, None)
                if column is not None:
                    if isinstance(value, str):
                        base_query = base_query.where(column.like(f"%{value}%"))
                    else:
                        base_query = base_query.where(column == value)
                        
        count_query = select(func.count()).select_from(base_query.subquery())
        total_records = await db_client.fetch_one(count_query)
        total = list(total_records.values())[0] if total_records else 0
        
        limit = query.pageSize
        offset = (query.pageNo - 1) * query.pageSize
        
        # 默认按创建时间倒序
        if hasattr(modelconfig_table.c, 'createTime'):
            list_query = base_query.order_by(desc(modelconfig_table.c.createTime)).limit(limit).offset(offset)
        else:
            list_query = base_query.limit(limit).offset(offset)
            
        records = await db_client.fetch_all(list_query)
        validated_records = [ModelconfigResponse(**record).model_dump() for record in records]
        
        return success(data={
            "total": total,
            "list": validated_records,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize
        })
    except Exception as e:
        return server_error(f"查询失败: {str(e)}")


@router.post("/insert", summary="新增记录")
async def insert_modelconfig(data: ModelconfigCreate, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        insert_data = data.model_dump(exclude_unset=True, exclude_none=True)
        insert_data = fill_audit_fields(insert_data, user, is_update=False)
        stmt = insert(modelconfig_table).values(**insert_data)
        await db_client.execute(stmt)
        return success(message="新增成功")
    except Exception as e:
        return server_error(f"新增失败: {str(e)}")

@router.post("/update", summary="修改记录")
async def update_modelconfig(data: ModelconfigUpdate, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        update_data = data.model_dump(exclude={"id"}, exclude_unset=True, exclude_none=True)
        if not update_data:
            return server_error("没有需要更新的字段")
            
        update_data = fill_audit_fields(update_data, user, is_update=True)
        stmt = update(modelconfig_table).where(modelconfig_table.c.id == getattr(data, 'id')).values(**update_data)
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="修改成功")
        return server_error("修改失败，记录不存在")
    except Exception as e:
        return server_error(f"修改失败: {str(e)}")

@router.post("/delete", summary="物理删除")
async def delete_modelconfig(req: DeleteRequest):
    try:
        stmt = delete(modelconfig_table).where(modelconfig_table.c.id == getattr(req, 'id'))
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="删除成功")
        return server_error("删除失败，记录不存在")
    except Exception as e:
        return server_error(f"删除失败: {str(e)}")

@router.post("/deleteLj", summary="逻辑删除")
async def delete_lj_modelconfig(req: DeleteRequest, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not hasattr(modelconfig_table.c, 'removed') or not hasattr(modelconfig_table.c, 'enabled'):
            return server_error("该表不支持逻辑删除(缺少 removed 或 enabled 字段)")
            
        update_data = {"removed": 1, "enabled": 0}
        update_data = fill_audit_fields(update_data, user, is_update=True)
        
        stmt = update(modelconfig_table).where(modelconfig_table.c.id == getattr(req, 'id')).values(**update_data)
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="逻辑删除成功")
        return server_error("逻辑删除失败，记录不存在")
    except Exception as e:
        return server_error(f"逻辑删除失败: {str(e)}")


@router.get("/downloadTemplate", summary="下载导入模板")
async def download_template_modelconfig():
    try:
        # 生成空数据，仅包含表头
        df = pd.DataFrame(columns=list(MODELCONFIG_FIELD_MAP.values()))
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='模板')
        output.seek(0)
        
        filename = quote(f"Modelconfig导入模板.xlsx")
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }
        return Response(content=output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
    except Exception as e:
        return server_error(f"下载模板失败: {str(e)}")

@router.post("/export", summary="导出数据")
async def export_modelconfig(query: ModelconfigQueryRequest):
    try:
        base_query = select(modelconfig_table)
        
        if hasattr(modelconfig_table.c, 'removed'):
            base_query = base_query.where(modelconfig_table.c.removed == 0)
        if hasattr(modelconfig_table.c, 'enabled'):
            base_query = base_query.where(modelconfig_table.c.enabled == 1)
            
        filter_data = query.model_dump(exclude={"pageNo", "pageSize"}, exclude_unset=True, exclude_none=True)
        
        for field, value in filter_data.items():
            if value is not None and value != "":
                column = getattr(modelconfig_table.c, field, None)
                if column is not None:
                    if isinstance(value, str):
                        base_query = base_query.where(column.like(f"%{value}%"))
                    else:
                        base_query = base_query.where(column == value)
                        
        if hasattr(modelconfig_table.c, 'createTime'):
            list_query = base_query.order_by(desc(modelconfig_table.c.createTime))
        else:
            list_query = base_query
            
        records = await db_client.fetch_all(list_query)
        
        export_data = []
        for record in records:
            row = {}
            record_dict = dict(record) if not hasattr(record, '_mapping') else dict(record._mapping)
            for field, col_name in MODELCONFIG_FIELD_MAP.items():
                row[col_name] = record_dict.get(field)
            export_data.append(row)
            
        df = pd.DataFrame(export_data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='数据导出')
        output.seek(0)
        
        filename = quote(f"Modelconfig数据导出_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx")
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }
        return Response(content=output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
    except Exception as e:
        return server_error(f"导出失败: {str(e)}")


@router.post("/import", summary="导入数据")
async def import_modelconfig(file: UploadFile = File(...), user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            return server_error("请上传 Excel 或 CSV 文件")
            
        contents = await file.read()
        import io
        if file.filename.endswith('.csv'):
            df = None
            for enc in ['utf-8', 'gb18030', 'utf-8-sig', 'gbk']:
                try:
                    df = pd.read_csv(io.BytesIO(contents), encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                df = pd.read_csv(io.BytesIO(contents), encoding='gb18030', encoding_errors='replace')
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        reverse_map = {v: k for k, v in MODELCONFIG_FIELD_MAP.items()}
        
        success_count = 0
        error_list = []
        
        for index, row in df.iterrows():
            try:
                row_data = {}
                for col_name, val in row.items():
                    if col_name in reverse_map and pd.notna(val):
                        row_data[reverse_map[col_name]] = val
                        
                if not row_data:
                    continue
                    
                insert_data = fill_audit_fields(row_data, user, is_update=False)
                stmt = insert(modelconfig_table).values(**insert_data)
                await db_client.execute(stmt)
                success_count += 1
            except Exception as row_e:
                error_list.append(f"第 {index + 2} 行导入失败: {str(row_e)}")
                
        if error_list:
            return success(message=f"导入完成，成功 {success_count} 条，失败 {len(error_list)} 条", data={"errors": error_list})
        return success(message=f"导入成功，共 {success_count} 条")
    except Exception as e:
        return server_error(f"导入失败: {str(e)}")
