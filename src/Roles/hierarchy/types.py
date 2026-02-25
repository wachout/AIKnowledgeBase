"""
多层强化学习智能体系统 - 数据类型定义
定义系统中使用的所有数据结构、枚举和接口
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable, Set
import uuid


# ==================== 基础枚举 ====================

class LayerType(Enum):
    """层级类型"""
    DECISION = 1           # 决策层
    IMPLEMENTATION = 2     # 实施讨论层
    EXECUTION = 3          # 具体实施模拟层（新增）
    VALIDATION = 4         # 检验层（原第三层）


class EdgeType(Enum):
    """有向边类型"""
    TASK_FLOW = "task"           # 任务传递
    FEEDBACK = "feedback"        # 反馈信号
    COORDINATION = "coord"       # 协调通信
    REWARD = "reward"            # 奖励传播


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentAction(Enum):
    """智能体动作类型"""
    # 决策层动作
    PROPOSE_STRATEGY = "propose"
    EVALUATE_PROPOSAL = "evaluate"
    SYNTHESIZE = "synthesize"
    CHALLENGE = "challenge"
    
    # 实施层动作
    DESIGN = "design"
    IMPLEMENT = "implement"
    TEST = "test"
    COORDINATE = "coordinate"
    DOCUMENT = "document"
    
    # 检验层动作
    INSPECT = "inspect"
    VALIDATE = "validate"
    REPORT = "report"
    ESCALATE = "escalate"


class ImplementationRole(Enum):
    """实施层角色"""
    ARCHITECT = "架构师"
    DEVELOPER = "开发者"
    TESTER = "测试员"
    DOCUMENTER = "文档员"
    COORDINATOR = "协调员"


class ExecutionSimulationRole(Enum):
    """实施模拟层角色"""
    STEP_ANALYST = "步骤分析家"
    HARDWARE_ENGINEER = "硬件工程师"
    SOFTWARE_ENGINEER = "软件工程师"
    VISUAL_DESIGNER = "视觉设计师"
    ALGORITHM_SPECIALIST = "算法专家"
    MECHANICAL_ENGINEER = "机械工程师"
    ELECTRICAL_ENGINEER = "电气工程师"
    DATA_ARCHITECT = "数据架构师"
    TESTING_SPECIALIST = "测试专家"
    SPECIFICATION_SYNTHESIZER = "规格综合者"


class ValidationRole(Enum):
    """检验层角色"""
    QUALITY_INSPECTOR = "质量检验员"
    LOGIC_VALIDATOR = "逻辑验证员"
    PERFORMANCE_ANALYST = "性能分析员"
    SECURITY_AUDITOR = "安全审计员"
    COMPLIANCE_CHECKER = "合规检查员"


class MessageType(Enum):
    """消息类型"""
    TASK_DISPATCH = "task_dispatch"      # 任务下发
    RESULT_REPORT = "result_report"      # 结果上报
    FEEDBACK = "feedback"                 # 反馈信号
    ESCALATION = "escalation"            # 问题升级
    COORDINATION = "coordination"         # 协调请求
    REWARD_SIGNAL = "reward_signal"      # 奖励信号


class IssueSeverity(Enum):
    """问题严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== 基础数据类 ====================

@dataclass
class Objective:
    """目标定义"""
    objective_id: str = field(default_factory=lambda: f"obj_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    priority: int = 0
    measurable_criteria: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他目标ID


@dataclass
class Constraint:
    """约束条件"""
    constraint_id: str = field(default_factory=lambda: f"con_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    constraint_type: str = "soft"  # hard/soft
    validation_func: Optional[str] = None  # 验证函数名


@dataclass
class Task:
    """任务定义"""
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    parent_objective_id: Optional[str] = None
    assigned_roles: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0
    estimated_effort: float = 1.0  # 预估工作量
    deadline: Optional[datetime] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    sequence: int = 0
    action: str = ""
    description: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class ExecutionMetric:
    """执行指标"""
    metric_id: str = field(default_factory=lambda: f"metric_{uuid.uuid4().hex[:8]}")
    name: str = ""                         # 如 "材质密度"、"系统配置"
    category: str = "other"                # hardware/software/visual/algorithm/other
    value: str = ""                        # 指标值
    unit: str = ""                         # 单位
    specification: Dict[str, Any] = field(default_factory=dict)  # 详细规格
    confidence: float = 0.8                # 置信度
    source_expert: str = ""                # 来源专家
    source_step: str = ""                  # 来源步骤

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "category": self.category,
            "value": self.value,
            "unit": self.unit,
            "specification": self.specification,
            "confidence": self.confidence,
            "source_expert": self.source_expert,
            "source_step": self.source_step
        }


@dataclass
class Artifact:
    """产出物"""
    artifact_id: str = field(default_factory=lambda: f"art_{uuid.uuid4().hex[:8]}")
    name: str = ""
    artifact_type: str = ""  # code/document/config/test/etc
    content: Any = None
    file_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: datetime = field(default_factory=datetime.now)
    level: str = "INFO"
    source: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Issue:
    """问题定义"""
    issue_id: str = field(default_factory=lambda: f"issue_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    severity: IssueSeverity = IssueSeverity.MEDIUM
    category: str = ""
    source_layer: int = 0
    detected_at: datetime = field(default_factory=datetime.now)
    detected_by: str = ""
    affected_artifacts: List[str] = field(default_factory=list)
    resolution_status: str = "open"  # open/in_progress/resolved/wontfix


@dataclass
class Suggestion:
    """改进建议"""
    suggestion_id: str = field(default_factory=lambda: f"sug_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    target_layer: int = 0  # 建议针对的层级
    impact_estimate: float = 0.0  # 预估影响
    effort_estimate: float = 0.0  # 预估工作量
    priority: int = 0
    related_issues: List[str] = field(default_factory=list)


# ==================== 层输出数据类 ====================

@dataclass
class DecisionOutput:
    """决策层输出"""
    strategy_id: str = field(default_factory=lambda: f"strategy_{uuid.uuid4().hex[:8]}")
    query: str = ""
    objectives: List[Objective] = field(default_factory=list)
    tasks: List[Task] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    discussion_summary: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "query": self.query,
            "objectives": [{"id": o.objective_id, "name": o.name, "description": o.description} for o in self.objectives],
            "tasks": [{"id": t.task_id, "name": t.name, "description": t.description, "status": t.status.value} for t in self.tasks],
            "constraints": [{"id": c.constraint_id, "name": c.name, "type": c.constraint_type} for c in self.constraints],
            "success_criteria": self.success_criteria,
            "discussion_summary": self.discussion_summary,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class ImplementationOutput:
    """实施层输出"""
    implementation_id: str = field(default_factory=lambda: f"impl_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    execution_steps: List[ExecutionStep] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    execution_log: List[LogEntry] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "implementation_id": self.implementation_id,
            "task_id": self.task_id,
            "execution_steps": [{"id": s.step_id, "action": s.action, "status": s.status.value} for s in self.execution_steps],
            "artifacts": [{"id": a.artifact_id, "name": a.name, "type": a.artifact_type} for a in self.artifacts],
            "status": self.status.value,
            "metrics": self.metrics
        }


@dataclass
class ExecutionSimulationOutput:
    """实施模拟层输出"""
    simulation_id: str = field(default_factory=lambda: f"exec_sim_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    step_simulations: List[Dict[str, Any]] = field(default_factory=list)  # 每个步骤的模拟结果
    metrics: List[ExecutionMetric] = field(default_factory=list)          # 所有指标集合
    visual_artifacts: List[Artifact] = field(default_factory=list)       # 视觉产出（图片等）
    specification_document: str = ""    # 完整的任务实施规格书
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expert_count: int = 0
    success: bool = False
    # 具像化产出：软件任务生成的代码文件；硬件任务生成的验收指标文档
    code_artifacts: List[Artifact] = field(default_factory=list)  # 软件代码文件（路径在 file_path）
    concretization_type: str = ""  # "software" | "hardware" | "mixed" | ""
    acceptance_criteria_path: str = ""  # 硬件/混合任务的验收指标文件路径（可作为验收依据）
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "task_id": self.task_id,
            "step_simulations": self.step_simulations,
            "metrics": [m.to_dict() for m in self.metrics],
            "visual_artifacts": [{"id": a.artifact_id, "name": a.name, "type": a.artifact_type} for a in self.visual_artifacts],
            "specification_document": self.specification_document[:500] if self.specification_document else "",
            "status": self.status.value,
            "expert_count": self.expert_count,
            "success": self.success,
            "code_artifacts": [{"id": a.artifact_id, "name": a.name, "type": a.artifact_type, "file_path": a.file_path} for a in self.code_artifacts],
            "concretization_type": self.concretization_type,
            "acceptance_criteria_path": self.acceptance_criteria_path,
        }


@dataclass
class ValidationOutput:
    """检验层输出"""
    validation_id: str = field(default_factory=lambda: f"val_{uuid.uuid4().hex[:8]}")
    target_strategy_id: str = ""
    target_implementation_ids: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)  # 各维度评分
    issues: List[Issue] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    reward_signal: float = 0.0  # 强化学习奖励信号 [-1, 1]
    escalation_required: bool = False
    overall_assessment: str = ""
    validated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "target_strategy_id": self.target_strategy_id,
            "scores": self.scores,
            "issues": [{"id": i.issue_id, "title": i.title, "severity": i.severity.value} for i in self.issues],
            "suggestions": [{"id": s.suggestion_id, "title": s.title, "priority": s.priority} for s in self.suggestions],
            "reward_signal": self.reward_signal,
            "escalation_required": self.escalation_required,
            "overall_assessment": self.overall_assessment
        }


# ==================== 状态相关数据类 ====================

@dataclass
class AgentMemory:
    """智能体记忆"""
    short_term: List[Dict[str, Any]] = field(default_factory=list)  # 短期记忆
    long_term: List[Dict[str, Any]] = field(default_factory=list)   # 长期记忆
    working: Dict[str, Any] = field(default_factory=dict)           # 工作记忆
    max_short_term: int = 100
    
    def add_short_term(self, item: Dict[str, Any]):
        self.short_term.append(item)
        if len(self.short_term) > self.max_short_term:
            # 将溢出的移动到长期记忆
            self.long_term.extend(self.short_term[:-self.max_short_term])
            self.short_term = self.short_term[-self.max_short_term:]


@dataclass
class AgentState:
    """智能体状态"""
    agent_id: str
    agent_type: str = ""
    layer: int = 0
    current_task: Optional[Task] = None
    memory: AgentMemory = field(default_factory=AgentMemory)
    communication_buffer: List[Dict[str, Any]] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    is_active: bool = True
    last_action: Optional[AgentAction] = None
    last_action_time: Optional[datetime] = None


@dataclass
class LayerState:
    """层状态"""
    layer_type: LayerType
    agents: Dict[str, AgentState] = field(default_factory=dict)
    pending_tasks: List[Task] = field(default_factory=list)
    completed_tasks: List[Task] = field(default_factory=list)
    current_phase: str = "idle"
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class GlobalState:
    """全局状态"""
    session_id: str = field(default_factory=lambda: f"session_{uuid.uuid4().hex[:8]}")
    iteration: int = 0
    current_query: str = ""
    layer_states: Dict[int, LayerState] = field(default_factory=dict)
    reward_history: List[float] = field(default_factory=list)
    total_reward: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)
    status: str = "active"  # active/completed/failed


@dataclass
class StateTransition:
    """状态转移记录"""
    transition_id: str = field(default_factory=lambda: f"trans_{uuid.uuid4().hex[:8]}")
    from_state: Dict[str, Any] = field(default_factory=dict)
    to_state: Dict[str, Any] = field(default_factory=dict)
    action: Optional[AgentAction] = None
    reward: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class HierarchicalState:
    """层次化状态（完整）"""
    global_state: GlobalState = field(default_factory=GlobalState)
    task_context: Dict[str, Any] = field(default_factory=dict)
    history: List[StateTransition] = field(default_factory=list)


# ==================== 策略相关数据类 ====================

@dataclass
class Policy:
    """策略参数"""
    policy_id: str = field(default_factory=lambda: f"policy_{uuid.uuid4().hex[:8]}")
    agent_type: str = ""
    layer: int = 0
    parameters: Dict[str, float] = field(default_factory=dict)
    action_preferences: Dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.001
    exploration_rate: float = 0.1
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Experience:
    """经验（用于强化学习）"""
    experience_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:8]}")
    layer: int = 0
    agent_id: str = ""
    state: Dict[str, Any] = field(default_factory=dict)
    action: Optional[AgentAction] = None
    reward: float = 0.0
    next_state: Dict[str, Any] = field(default_factory=dict)
    done: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== 通信相关数据类 ====================

@dataclass
class LayerMessage:
    """层间消息"""
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    source_layer: int = 0
    target_layer: int = 0
    source_agent: str = ""
    target_agent: str = ""
    message_type: MessageType = MessageType.COORDINATION
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    requires_response: bool = False
    response_deadline: Optional[datetime] = None


# ==================== 图结构相关数据类 ====================

@dataclass
class AgentNode:
    """智能体节点（强化学习图中的节点）"""
    node_id: str
    agent_type: str
    layer: int
    state: AgentState = field(default_factory=lambda: AgentState(agent_id=""))
    policy: Policy = field(default_factory=Policy)
    value_estimate: float = 0.0
    incoming_edges: List[str] = field(default_factory=list)
    outgoing_edges: List[str] = field(default_factory=list)


@dataclass
class Edge:
    """有向边"""
    edge_id: str = field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    source: str = ""
    target: str = ""
    edge_type: EdgeType = EdgeType.TASK_FLOW
    weight: float = 1.0
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== 最终输出数据类 ====================

@dataclass
class HierarchicalOutput:
    """层次化系统最终输出"""
    session_id: str = ""
    query: str = ""
    decision_output: Optional[DecisionOutput] = None
    implementation_outputs: List[ImplementationOutput] = field(default_factory=list)
    execution_simulation_outputs: List[ExecutionSimulationOutput] = field(default_factory=list)
    validation_output: Optional[ValidationOutput] = None
    total_iterations: int = 0
    final_reward: float = 0.0
    execution_time_seconds: float = 0.0
    success: bool = False
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "query": self.query,
            "decision_output": self.decision_output.to_dict() if self.decision_output else None,
            "implementation_outputs": [o.to_dict() for o in self.implementation_outputs],
            "execution_simulation_outputs": [o.to_dict() for o in self.execution_simulation_outputs],
            "validation_output": self.validation_output.to_dict() if self.validation_output else None,
            "total_iterations": self.total_iterations,
            "final_reward": self.final_reward,
            "execution_time_seconds": self.execution_time_seconds,
            "success": self.success,
            "summary": self.summary
        }
