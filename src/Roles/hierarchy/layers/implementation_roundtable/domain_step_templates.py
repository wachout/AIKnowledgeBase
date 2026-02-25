# -*- coding: utf-8 -*-
"""
领域知识实施步骤模板

为第二层「实施与专业领域知识划分层」提供各领域的步骤细化指南，
确保每个知识领域的实施步骤被充分展开和扩展。
"""

from typing import Dict, List, Any

# 各专业领域的实施步骤模板与扩展指南
# 用于指导专家在提案时输出更细化的步骤
DOMAIN_STEP_TEMPLATES: Dict[str, Dict[str, Any]] = {
    # 软件领域
    "软件架构": {
        "min_steps": 6,
        "phase_hints": ["需求澄清", "架构设计", "技术选型", "接口定义", "部署架构", "验收标准"],
        "step_expansion_hint": "每个步骤需包含：输入条件、具体动作、产出物、验收标准",
    },
    "前端开发": {
        "min_steps": 6,
        "phase_hints": ["需求拆解", "组件设计", "实现开发", "联调测试", "性能优化", "文档与交付"],
        "step_expansion_hint": "细化到：页面/组件级、交互状态、响应式适配",
    },
    "后端开发": {
        "min_steps": 6,
        "phase_hints": ["接口设计", "数据建模", "业务逻辑实现", "单元测试", "集成联调", "部署上线"],
        "step_expansion_hint": "细化到：API 契约、错误处理、日志监控",
    },
    "数据库": {
        "min_steps": 5,
        "phase_hints": ["需求分析", "模型设计", "索引优化", "迁移脚本", "备份与恢复"],
        "step_expansion_hint": "细化到：表结构、索引策略、查询优化",
    },
    "运维/DevOps": {
        "min_steps": 5,
        "phase_hints": ["环境规划", "CI/CD 配置", "监控告警", "日志聚合", "运维文档"],
        "step_expansion_hint": "细化到：流水线步骤、告警阈值、回滚策略",
    },
    "AI/机器学习": {
        "min_steps": 6,
        "phase_hints": ["数据准备", "特征工程", "模型选型", "训练与调参", "评估与部署", "持续迭代"],
        "step_expansion_hint": "细化到：数据质量检查、评估指标、A/B 测试",
    },
    "安全": {
        "min_steps": 5,
        "phase_hints": ["威胁建模", "安全设计", "渗透测试", "修复验证", "安全文档"],
        "step_expansion_hint": "细化到：攻击面、防护措施、合规检查",
    },
    # 硬件领域
    "硬件工程": {
        "min_steps": 6,
        "phase_hints": ["需求分析", "方案选型", "原理图设计", "PCB 设计", "样机制作", "测试验证"],
        "step_expansion_hint": "细化到：元器件选型、信号完整性、散热设计",
    },
    "嵌入式": {
        "min_steps": 6,
        "phase_hints": ["需求分解", "驱动开发", "应用逻辑", "联调测试", "固件发布", "文档交付"],
        "step_expansion_hint": "细化到：外设驱动、中断处理、功耗优化",
    },
    "电路设计": {
        "min_steps": 5,
        "phase_hints": ["规格确定", "电路仿真", "原理图", "Layout", "制板与焊接"],
        "step_expansion_hint": "细化到：关键参数、仿真条件、测试点",
    },
    "PCB 设计": {
        "min_steps": 5,
        "phase_hints": ["叠层规划", "布局", "布线", "DRC 检查", "Gerber 输出"],
        "step_expansion_hint": "细化到：阻抗控制、EMC 设计、可制造性",
    },
    # 科学领域
    "数据科学": {
        "min_steps": 6,
        "phase_hints": ["问题定义", "数据采集", "探索分析", "建模", "验证", "报告与部署"],
        "step_expansion_hint": "细化到：假设检验、可视化、可复现性",
    },
    "材料科学": {
        "min_steps": 5,
        "phase_hints": ["材料选型", "配方/工艺", "制备", "表征测试", "分析报告"],
        "step_expansion_hint": "细化到：工艺参数、测试标准、数据分析",
    },
    "化学": {
        "min_steps": 5,
        "phase_hints": ["方案设计", "实验准备", "实验执行", "数据分析", "报告撰写"],
        "step_expansion_hint": "细化到：反应条件、安全措施、重复性验证",
    },
    "物理": {
        "min_steps": 5,
        "phase_hints": ["理论推导", "实验设计", "数据采集", "误差分析", "结论与论文"],
        "step_expansion_hint": "细化到：实验变量、测量精度、不确定度",
    },
    "生物": {
        "min_steps": 5,
        "phase_hints": ["实验设计", "样本准备", "实验操作", "数据处理", "结果解释"],
        "step_expansion_hint": "细化到：对照设计、重复数、统计学方法",
    },
    # 管理与规划
    "项目规划": {
        "min_steps": 6,
        "phase_hints": ["范围界定", "WBS 分解", "里程碑", "资源分配", "风险登记", "进度基线"],
        "step_expansion_hint": "细化到：可交付物、责任人、验收标准",
    },
    "成本估算": {
        "min_steps": 5,
        "phase_hints": ["成本分解", "工时估算", "物料清单", "风险储备", "预算编制"],
        "step_expansion_hint": "细化到：估算依据、假设条件、敏感性",
    },
    "质量管理": {
        "min_steps": 5,
        "phase_hints": ["质量计划", "标准定义", "检查点", "缺陷管理", "持续改进"],
        "step_expansion_hint": "细化到：检查清单、度量指标、改进措施",
    },
    "风险分析": {
        "min_steps": 5,
        "phase_hints": ["风险识别", "评估", "应对策略", "监控计划", "复盘机制"],
        "step_expansion_hint": "细化到：触发条件、责任人、升级机制",
    },
    # 产品与设计
    "产品设计": {
        "min_steps": 5,
        "phase_hints": ["用户研究", "需求定义", "概念设计", "原型验证", "规格输出"],
        "step_expansion_hint": "细化到：用户故事、验收场景、优先级",
    },
    "用户体验": {
        "min_steps": 5,
        "phase_hints": ["用户旅程", "信息架构", "交互设计", "可用性测试", "迭代优化"],
        "step_expansion_hint": "细化到：任务流程、异常状态、可访问性",
    },
    # 通用
    "通用": {
        "min_steps": 5,
        "phase_hints": ["需求理解", "方案设计", "执行实施", "检查验证", "交付总结"],
        "step_expansion_hint": "每个步骤需包含：做什么、怎么做、产出是什么",
    },
}


def get_domain_template(domain: str) -> Dict[str, Any]:
    """
    根据领域名称获取步骤模板。
    支持模糊匹配（如「软件架构设计」匹配「软件架构」）。
    """
    domain_lower = (domain or "").strip().lower()
    for key, template in DOMAIN_STEP_TEMPLATES.items():
        if key in domain or domain in key or key.lower() in domain_lower:
            return template
    return DOMAIN_STEP_TEMPLATES["通用"]


def get_min_steps_for_domain(domain: str) -> int:
    """获取该领域建议的最小步骤数"""
    t = get_domain_template(domain)
    return t.get("min_steps", 5)


def get_phase_hints_for_domain(domain: str) -> List[str]:
    """获取该领域的阶段提示"""
    t = get_domain_template(domain)
    return t.get("phase_hints", [])


def get_step_expansion_hint(domain: str) -> str:
    """获取该领域的步骤扩展提示"""
    t = get_domain_template(domain)
    return t.get("step_expansion_hint", "细化到可执行级别")
