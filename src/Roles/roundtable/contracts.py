"""
消息契约模块

包含消息契约系统:
- MessageContract: 消息契约基类
- 各种预定义契约类
- ContractRegistry: 契约注册表
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .communication import AgentMessage

logger = logging.getLogger(__name__)


class MessageContract:
    """
    消息契约基类 - 定义消息的结构和验证规则
    
    消息契约用于规范智能体间通信的格式和语义，确保：
    1. 消息结构符合预定义规范
    2. 必要字段完整
    3. 响应期望明确
    """
    
    contract_name: str = "base"
    contract_version: str = "1.0"
    required_fields: List[str] = []
    optional_fields: List[str] = []
    response_contract: Optional[str] = None  # 期望的响应契约类型
    timeout_seconds: int = 300  # 默认超时 5 分钟
    
    def __init__(self, **kwargs):
        """
        初始化消息契约
        
        Args:
            **kwargs: 可覆盖默认配置的参数
        """
        self.contract_name = kwargs.get('contract_name', self.__class__.contract_name)
        self.contract_version = kwargs.get('contract_version', self.__class__.contract_version)
        self.required_fields = kwargs.get('required_fields', self.__class__.required_fields.copy())
        self.optional_fields = kwargs.get('optional_fields', self.__class__.optional_fields.copy())
        self.response_contract = kwargs.get('response_contract', self.__class__.response_contract)
        self.timeout_seconds = kwargs.get('timeout_seconds', self.__class__.timeout_seconds)
    
    def validate(self, message: AgentMessage) -> tuple:
        """
        验证消息是否符合契约
        
        Args:
            message: 待验证的消息
            
        Returns:
            (is_valid, errors): 验证结果和错误列表
        """
        errors = []
        
        # 检查必要字段
        content = message.content or {}
        for field in self.required_fields:
            if field not in content or content[field] is None:
                errors.append(f"缺少必要字段: {field}")
            elif isinstance(content[field], str) and not content[field].strip():
                errors.append(f"必要字段 {field} 不能为空")
        
        # 检查契约版本兼容性
        msg_contract_version = content.get('contract_version', '1.0')
        if msg_contract_version != self.contract_version:
            # 版本不匹配时记录警告但不阻止
            logger.warning(f"契约版本不匹配: 消息版本 {msg_contract_version}, 契约版本 {self.contract_version}")
        
        is_valid = len(errors) == 0
        return (is_valid, errors)
    
    def get_response_expectation(self) -> Dict[str, Any]:
        """
        获取响应期望
        
        Returns:
            响应期望配置
        """
        return {
            "expected_contract": self.response_contract,
            "timeout_seconds": self.timeout_seconds,
            "requires_response": self.response_contract is not None
        }
    
    def create_content_template(self) -> Dict[str, Any]:
        """
        创建符合契约的内容模板
        
        Returns:
            内容模板字典
        """
        template = {
            "contract_name": self.contract_name,
            "contract_version": self.contract_version
        }
        for field in self.required_fields:
            template[field] = None
        for field in self.optional_fields:
            template[field] = None
        return template
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "contract_name": self.contract_name,
            "contract_version": self.contract_version,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "response_contract": self.response_contract,
            "timeout_seconds": self.timeout_seconds
        }


class QuestioningContract(MessageContract):
    """质疑消息契约 - 用于 Skeptic 对 DomainExpert 的质疑"""
    
    contract_name = "questioning"
    required_fields = ["target_expert", "questioning_content", "questioning_type"]
    optional_fields = ["evidence", "severity", "suggested_alternatives"]
    response_contract = "expert_response"
    timeout_seconds = 180  # 3 分钟内期望响应


class ExpertResponseContract(MessageContract):
    """专家回应契约 - 用于专家对质疑的回应"""
    
    contract_name = "expert_response"
    required_fields = ["response_content", "response_type", "addresses_points"]
    optional_fields = ["confidence_level", "supporting_evidence", "acknowledgments"]
    response_contract = None  # 回应通常不需要再回应
    timeout_seconds = 300


class DirectDebateContract(MessageContract):
    """直接辩论契约 - 用于专家间的观点交锋"""
    
    contract_name = "direct_debate"
    required_fields = ["debate_position", "supporting_evidence", "target_claim"]
    optional_fields = ["counter_arguments", "concessions", "proposed_resolution"]
    response_contract = "debate_response"
    timeout_seconds = 240  # 4 分钟


class DebateResponseContract(MessageContract):
    """辩论回应契约"""
    
    contract_name = "debate_response"
    required_fields = ["response_position", "rebuttal_points", "agreements"]
    optional_fields = ["new_evidence", "compromise_proposal"]
    response_contract = "direct_debate"  # 可以继续辩论
    timeout_seconds = 240


class ClarificationRequestContract(MessageContract):
    """澄清请求契约 - 用于请求对观点的澄清"""
    
    contract_name = "clarification_request"
    required_fields = ["clarification_topic", "specific_questions", "context"]
    optional_fields = ["urgency", "related_points"]
    response_contract = "clarification_response"
    timeout_seconds = 180


class ClarificationResponseContract(MessageContract):
    """澄清回应契约"""
    
    contract_name = "clarification_response"
    required_fields = ["clarification_content", "addressed_questions"]
    optional_fields = ["additional_context", "references"]
    response_contract = None
    timeout_seconds = 300


class CollaborationProposalContract(MessageContract):
    """协作提议契约 - 用于专家间提议协作"""
    
    contract_name = "collaboration_proposal"
    required_fields = ["proposal_content", "collaboration_goal", "expected_contribution"]
    optional_fields = ["timeline", "resources_needed", "success_criteria"]
    response_contract = "collaboration_response"
    timeout_seconds = 300


class CollaborationResponseContract(MessageContract):
    """协作回应契约"""
    
    contract_name = "collaboration_response"
    required_fields = ["acceptance_status", "response_content"]
    optional_fields = ["modifications", "commitment_level", "conditions"]
    response_contract = None
    timeout_seconds = 300


class OpenQuestionContract(MessageContract):
    """开放问题契约 - 用于广播开放式问题"""
    
    contract_name = "open_question"
    required_fields = ["question_content", "question_context", "seeking_perspectives"]
    optional_fields = ["background", "constraints", "priority"]
    response_contract = "open_question_response"
    timeout_seconds = 600  # 10 分钟，允许多人回应


class OpenQuestionResponseContract(MessageContract):
    """开放问题回应契约"""
    
    contract_name = "open_question_response"
    required_fields = ["response_content", "perspective_type"]
    optional_fields = ["confidence", "caveats", "follow_up_questions"]
    response_contract = None
    timeout_seconds = 300


class ContractRegistry:
    """
    消息契约注册表 - 支持动态扩展
    
    管理所有消息契约的注册、查询和扩展
    """
    
    def __init__(self):
        self._contracts: Dict[str, MessageContract] = {}
        self._contract_history: List[Dict[str, Any]] = []
        self._register_default_contracts()
    
    def _register_default_contracts(self):
        """注册默认契约"""
        default_contracts = [
            QuestioningContract(),
            ExpertResponseContract(),
            DirectDebateContract(),
            DebateResponseContract(),
            ClarificationRequestContract(),
            ClarificationResponseContract(),
            CollaborationProposalContract(),
            CollaborationResponseContract(),
            OpenQuestionContract(),
            OpenQuestionResponseContract()
        ]
        
        for contract in default_contracts:
            self._contracts[contract.contract_name] = contract
    
    def register(self, contract: MessageContract) -> bool:
        """
        注册新契约
        
        Args:
            contract: 待注册的契约
            
        Returns:
            是否注册成功
        """
        if contract.contract_name in self._contracts:
            logger.warning(f"契约 {contract.contract_name} 已存在，将被覆盖")
        
        self._contracts[contract.contract_name] = contract
        self._contract_history.append({
            "action": "register",
            "contract_name": contract.contract_name,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"已注册契约: {contract.contract_name}")
        return True
    
    def get(self, name: str) -> Optional[MessageContract]:
        """
        获取契约
        
        Args:
            name: 契约名称
            
        Returns:
            契约实例或 None
        """
        return self._contracts.get(name)
    
    def has(self, name: str) -> bool:
        """检查契约是否存在"""
        return name in self._contracts
    
    def extend(self, base_name: str, extensions: Dict[str, Any], new_name: str) -> Optional[MessageContract]:
        """
        基于现有契约扩展新契约
        
        Args:
            base_name: 基础契约名称
            extensions: 扩展配置
            new_name: 新契约名称
            
        Returns:
            扩展后的新契约或 None
        """
        base_contract = self.get(base_name)
        if not base_contract:
            logger.error(f"基础契约 {base_name} 不存在")
            return None
        
        # 创建扩展契约
        extended_config = base_contract.to_dict()
        extended_config.update(extensions)
        extended_config['contract_name'] = new_name
        
        extended_contract = MessageContract(**extended_config)
        self.register(extended_contract)
        
        return extended_contract
    
    def get_all_contracts(self) -> Dict[str, MessageContract]:
        """获取所有契约"""
        return self._contracts.copy()
    
    def get_contract_chain(self, start_contract: str) -> List[str]:
        """
        获取契约链（请求-响应链）
        
        Args:
            start_contract: 起始契约名称
            
        Returns:
            契约链列表
        """
        chain = []
        current = start_contract
        visited = set()
        
        while current and current not in visited:
            chain.append(current)
            visited.add(current)
            contract = self.get(current)
            if contract:
                current = contract.response_contract
            else:
                break
        
        return chain
    
    def validate_message_against_contract(self, message: AgentMessage, contract_name: str) -> tuple:
        """
        验证消息是否符合指定契约
        
        Args:
            message: 待验证消息
            contract_name: 契约名称
            
        Returns:
            (is_valid, errors)
        """
        contract = self.get(contract_name)
        if not contract:
            return (False, [f"契约 {contract_name} 不存在"])
        
        return contract.validate(message)
