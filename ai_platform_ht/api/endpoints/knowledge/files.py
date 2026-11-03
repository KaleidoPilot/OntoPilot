"""保存上传时的原始 Word/Excel，下载时按原文件返回。"""

import io
import re
import zipfile
from pathlib import Path
from utils.file_utils import extract_text_by_extension

OFFICE_EXTENSIONS = {".docx", ".xlsx", ".xls"}
MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".txt": "text/plain; charset=utf-8",
}
STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage" / "knowledge"
FILE_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{12}$")


def extract_complete_text(filename: str, contents: bytes) -> str:
    """沿用公共解析器，补齐 Word 正文中交错的表格，不修改公共 utils。"""
    extension = Path(filename).suffix.lower()
    if extension in {'.docx', '.xlsx'}:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 80 * 1024 * 1024:
                raise ValueError('Office 文件解压后超过80MB，请拆分后上传')
    if extension != '.docx':
        return extract_text_by_extension(filename, contents)
    from docx import Document
    from docx.table import Table
    document = Document(io.BytesIO(contents))
    if not document.tables:
        return extract_text_by_extension(filename, contents)
    blocks = []
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            blocks.append('【表格】\n' + '\n'.join('\t'.join(cell.text for cell in row.cells) for row in block.rows))
        elif block.text.strip():
            blocks.append(block.text)
    return '\n\n'.join(blocks)


def document_warnings(filename: str, contents: bytes) -> list[str]:
    if Path(filename).suffix.lower() not in {'.docx', '.xlsx'}:
        return []
    with zipfile.ZipFile(io.BytesIO(contents)) as archive:
        if any(name.startswith(('word/media/', 'word/charts/', 'xl/media/', 'xl/charts/')) for name in archive.namelist()):
            return [f'{filename} 含图片或图表，目前仅提取文字和表格，图像中的信息尚未识别。']
    return []


def split_knowledge_text(value: str, max_bytes: int = 6000) -> list[str]:
    """按 UTF-8 字符边界分段，所有段拼接必须等于完整原文。"""
    if max_bytes < 4:
        raise ValueError('分段字节数至少为4')
    data = value.encode('utf-8')
    parts = []
    start = 0
    while start < len(data):
        end = min(start + max_bytes, len(data))
        while end < len(data) and data[end] & 0xC0 == 0x80:
            end -= 1
        # 优先在段落边界结束，保持表格行和句子尽量连续。
        newline = data.rfind(b'\n', start + (end - start) // 2, end)
        if newline >= 0:
            end = newline + 1
        parts.append(data[start:end].decode('utf-8'))
        start = end
    return parts


def office_extension(filename: str) -> str | None:
    extension = Path(filename).suffix.lower()
    return extension if extension in OFFICE_EXTENSIONS else None


def stored_path(file_id: str, extension: str) -> Path:
    if not FILE_ID_PATTERN.fullmatch(file_id) or extension not in OFFICE_EXTENSIONS:
        raise ValueError("原始文件标识不正确")
    return STORAGE_ROOT / f"{file_id}{extension}"


def save_original(file_id: str, filename: str, contents: bytes) -> None:
    extension = office_extension(Path(filename).name)
    if extension is None:
        return
    path = stored_path(file_id, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def read_original(file_id: str, filename: str) -> tuple[bytes, str, str] | None:
    safe_name = Path(str(filename or "")).name
    extension = office_extension(safe_name)
    if extension is None or not FILE_ID_PATTERN.fullmatch(str(file_id or "")):
        return None
    path = stored_path(str(file_id), extension)
    if not path.is_file():
        return None
    return path.read_bytes(), safe_name, MEDIA_TYPES[extension]


def delete_original(file_id: str, filename: str) -> None:
    safe_name = Path(str(filename or "")).name
    extension = office_extension(safe_name)
    if extension is None or not FILE_ID_PATTERN.fullmatch(str(file_id or "")):
        return
    path = stored_path(str(file_id), extension)
    if path.is_file():
        path.unlink()


def text_download_name(filename: str, title: str) -> str:
    raw = Path(str(filename or "")).name.replace("\r", "").replace("\n", "").replace('"', "")
    stem = Path(raw).stem if raw and raw not in {".", ".."} else ""
    if not stem:
        stem = str(title or "知识资料").replace("\r", "").replace("\n", "").replace('"', "") or "知识资料"
    return f"{stem[:160]}.txt"
