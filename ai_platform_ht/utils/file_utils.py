import io
import pandas as pd
from docx import Document
from pypdf import PdfReader

def extract_text_from_docx(file_contents: bytes) -> str:
    """从 docx 文件中提取文本"""
    doc = Document(io.BytesIO(file_contents))
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

def extract_text_from_pdf(file_contents: bytes) -> str:
    """从 pdf 文件中提取文本"""
    reader = PdfReader(io.BytesIO(file_contents))
    full_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text.append(text)
    return '\n'.join(full_text)

def extract_text_from_excel(file_contents: bytes) -> str:
    """从 excel 文件中提取文本 (读取所有 sheet)"""
    xl = pd.ExcelFile(io.BytesIO(file_contents))
    full_text = []
    for sheet_name in xl.sheet_names:
        df = xl.parse(sheet_name)
        # 将整个 df 转换为字符串，去除空值
        sheet_text = df.to_string(index=False, header=True)
        full_text.append(f"Sheet: {sheet_name}\n{sheet_text}")
    return '\n\n'.join(full_text)

def extract_text_by_extension(filename: str, file_contents: bytes) -> str:
    """根据文件扩展名提取文本"""
    ext = filename.lower().split('.')[-1]
    if ext == 'docx':
        return extract_text_from_docx(file_contents)
    elif ext == 'pdf':
        return extract_text_from_pdf(file_contents)
    elif ext in ['xlsx', 'xls']:
        return extract_text_from_excel(file_contents)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")
