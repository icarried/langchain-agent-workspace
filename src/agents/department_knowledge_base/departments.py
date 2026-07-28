from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Department:
    knowledge_id: str
    display_name: str


DEPARTMENTS: dict[str, Department] = {
    item.knowledge_id: item
    for item in (
        Department("company-leadership", "公司领导层"),
        Department("marketing", "市场营销部"),
        Department("technical-support", "技术支撑部"),
        Department("project-delivery", "项目交付部"),
        Department("operations-service", "运维服务部"),
        Department("procurement-implementation", "采购实施部"),
        Department("finance", "经营财务部"),
        Department("general-management", "综合管理部"),
    )
}


def get_department(knowledge_id: str) -> Department:
    try:
        return DEPARTMENTS[knowledge_id]
    except KeyError as exc:
        allowed = ", ".join(DEPARTMENTS)
        raise ValueError(
            f"unknown knowledge_id {knowledge_id!r}; allowed values: {allowed}"
        ) from exc
