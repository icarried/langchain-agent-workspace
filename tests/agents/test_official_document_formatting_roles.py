from __future__ import annotations

from src.agents.official_document_formatting.roles import (
    ParagraphRole,
    classify_paragraphs,
)


def test_classifies_normal_body_hierarchy_and_closing_blocks() -> None:
    texts = [
        "关于开展测试工作的请示",
        "公司领导：",
        "现将有关情况报告如下。",
        "一、主要事项",
        "（一）具体安排",
        "1. 实施步骤",
        "（1）报送材料",
        "附件：1. 测试材料清单",
        "2. 测试报价单",
        "技术支撑部",
        "2026年7月29日",
        "（联系人：张三，电话：12345678）",
    ]

    assert classify_paragraphs(texts) == [
        ParagraphRole.TITLE,
        ParagraphRole.MAIN_RECIPIENT,
        ParagraphRole.BODY,
        ParagraphRole.HEADING_1,
        ParagraphRole.HEADING_2,
        ParagraphRole.HEADING_3,
        ParagraphRole.HEADING_4,
        ParagraphRole.ATTACHMENT_NOTE,
        ParagraphRole.ATTACHMENT_ITEM,
        ParagraphRole.SIGNATURE,
        ParagraphRole.DATE,
        ParagraphRole.ANNOTATION,
    ]


def test_classifies_document_number_and_signer_before_title() -> None:
    texts = [
        "广智〔2026〕12号",
        "签发人：张三",
        "关于印发测试方案的通知",
        "公司各部门：",
    ]

    assert classify_paragraphs(texts) == [
        ParagraphRole.DOCUMENT_NUMBER,
        ParagraphRole.SIGNER_LINE,
        ParagraphRole.TITLE,
        ParagraphRole.MAIN_RECIPIENT,
    ]


def test_classifies_imprint_without_treating_it_as_recipient() -> None:
    texts = [
        "关于开展测试工作的通知",
        "公司各部门：",
        "请遵照执行。",
        "抄送：公司领导。",
        "综合管理部 2026年7月29日印发",
    ]

    assert classify_paragraphs(texts)[-2:] == [
        ParagraphRole.IMPRINT,
        ParagraphRole.IMPRINT,
    ]
