"""百炼文件解析器：把任意支持格式的文件转成纯文本，供 RAG 入库。

分流策略（按格式选最合适的百炼能力）：
- 纯文本(.md/.txt/.csv/.json/.html) → 直接 decode（快、免费、无损）
- 图片(.png/.jpg/.bmp/.gif) → 百炼 qwen-vl-ocr 专用 OCR（base64 直传，识别准）
- 文档(.pdf/.docx/.xlsx/.epub …) → 百炼 file-extract 上传 + qwen-long 提取全文
  （百炼内部已做 PDF/Word 解析，支持 150MB，上传/存储免费）

为什么图片用 qwen-vl-ocr 而非 qwen-long：qwen-long 是文档理解模型，对纯图片 OCR 能力弱、
易丢字；qwen-vl-ocr 是专用 OCR 模型，对图片文字识别准确得多。
"""
from __future__ import annotations

import base64
import logging
import os
import tempfile
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

# 直接 decode 的纯文本扩展名（不走 LLM，省时省钱）
_TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".xml", ".log"}
# 图片扩展名 → 走 qwen-vl-ocr
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
# 百炼 file-extract 官方支持的文档格式 → 走 qwen-long
_DOC_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".epub", ".mobi"}
SUPPORTED_EXTS = _TEXT_EXTS | _IMAGE_EXTS | _DOC_EXTS


def _bailian_client():
    from openai import OpenAI

    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def _extract_image_via_ocr(file_bytes: bytes, filename: str) -> str:
    """图片走百炼 qwen-vl-ocr（专用 OCR，base64 直传）。"""
    ext = Path(filename).suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if ext == "jpg" else ext
    data_url = f"data:image/{mime};base64,{base64.b64encode(file_bytes).decode()}"
    client = _bailian_client()
    resp = client.chat.completions.create(
        model=settings.ocr_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {
                        "type": "text",
                        "text": "请准确提取图片中的全部文字内容，原样输出，不要总结、不要添加描述。"
                    },
                ],
            }
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _extract_doc_via_bailian(file_bytes: bytes, filename: str) -> str:
    """文档走百炼 file-extract 上传 + qwen-long 提取全文，用完删除远端文件。"""
    ext = Path(filename).suffix.lower() or ".bin"
    client = _bailian_client()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        fobj = client.files.create(file=open(tmp_path, "rb"), purpose="file-extract")
        file_id = fobj.id
        logger.info("百炼文件上传: %s -> %s", filename, file_id)
        try:
            resp = client.chat.completions.create(
                model=settings.file_extract_model,
                messages=[
                    {"role": "system", "content": f"fileid://{file_id}"},
                    {
                        "role": "user",
                        "content": (
                            "请完整、原样提取这篇文档的全部文本内容，保留章节结构和层次，"
                            "不要总结、不要省略。"
                        ),
                    },
                ],
            )
            return (resp.choices[0].message.content or "").strip()
        finally:
            try:
                client.files.delete(file_id)
            except Exception:  # noqa: BLE001
                logger.warning("删除百炼远端文件失败: %s", file_id)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:  # noqa: BLE001
            pass


def extract_text(file_bytes: bytes, filename: str) -> str:
    """把任意支持格式的文件转为纯文本（按格式自动分流到最合适的百炼能力）。"""
    ext = Path(filename).suffix.lower()
    if ext in _TEXT_EXTS:
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("utf-8", errors="ignore")
    if ext in _IMAGE_EXTS:
        return _extract_image_via_ocr(file_bytes, filename)
    if ext in _DOC_EXTS:
        return _extract_doc_via_bailian(file_bytes, filename)
    # 未知扩展名：先尝试 decode，不行就当文档走百炼
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return _extract_doc_via_bailian(file_bytes, filename)


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTS
