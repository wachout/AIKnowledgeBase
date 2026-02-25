"""
实施层共识追踪器

追踪实施讨论过程中的各类共识：
- 技术方案共识（架构、技术选型）
- 实现路径共识（开发步骤、优先级）
- 风险共识（潜在问题、缓解策略）
- 资源共识（时间、人力）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import uuid


class ConsensusCategory(Enum):
    """共识类别"""
    TECHNICAL = "technical"        # 技术方案（架构、技术选型）
    PATH = "path"                  # 实现路径（开发步骤、优先级）
    RISK = "risk"                  # 风险（潜在问题、缓解策略）
    RESOURCE = "resource"          # 资源（时间、人力）
    QUALITY = "quality"            # 质量（测试策略、验收标准）


class OpinionStance(Enum):
    """意见立场"""
    STRONGLY_AGREE = "strongly_agree"      # 强烈同意
    AGREE = "agree"                        # 同意
    NEUTRAL = "neutral"                    # 中立
    DISAGREE = "disagree"                  # 反对
    STRONGLY_DISAGREE = "strongly_disagree"  # 强烈反对


@dataclass
class OpinionRecord:
    """意见记录"""
    opinion_id: str = field(default_factory=lambda: f"op_{uuid.uuid4().hex[:8]}")
    agent_id: str = ""
    agent_role: str = ""
    category: ConsensusCategory = ConsensusCategory.TECHNICAL
    topic: str = ""
    stance: OpinionStance = OpinionStance.NEUTRAL
    content: str = ""
    supporting_evidence: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    weight: float = 1.0  # 意见权重，根据角色专业度调整


@dataclass
class ConsensusResult:
    """共识结果"""
    topic: str = ""
    category: ConsensusCategory = ConsensusCategory.TECHNICAL
    consensus_level: float = 0.0  # 0-1，共识度
    dominant_stance: OpinionStance = OpinionStance.NEUTRAL
    supporters: List[str] = field(default_factory=list)  # 支持者agent_id列表
    dissenters: List[str] = field(default_factory=list)  # 反对者agent_id列表
    key_agreements: List[str] = field(default_factory=list)  # 关键共识点
    key_disagreements: List[str] = field(default_factory=list)  # 关键分歧点
    resolution: Optional[str] = None  # 解决方案
    finalized: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class ImplementationConsensus:
    """
    实施层共识追踪器
    
    负责追踪和计算实施讨论过程中的共识形成情况
    """
    
    # 角色权重配置（不同角色在不同领域的发言权重）
    ROLE_WEIGHTS = {
        "architect": {
            ConsensusCategory.TECHNICAL: 1.5,
            ConsensusCategory.PATH: 1.2,
            ConsensusCategory.RISK: 1.0,
            ConsensusCategory.RESOURCE: 0.8,
            ConsensusCategory.QUALITY: 1.0,
        },
        "developer": {
            ConsensusCategory.TECHNICAL: 1.2,
            ConsensusCategory.PATH: 1.5,
            ConsensusCategory.RISK: 1.0,
            ConsensusCategory.RESOURCE: 1.0,
            ConsensusCategory.QUALITY: 1.0,
        },
        "tester": {
            ConsensusCategory.TECHNICAL: 0.8,
            ConsensusCategory.PATH: 0.8,
            ConsensusCategory.RISK: 1.2,
            ConsensusCategory.RESOURCE: 0.8,
            ConsensusCategory.QUALITY: 1.5,
        },
        "documenter": {
            ConsensusCategory.TECHNICAL: 0.6,
            ConsensusCategory.PATH: 0.8,
            ConsensusCategory.RISK: 0.6,
            ConsensusCategory.RESOURCE: 0.8,
            ConsensusCategory.QUALITY: 1.0,
        },
        "coordinator": {
            ConsensusCategory.TECHNICAL: 0.8,
            ConsensusCategory.PATH: 1.0,
            ConsensusCategory.RISK: 1.0,
            ConsensusCategory.RESOURCE: 1.5,
            ConsensusCategory.QUALITY: 1.0,
        },
    }
    
    # 立场分值
    STANCE_SCORES = {
        OpinionStance.STRONGLY_AGREE: 1.0,
        OpinionStance.AGREE: 0.5,
        OpinionStance.NEUTRAL: 0.0,
        OpinionStance.DISAGREE: -0.5,
        OpinionStance.STRONGLY_DISAGREE: -1.0,
    }
    
    def __init__(self):
        # 按类别存储意见
        self._opinions: Dict[ConsensusCategory, Dict[str, List[OpinionRecord]]] = {
            category: {} for category in ConsensusCategory
        }
        
        # 共识结果缓存
        self._consensus_cache: Dict[str, ConsensusResult] = {}
        
        # 讨论历史
        self._discussion_history: List[OpinionRecord] = []
    
    def record_opinion(
        self,
        agent_id: str,
        agent_role: str,
        category: ConsensusCategory,
        topic: str,
        stance: OpinionStance,
        content: str,
        supporting_evidence: Optional[List[str]] = None,
        concerns: Optional[List[str]] = None
    ) -> OpinionRecord:
        """
        记录一条意见
        
        Args:
            agent_id: 智能体ID
            agent_role: 智能体角色
            category: 共识类别
            topic: 讨论话题
            stance: 意见立场
            content: 意见内容
            supporting_evidence: 支持证据
            concerns: 关注点/担忧
            
        Returns:
            OpinionRecord: 意见记录
        """
        # 计算角色权重
        role_key = agent_role.lower().replace("agent", "").strip()
        weight = self.ROLE_WEIGHTS.get(role_key, {}).get(category, 1.0)
        
        opinion = OpinionRecord(
            agent_id=agent_id,
            agent_role=agent_role,
            category=category,
            topic=topic,
            stance=stance,
            content=content,
            supporting_evidence=supporting_evidence or [],
            concerns=concerns or [],
            weight=weight
        )
        
        # 存储意见
        if topic not in self._opinions[category]:
            self._opinions[category][topic] = []
        self._opinions[category][topic].append(opinion)
        
        # 记录历史
        self._discussion_history.append(opinion)
        
        # 清除该话题的共识缓存
        cache_key = f"{category.value}:{topic}"
        if cache_key in self._consensus_cache:
            del self._consensus_cache[cache_key]
        
        return opinion
    
    def calculate_consensus_level(
        self,
        category: ConsensusCategory,
        topic: str
    ) -> ConsensusResult:
        """
        计算特定话题的共识度
        
        Args:
            category: 共识类别
            topic: 讨论话题
            
        Returns:
            ConsensusResult: 共识结果
        """
        cache_key = f"{category.value}:{topic}"
        
        # 检查缓存
        if cache_key in self._consensus_cache:
            return self._consensus_cache[cache_key]
        
        opinions = self._opinions[category].get(topic, [])
        
        if not opinions:
            return ConsensusResult(
                topic=topic,
                category=category,
                consensus_level=0.0
            )
        
        # 计算加权平均立场
        total_weighted_score = 0.0
        total_weight = 0.0
        supporters = []
        dissenters = []
        key_agreements = []
        key_disagreements = []
        
        for opinion in opinions:
            score = self.STANCE_SCORES[opinion.stance]
            weighted_score = score * opinion.weight
            total_weighted_score += weighted_score
            total_weight += opinion.weight
            
            # 分类支持者和反对者
            if opinion.stance in [OpinionStance.STRONGLY_AGREE, OpinionStance.AGREE]:
                supporters.append(opinion.agent_id)
                if opinion.supporting_evidence:
                    key_agreements.extend(opinion.supporting_evidence[:2])
            elif opinion.stance in [OpinionStance.STRONGLY_DISAGREE, OpinionStance.DISAGREE]:
                dissenters.append(opinion.agent_id)
                if opinion.concerns:
                    key_disagreements.extend(opinion.concerns[:2])
        
        # 计算共识度 (0-1)
        if total_weight > 0:
            avg_score = total_weighted_score / total_weight
            # 将 [-1, 1] 映射到 [0, 1]
            # 同时考虑立场一致性
            stance_scores = [self.STANCE_SCORES[op.stance] for op in opinions]
            variance = self._calculate_variance(stance_scores) if len(stance_scores) > 1 else 0
            # 共识度 = 平均倾向的绝对值 * (1 - 方差系数)
            consensus_level = abs(avg_score) * (1 - min(variance, 1))
        else:
            avg_score = 0
            consensus_level = 0
        
        # 确定主导立场
        if avg_score > 0.5:
            dominant_stance = OpinionStance.STRONGLY_AGREE
        elif avg_score > 0.1:
            dominant_stance = OpinionStance.AGREE
        elif avg_score < -0.5:
            dominant_stance = OpinionStance.STRONGLY_DISAGREE
        elif avg_score < -0.1:
            dominant_stance = OpinionStance.DISAGREE
        else:
            dominant_stance = OpinionStance.NEUTRAL
        
        result = ConsensusResult(
            topic=topic,
            category=category,
            consensus_level=consensus_level,
            dominant_stance=dominant_stance,
            supporters=list(set(supporters)),
            dissenters=list(set(dissenters)),
            key_agreements=list(set(key_agreements))[:5],
            key_disagreements=list(set(key_disagreements))[:5]
        )
        
        # 缓存结果
        self._consensus_cache[cache_key] = result
        
        return result
    
    def get_category_consensus(self, category: ConsensusCategory) -> Dict[str, ConsensusResult]:
        """获取某类别下所有话题的共识情况"""
        results = {}
        for topic in self._opinions[category].keys():
            results[topic] = self.calculate_consensus_level(category, topic)
        return results
    
    def get_overall_consensus(self) -> float:
        """
        计算整体共识度
        
        Returns:
            float: 0-1之间的整体共识度
        """
        all_results = []
        for category in ConsensusCategory:
            for topic in self._opinions[category].keys():
                result = self.calculate_consensus_level(category, topic)
                all_results.append(result.consensus_level)
        
        if not all_results:
            return 0.0
        
        return sum(all_results) / len(all_results)
    
    def get_unresolved_conflicts(self) -> List[ConsensusResult]:
        """获取未解决的分歧"""
        conflicts = []
        for category in ConsensusCategory:
            for topic in self._opinions[category].keys():
                result = self.calculate_consensus_level(category, topic)
                # 共识度低于0.6且有反对者，视为未解决冲突
                if result.consensus_level < 0.6 and len(result.dissenters) > 0:
                    conflicts.append(result)
        return conflicts
    
    def finalize_consensus(
        self,
        category: ConsensusCategory,
        topic: str,
        resolution: str
    ) -> ConsensusResult:
        """
        确定共识并记录解决方案
        
        Args:
            category: 共识类别
            topic: 话题
            resolution: 最终解决方案
            
        Returns:
            ConsensusResult: 最终共识结果
        """
        result = self.calculate_consensus_level(category, topic)
        result.resolution = resolution
        result.finalized = True
        result.timestamp = datetime.now()
        
        # 更新缓存
        cache_key = f"{category.value}:{topic}"
        self._consensus_cache[cache_key] = result
        
        return result
    
    def get_discussion_summary(self) -> Dict[str, Any]:
        """获取讨论摘要"""
        summary = {
            "total_opinions": len(self._discussion_history),
            "categories": {},
            "overall_consensus": self.get_overall_consensus(),
            "unresolved_conflicts": len(self.get_unresolved_conflicts())
        }
        
        for category in ConsensusCategory:
            topics = list(self._opinions[category].keys())
            if topics:
                category_results = self.get_category_consensus(category)
                avg_consensus = sum(r.consensus_level for r in category_results.values()) / len(category_results)
                summary["categories"][category.value] = {
                    "topic_count": len(topics),
                    "avg_consensus": avg_consensus,
                    "topics": topics
                }
        
        return summary
    
    def _calculate_variance(self, values: List[float]) -> float:
        """计算方差"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def clear(self):
        """清除所有记录"""
        self._opinions = {category: {} for category in ConsensusCategory}
        self._consensus_cache.clear()
        self._discussion_history.clear()
    
    def export_to_dict(self) -> Dict[str, Any]:
        """导出为字典格式"""
        return {
            "opinions": {
                cat.value: {
                    topic: [
                        {
                            "agent_id": op.agent_id,
                            "agent_role": op.agent_role,
                            "stance": op.stance.value,
                            "content": op.content,
                            "timestamp": op.timestamp.isoformat()
                        }
                        for op in ops
                    ]
                    for topic, ops in topics.items()
                }
                for cat, topics in self._opinions.items()
            },
            "summary": self.get_discussion_summary()
        }
