from __future__ import annotations

import re

from .schemas import CandidateProfile, CandidateScore, ScreeningCriteria


def score_candidate(candidate: CandidateProfile, criteria: ScreeningCriteria) -> CandidateScore:
    text = candidate.text.lower()
    matched_hard = tuple(condition for condition in criteria.hard_conditions if _condition_matches(condition, text))
    missing_hard = tuple(condition for condition in criteria.hard_conditions if condition not in matched_hard)
    matched_bonus = tuple(condition for condition in criteria.bonus_conditions if _condition_matches(condition, text))
    reject_hits = tuple(condition for condition in criteria.reject_conditions if _condition_matches(condition, text))
    risks = _detect_risks(candidate.text)
    strengths = _detect_strengths(candidate.text, matched_bonus)

    if reject_hits:
        status = "excluded"
        total_score = 0
        recommendation = "不推荐，命中淘汰条件。"
    elif missing_hard:
        status = "not_met"
        total_score = min(59, _base_score(candidate.text, criteria) + len(matched_bonus) * 3)
        recommendation = "暂不推荐，硬性条件不完整。"
    else:
        status = "qualified"
        total_score = min(100, _base_score(candidate.text, criteria) + len(matched_bonus) * 5 - len(risks) * 3)
        recommendation = _recommendation(total_score)

    return CandidateScore(
        filename=candidate.filename,
        display_name=candidate.display_name,
        status=status,
        total_score=max(0, total_score),
        matched_hard_conditions=matched_hard,
        missing_hard_conditions=missing_hard,
        matched_bonus_conditions=matched_bonus,
        reject_hits=reject_hits,
        strengths=tuple(strengths),
        risks=tuple(risks),
        recommendation=recommendation,
    )


def _condition_matches(condition: str, normalized_text: str) -> bool:
    tokens = [token.strip().lower() for token in re.split(r"[\s/、,，；;]+", condition) if token.strip()]
    if not tokens:
        return False
    return any(token in normalized_text for token in tokens)


def _base_score(text: str, criteria: ScreeningCriteria) -> int:
    score = 45
    if re.search(r"(本科|学士|硕士|研究生|博士)", text):
        score += min(criteria.education_weight, 15)
    if re.search(r"(\d+\s*年|工作经历|项目经历|实习经历)", text):
        score += min(criteria.experience_weight, 20)
    if re.search(r"(python|java|sql|ai|算法|数据|传媒|内容|运营|开发|系统)", text, re.IGNORECASE):
        score += min(criteria.skill_weight, 20)
    if re.search(r"(项目|成果|负责|上线|交付|获奖)", text):
        score += min(criteria.project_weight, 10)
    return score


def _detect_risks(text: str) -> list[str]:
    risks: list[str] = []
    lowered = text.lower()
    if any(token in lowered for token in ["忽略前面的", "强制通过", "ignore previous"]):
        risks.append("发现疑似提示词注入或操控筛选文本。")
    years = [int(year) for year in re.findall(r"(20\d{2})", text)]
    if len(years) >= 2 and years != sorted(years):
        risks.append("时间线年份顺序疑似不连续，建议人工核验。")
    if "频繁跳槽" in text:
        risks.append("简历自述存在频繁跳槽风险。")
    return risks


def _detect_strengths(text: str, matched_bonus: tuple[str, ...]) -> list[str]:
    strengths = list(matched_bonus)
    if re.search(r"(985|211|双一流|qs\s*100)", text, re.IGNORECASE):
        strengths.append("教育背景有高校层次亮点。")
    if re.search(r"(上线|落地|交付|获奖|专利|论文)", text):
        strengths.append("项目成果或产出有明确线索。")
    return strengths or ["简历包含可用于初筛的基础信息。"]


def _recommendation(score: int) -> str:
    if score >= 85:
        return "强烈推荐进入面试。"
    if score >= 75:
        return "推荐进入面试。"
    if score >= 60:
        return "可进入备选池或补充核验。"
    return "暂不推荐。"

