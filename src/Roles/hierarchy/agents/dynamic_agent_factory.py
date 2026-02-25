"""
动态智能体工厂

根据科学家分析结果，动态创建各领域专家智能体。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging

from .dynamic_expert_agent import DynamicExpertAgent


logger = logging.getLogger(__name__)


@dataclass
class ExpertTemplate:
    """专家模板"""
    role: str
    name: str
    domain: str
    default_expertise: List[str] = field(default_factory=list)


class DynamicAgentFactory:
    """
    动态智能体工厂
    
    根据科学家分析结果，批量创建各领域专家智能体。
    支持预定义模板和自定义专家。
    """
    
    # 预定义领域专家模板
    EXPERT_TEMPLATES: Dict[str, ExpertTemplate] = {
        # ============ 软件领域 ============
        "software_architect": ExpertTemplate(
            role="software_architect",
            name="软件架构师",
            domain="软件架构设计",
            default_expertise=["系统架构", "技术选型", "模块设计", "性能优化"]
        ),
        "frontend_engineer": ExpertTemplate(
            role="frontend_engineer",
            name="前端工程师",
            domain="用户界面开发",
            default_expertise=["UI设计", "交互实现", "前端框架", "性能优化"]
        ),
        "backend_engineer": ExpertTemplate(
            role="backend_engineer",
            name="后端工程师",
            domain="服务端开发",
            default_expertise=["API设计", "业务逻辑", "数据处理", "系统集成"]
        ),
        "database_expert": ExpertTemplate(
            role="database_expert",
            name="数据库专家",
            domain="数据存储设计",
            default_expertise=["数据建模", "查询优化", "数据迁移", "高可用设计"]
        ),
        "devops_engineer": ExpertTemplate(
            role="devops_engineer",
            name="运维工程师",
            domain="部署与运维",
            default_expertise=["CI/CD", "容器化", "监控告警", "自动化运维"]
        ),
        "ai_engineer": ExpertTemplate(
            role="ai_engineer",
            name="AI工程师",
            domain="人工智能开发",
            default_expertise=["模型训练", "算法优化", "数据处理", "模型部署"]
        ),
        "security_expert": ExpertTemplate(
            role="security_expert",
            name="安全专家",
            domain="信息安全",
            default_expertise=["安全审计", "漏洞分析", "加密方案", "合规检查"]
        ),
        "test_engineer": ExpertTemplate(
            role="test_engineer",
            name="测试工程师",
            domain="软件测试",
            default_expertise=["测试策略", "自动化测试", "性能测试", "质量保障"]
        ),
        
        # ============ 硬件领域 ============
        "hardware_engineer": ExpertTemplate(
            role="hardware_engineer",
            name="硬件工程师",
            domain="硬件设计",
            default_expertise=["电路设计", "元器件选型", "热设计", "可靠性分析"]
        ),
        "embedded_engineer": ExpertTemplate(
            role="embedded_engineer",
            name="嵌入式工程师",
            domain="嵌入式开发",
            default_expertise=["固件开发", "驱动开发", "实时系统", "低功耗设计"]
        ),
        "circuit_designer": ExpertTemplate(
            role="circuit_designer",
            name="电路设计师",
            domain="电路设计",
            default_expertise=["模拟电路", "数字电路", "电源设计", "信号完整性"]
        ),
        "pcb_engineer": ExpertTemplate(
            role="pcb_engineer",
            name="PCB工程师",
            domain="PCB设计",
            default_expertise=["布局布线", "阻抗控制", "EMC设计", "热管理"]
        ),
        "mechanical_engineer": ExpertTemplate(
            role="mechanical_engineer",
            name="机械工程师",
            domain="机械设计",
            default_expertise=["结构设计", "运动分析", "材料选择", "工艺规划"]
        ),
        
        # ============ 科学领域 ============
        "materials_scientist": ExpertTemplate(
            role="materials_scientist",
            name="材料学家",
            domain="材料科学",
            default_expertise=["材料分析", "性能测试", "工艺优化", "新材料研发"]
        ),
        "chemist": ExpertTemplate(
            role="chemist",
            name="化学家",
            domain="化学工程",
            default_expertise=["化学合成", "反应优化", "分析测试", "工艺放大"]
        ),
        "physicist": ExpertTemplate(
            role="physicist",
            name="物理学家",
            domain="物理应用",
            default_expertise=["物理建模", "实验设计", "数据分析", "理论验证"]
        ),
        "biologist": ExpertTemplate(
            role="biologist",
            name="生物学家",
            domain="生物科学",
            default_expertise=["生物实验", "数据分析", "方案设计", "合规评估"]
        ),
        "data_scientist": ExpertTemplate(
            role="data_scientist",
            name="数据科学家",
            domain="数据分析",
            default_expertise=["数据挖掘", "统计分析", "机器学习", "可视化"]
        ),
        
        # ============ 管理与规划 ============
        "project_planner": ExpertTemplate(
            role="project_planner",
            name="项目规划师",
            domain="项目规划",
            default_expertise=["项目管理", "资源调度", "进度控制", "风险管理"]
        ),
        "cost_estimator": ExpertTemplate(
            role="cost_estimator",
            name="成本估算师",
            domain="成本评估",
            default_expertise=["成本分析", "预算编制", "投资回报", "成本控制"]
        ),
        "quality_manager": ExpertTemplate(
            role="quality_manager",
            name="质量管理师",
            domain="质量控制",
            default_expertise=["质量标准", "过程控制", "检验方法", "持续改进"]
        ),
        "risk_analyst": ExpertTemplate(
            role="risk_analyst",
            name="风险分析师",
            domain="风险管理",
            default_expertise=["风险识别", "影响评估", "缓解策略", "应急预案"]
        ),
        "product_manager": ExpertTemplate(
            role="product_manager",
            name="产品经理",
            domain="产品管理",
            default_expertise=["需求分析", "产品规划", "用户研究", "市场分析"]
        ),
        
        # ============ 其他领域 ============
        "technical_writer": ExpertTemplate(
            role="technical_writer",
            name="技术文档工程师",
            domain="技术文档",
            default_expertise=["文档编写", "知识管理", "标准规范", "用户手册"]
        ),
        "ux_designer": ExpertTemplate(
            role="ux_designer",
            name="用户体验设计师",
            domain="用户体验",
            default_expertise=["用户研究", "交互设计", "原型设计", "可用性测试"]
        ),
        "custom": ExpertTemplate(
            role="custom",
            name="领域专家",
            domain="自定义领域",
            default_expertise=["专业分析", "方案设计"]
        )
    }
    
    def __init__(self, llm_adapter=None):
        """
        初始化工厂
        
        Args:
            llm_adapter: LLM适配器，用于创建的专家
        """
        self.llm_adapter = llm_adapter
        self._created_experts: List[DynamicExpertAgent] = []
    
    def create_expert(self, expert_spec: Dict[str, Any]) -> DynamicExpertAgent:
        """
        根据规格创建单个专家智能体
        
        Args:
            expert_spec: 专家规格字典，包含：
                - role: 角色标识
                - name: 显示名称（可选，使用模板默认值）
                - domain: 专业领域（可选，使用模板默认值）
                - expertise: 具体专长列表（可选）
                - reason: 被选中原因
        
        Returns:
            DynamicExpertAgent 实例
        """
        role = expert_spec.get('role', 'custom')
        
        # 查找模板
        template = self.EXPERT_TEMPLATES.get(role, self.EXPERT_TEMPLATES['custom'])
        
        # 合并规格和模板
        name = expert_spec.get('name') or template.name
        domain = expert_spec.get('domain') or template.domain
        expertise = expert_spec.get('expertise') or template.default_expertise
        reason = expert_spec.get('reason', '')
        
        # 创建专家
        expert = DynamicExpertAgent(
            role=role,
            name=name,
            domain=domain,
            expertise=expertise,
            reason=reason,
            llm_adapter=self.llm_adapter
        )
        
        self._created_experts.append(expert)
        logger.info(f"创建专家: {name} ({domain})")
        
        return expert
    
    def create_experts_batch(
        self,
        expert_specs: List[Dict[str, Any]]
    ) -> List[DynamicExpertAgent]:
        """
        批量创建专家智能体
        
        Args:
            expert_specs: 专家规格列表
        
        Returns:
            创建的专家列表
        """
        experts = []
        for spec in expert_specs:
            try:
                expert = self.create_expert(spec)
                experts.append(expert)
            except Exception as e:
                logger.error(f"创建专家失败: {spec.get('role', 'unknown')}, 错误: {e}")
        
        logger.info(f"批量创建完成，共 {len(experts)} 位专家")
        return experts
    
    def get_created_experts(self) -> List[DynamicExpertAgent]:
        """获取已创建的所有专家"""
        return self._created_experts.copy()
    
    def clear_experts(self):
        """清空已创建的专家列表"""
        self._created_experts.clear()
    
    @classmethod
    def get_available_templates(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有可用的专家模板"""
        return {
            role: {
                "name": template.name,
                "domain": template.domain,
                "default_expertise": template.default_expertise
            }
            for role, template in cls.EXPERT_TEMPLATES.items()
        }
    
    @classmethod
    def get_template(cls, role: str) -> Optional[ExpertTemplate]:
        """获取指定角色的模板"""
        return cls.EXPERT_TEMPLATES.get(role)
    
    @classmethod
    def list_templates_by_category(cls) -> Dict[str, List[str]]:
        """按类别列出专家模板"""
        categories = {
            "软件领域": [
                "software_architect", "frontend_engineer", "backend_engineer",
                "database_expert", "devops_engineer", "ai_engineer",
                "security_expert", "test_engineer"
            ],
            "硬件领域": [
                "hardware_engineer", "embedded_engineer", "circuit_designer",
                "pcb_engineer", "mechanical_engineer"
            ],
            "科学领域": [
                "materials_scientist", "chemist", "physicist",
                "biologist", "data_scientist"
            ],
            "管理与规划": [
                "project_planner", "cost_estimator", "quality_manager",
                "risk_analyst", "product_manager"
            ],
            "其他": [
                "technical_writer", "ux_designer", "custom"
            ]
        }
        return categories
