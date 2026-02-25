"""
增强版共识追踪器主类模块

核心改进：
1. 多维度共识计算（强度、稳定度、收敛度、广度）
2. 动态时间衰减模型（不同类型不同衰减率）
3. 层次化共识分析与依赖关系
4. 共识动量与趋势预测
5. 置信度评分与可靠性评估
"""

import json
import math
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from .types import ConsensusType, ConsensusPriority, ConflictSeverity
from .decay_model import AdaptiveDecayModel
from .consensus_point import ConsensusPoint
from .dependency_graph import ConsensusDependencyGraph, DependencyType
from .weight_calculator import DiscussionPhase, DynamicWeightCalculator
from .aggregator import ConsensusAggregator
from .divergence_point import DivergencePoint, ConflictResolutionStrategy, ConflictResolution
from .conflict_detection import ConflictTriggerCondition, ConflictAlert, ConflictTriggerManager
from .resolution_orchestrator import ResolutionOrchestrator, ResolutionResult


class EnhancedConsensusTracker:
    """增强版共识追踪器"""

    CONSENSUS_TYPE_WEIGHTS = {
        ConsensusType.CORE: 1.0, ConsensusType.STRATEGIC: 0.85,
        ConsensusType.TECHNICAL: 0.75, ConsensusType.TACTICAL: 0.6,
        ConsensusType.PROCEDURAL: 0.5, ConsensusType.AUXILIARY: 0.35
    }
    PRIORITY_WEIGHTS = {
        ConsensusPriority.CRITICAL: 1.0, ConsensusPriority.HIGH: 0.8,
        ConsensusPriority.MEDIUM: 0.6, ConsensusPriority.LOW: 0.4
    }
    TIME_DECAY_ROUNDS = 10
    DECAY_FACTOR = 0.95
    CONSENSUS_TYPE_DECAY_RATES = {
        ConsensusType.CORE: 0.98, ConsensusType.STRATEGIC: 0.95,
        ConsensusType.TECHNICAL: 0.92, ConsensusType.TACTICAL: 0.90,
        ConsensusType.PROCEDURAL: 0.88, ConsensusType.AUXILIARY: 0.85
    }
    HIERARCHY_WEIGHTS = {
        "core": 0.30, "strategic": 0.25, "tactical": 0.20,
        "technical": 0.12, "procedural": 0.08, "auxiliary": 0.05
    }

    def __init__(self, total_participants: int = 5):
        self.consensus_points: List[ConsensusPoint] = []
        self.divergence_points: List[DivergencePoint] = []
        self.conflict_resolutions: List[ConflictResolution] = []
        self.discussion_summary = {
            "total_rounds": 0, "total_participants": total_participants,
            "overall_consensus_level": 0.0, "key_insights": [],
            "unresolved_issues": [], "debate_required": []
        }
        self.current_round = 0
        self.consensus_history: List[Dict[str, Any]] = []
        self._stability_tracker: Dict[str, List[float]] = {}
        self.adaptive_decay_model = AdaptiveDecayModel()
        self.dependency_graph = ConsensusDependencyGraph()
        self.dynamic_weight_calculator = DynamicWeightCalculator()
        self.consensus_aggregator = ConsensusAggregator()
        self.total_rounds_estimate = 10
        self.conflict_trigger_manager = ConflictTriggerManager(self)
        self.resolution_orchestrator = ResolutionOrchestrator()

    def set_current_round(self, round_number: int) -> None:
        self.current_round = round_number
        self.discussion_summary["total_rounds"] = round_number
        self._track_stability()

    def _track_stability(self) -> None:
        for cp in self.consensus_points:
            if cp.content not in self._stability_tracker:
                self._stability_tracker[cp.content] = []
            self._stability_tracker[cp.content].append(cp.strength)

    def calculate_stability_score(self, consensus: ConsensusPoint) -> float:
        history = self._stability_tracker.get(consensus.content, [])
        if len(history) < 2:
            return consensus.strength
        recent = history[-3:]
        if len(recent) < 2:
            return consensus.strength
        variance = sum((x - sum(recent)/len(recent))**2 for x in recent) / len(recent)
        stability = max(0, 1 - variance * 10)
        return consensus.strength * 0.7 + stability * consensus.strength * 0.3

    def calculate_convergence_score(self) -> float:
        if not self.consensus_points:
            return 0.0
        if len(self.consensus_points) == 1:
            return 1.0
        strengths = [cp.strength for cp in self.consensus_points]
        mean_strength = sum(strengths) / len(strengths)
        if mean_strength == 0:
            return 0.0
        variance = sum((s - mean_strength)**2 for s in strengths) / len(strengths)
        std_dev = variance ** 0.5
        cv = std_dev / mean_strength
        return max(0, 1 - cv)

    def calculate_breadth_score(self) -> float:
        if not self.consensus_points or not self.divergence_points:
            return 0.0
        total_participants = self.discussion_summary.get("total_participants", 5)
        all_supporters = set()
        all_proponents = set()
        for cp in self.consensus_points:
            all_supporters.update(cp.supporters)
        for dp in self.divergence_points:
            all_proponents.update(dp.proponents.keys())
        unique_participants = all_supporters | all_proponents
        coverage = len(unique_participants) / total_participants if total_participants > 0 else 0
        return min(1.0, coverage)

    def calculate_momentum(self) -> float:
        if len(self.consensus_history) < 2:
            return 0.0
        recent_5 = [h.get("overall_level", 0) for h in self.consensus_history[-5:]]
        if len(recent_5) < 2:
            return 0.0
        first_half_avg = sum(recent_5[:len(recent_5)//2]) / max(1, len(recent_5)//2)
        second_half_avg = sum(recent_5[len(recent_5)//2:]) / max(1, len(recent_5) - len(recent_5)//2)
        if first_half_avg == 0:
            return 0.0
        momentum = (second_half_avg - first_half_avg) / first_half_avg
        return max(-1.0, min(1.0, momentum))

    def _calculate_dynamic_decay(self, consensus: ConsensusPoint) -> float:
        decay_rate = self.CONSENSUS_TYPE_DECAY_RATES.get(consensus.consensus_type, self.DECAY_FACTOR)
        rounds_since_creation = max(0, self.current_round - consensus.round_created)
        if rounds_since_creation == 0:
            return 1.0
        base_decay = math.pow(decay_rate, min(rounds_since_creation, 20))
        if len(consensus.evidence) > 0:
            evidence_bonus = min(0.2, len(consensus.evidence) * 0.05)
            base_decay = min(1.0, base_decay + evidence_bonus)
        if consensus.verification_count > 0:
            verification_bonus = min(0.15, consensus.verification_count * 0.03)
            base_decay = min(1.0, base_decay + verification_bonus)
        return base_decay

    def _calculate_hierarchical_consensus(self) -> Dict[str, Dict[str, Any]]:
        hierarchy_scores = {}
        for consensus_type in ConsensusType:
            type_points = [cp for cp in self.consensus_points if cp.consensus_type == consensus_type]
            if not type_points:
                continue
            raw_scores = [cp.strength for cp in type_points]
            decayed_scores = [self._calculate_dynamic_decay(cp) * cp.strength for cp in type_points]
            stability_scores = [self.calculate_stability_score(cp) for cp in type_points]
            hierarchy_scores[consensus_type.value] = {
                "raw_avg": sum(raw_scores) / len(raw_scores),
                "decayed_avg": sum(decayed_scores) / len(decayed_scores) if decayed_scores else 0,
                "stability_avg": sum(stability_scores) / len(stability_scores) if stability_scores else 0,
                "point_count": len(type_points),
                "strong_points": len([s for s in raw_scores if s > 0.7]),
                "weak_points": len([s for s in raw_scores if s < 0.4]),
                "total_supporters": len(set(s for cp in type_points for s in cp.supporters))
            }
        return hierarchy_scores

    def _calculate_overall_with_hierarchy(self, hierarchy_scores: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        if not hierarchy_scores:
            return {"overall": 0.0, "core_weighted": 0.0, "secondary_weighted": 0.0, "hierarchy_contribution": 0.0, "coverage_bonus": 0.0}
        core_score = hierarchy_scores.get("core", {}).get("decayed_avg", 0)
        strategic_score = hierarchy_scores.get("strategic", {}).get("decayed_avg", 0)
        tactical_score = hierarchy_scores.get("tactical", {}).get("decayed_avg", 0)
        technical_score = hierarchy_scores.get("technical", {}).get("decayed_avg", 0)
        core_weighted = core_score * self.HIERARCHY_WEIGHTS.get("core", 0.3)
        strategic_weighted = strategic_score * self.HIERARCHY_WEIGHTS.get("strategic", 0.25)
        tactical_weighted = tactical_score * self.HIERARCHY_WEIGHTS.get("tactical", 0.2)
        technical_weighted = technical_score * self.HIERARCHY_WEIGHTS.get("technical", 0.12)
        secondary_types = [k for k in hierarchy_scores.keys() if k not in ["core", "strategic", "tactical", "technical"]]
        secondary_weighted = sum(hierarchy_scores.get(t, {}).get("decayed_avg", 0) * self.HIERARCHY_WEIGHTS.get(t, 0.05) for t in secondary_types)
        hierarchy_contribution = core_weighted + strategic_weighted + tactical_weighted + technical_weighted + secondary_weighted
        convergence = self.calculate_convergence_score()
        breadth = self.calculate_breadth_score()
        overall = min(1.0, hierarchy_contribution + convergence * 0.1 + breadth * 0.1)
        return {
            "overall": overall, "core_weighted": core_weighted, "strategic_weighted": strategic_weighted,
            "tactical_weighted": tactical_weighted, "technical_weighted": technical_weighted,
            "secondary_weighted": secondary_weighted, "hierarchy_contribution": hierarchy_contribution,
            "convergence_bonus": convergence * 0.1, "coverage_bonus": breadth * 0.1,
            "convergence_score": convergence, "breadth_score": breadth
        }

    def _calculate_divergence_penalty(self) -> Dict[str, Any]:
        if not self.divergence_points:
            return {"total_penalty": 0.0, "weighted_intensity": 0.0, "severity_breakdown": {}, "type_breakdown": {}}
        severity_weights = {ConflictSeverity.CRITICAL: 1.0, ConflictSeverity.HIGH: 0.75, ConflictSeverity.MEDIUM: 0.5, ConflictSeverity.LOW: 0.25}
        severity_breakdown, type_breakdown = {}, {}
        total_weighted_intensity, total_weight = 0.0, 0.0
        for dp in self.divergence_points:
            severity_w = severity_weights.get(dp.severity, 0.5)
            type_w = self.CONSENSUS_TYPE_WEIGHTS.get(dp.consensus_type, 0.5)
            combined_weight = severity_w * type_w
            contribution = dp.intensity * combined_weight
            total_weighted_intensity += contribution
            total_weight += combined_weight
            severity_breakdown[dp.severity.value] = severity_breakdown.get(dp.severity.value, 0) + contribution
            type_breakdown[dp.consensus_type.value] = type_breakdown.get(dp.consensus_type.value, 0) + contribution
        weighted_intensity = total_weighted_intensity / total_weight if total_weight > 0 else 0
        return {"total_penalty": weighted_intensity * 0.35, "weighted_intensity": weighted_intensity, "severity_breakdown": severity_breakdown, "type_breakdown": type_breakdown}

    def _predict_consensus_trajectory(self, current_overall: float, momentum: float) -> Dict[str, Any]:
        if momentum > 0.1:
            trajectory = "上升趋势"
            predicted_rounds = [min(1.0, current_overall + (i + 1) * 0.05 * momentum) for i in range(3)]
        elif momentum < -0.1:
            trajectory = "下降趋势"
            predicted_rounds = [max(0.0, current_overall + (i + 1) * 0.05 * momentum) for i in range(3)]
        else:
            trajectory = "趋于稳定"
            predicted_rounds = [current_overall] * 3
        confidence = min(0.95, 0.5 + 0.3 * abs(momentum) + 0.2 * (1 - abs(momentum)))
        return {"trajectory": trajectory, "predicted_levels": predicted_rounds, "confidence": confidence, "momentum": momentum}

    def calculate_enhanced_consensus(self) -> Dict[str, Any]:
        """增强版共识计算"""
        if not self.consensus_points and not self.divergence_points:
            return {"overall_level": 0.0, "consensus_count": 0, "divergence_count": 0, "analysis": "暂无共识和分歧数据"}
        current_consensus_level = self._get_last_consensus_level()
        phase = DiscussionPhase.detect_from_progress(self.current_round, self.total_rounds_estimate, current_consensus_level)
        self.dynamic_weight_calculator.set_phase(phase)
        type_weights = self.dynamic_weight_calculator.get_phase_adjusted_type_weights(phase)
        adjusted_strengths = {}
        for i, cp in enumerate(self.consensus_points):
            consensus_id = cp.consensus_id or f"consensus_{i}"
            decay_factor = self.adaptive_decay_model.calculate_adaptive_decay(cp, self.current_round, self.adaptive_decay_model.get_decay_history(consensus_id))
            consensus_strengths_map = {f"consensus_{j}": self.consensus_points[j].strength for j in range(len(self.consensus_points))}
            cascading_factor = self.dependency_graph.calculate_cascading_strength(consensus_id, consensus_strengths_map)
            expert_factor = self.dynamic_weight_calculator.calculate_expert_weighted_support(cp, cp.supporters)
            context = {"topic_keywords": self.discussion_summary.get("topic_keywords", [])}
            context_modifier = self.dynamic_weight_calculator.calculate_context_weight_modifier(cp, context)
            type_weight = type_weights.get(cp.consensus_type, 0.5)
            adjusted_strength = cp.strength * decay_factor * cascading_factor * expert_factor * context_modifier * type_weight
            adjusted_strengths[consensus_id] = max(0.0, min(1.0, adjusted_strength))
        self.consensus_aggregator.compute_all_correlations(self.consensus_points)
        aggregation_strategy = self.consensus_aggregator.select_strategy_for_phase(phase)
        aggregated_consensus = self.consensus_aggregator.aggregate_with_correlation(adjusted_strengths, aggregation_strategy)
        divergence_penalty = self._calculate_divergence_penalty()
        final_overall = max(0.0, min(1.0, aggregated_consensus - divergence_penalty["total_penalty"]))
        momentum = self.calculate_momentum()
        trajectory = self._predict_consensus_trajectory(final_overall, momentum)
        self.consensus_history.append({"overall_level": final_overall, "timestamp": datetime.now().isoformat(), "round": self.current_round, "phase": phase.value, "aggregation_strategy": aggregation_strategy.value})
        stability_score = sum(self.calculate_stability_score(cp) for cp in self.consensus_points) / len(self.consensus_points) if self.consensus_points else 0
        hierarchy_scores = self._calculate_hierarchical_consensus()
        hierarchy_result = self._calculate_overall_with_hierarchy(hierarchy_scores)
        hierarchy_summary = self.dependency_graph.get_hierarchy_summary()
        return {
            "overall_level": final_overall, "consensus_count": len(self.consensus_points), "divergence_count": len(self.divergence_points),
            "discussion_phase": phase.value, "aggregation_strategy": aggregation_strategy.value,
            "hierarchy_analysis": {"core_level": hierarchy_result.get("core_weighted", 0), "strategic_level": hierarchy_result.get("strategic_weighted", 0), "tactical_level": hierarchy_result.get("tactical_weighted", 0), "technical_level": hierarchy_result.get("technical_weighted", 0), "secondary_level": hierarchy_result.get("secondary_weighted", 0)},
            "divergence_penalty": divergence_penalty["total_penalty"], "weighted_divergence_intensity": divergence_penalty["weighted_intensity"],
            "multi_dimension_scores": {"strength_score": hierarchy_result.get("overall", 0), "convergence_score": hierarchy_result.get("convergence_score", 0), "breadth_score": hierarchy_result.get("breadth_score", 0), "stability_score": stability_score, "aggregated_score": aggregated_consensus},
            "momentum": momentum, "trajectory_prediction": trajectory, "detailed_hierarchy": hierarchy_scores, "hierarchy_dependency_summary": hierarchy_summary,
            "decay_statistics": {"total_consensus_with_decay": len([s for s in adjusted_strengths.values() if s < 0.9]), "avg_adjusted_strength": sum(adjusted_strengths.values()) / len(adjusted_strengths) if adjusted_strengths else 0},
            "correlation_statistics": {"total_correlations": len(self.consensus_aggregator.correlations), "significant_correlations": len([c for c in self.consensus_aggregator.correlations if c.is_significant()])},
            "debate_required": self._identify_debate_requirements(),
            "analysis": self._analyze_enhanced_consensus(final_overall, hierarchy_result, divergence_penalty, momentum),
            "consensus_trend": self._calculate_consensus_trend(), "confidence_level": self._calculate_confidence_level(hierarchy_scores)
        }

    def _get_last_consensus_level(self) -> float:
        return self.consensus_history[-1].get("overall_level", 0.0) if self.consensus_history else 0.0

    def set_total_rounds_estimate(self, total_rounds: int) -> None:
        self.total_rounds_estimate = max(1, total_rounds)

    def add_consensus_dependency(self, parent_id: str, child_id: str, dep_type: str, strength: float = 1.0, evidence: str = "") -> bool:
        try:
            dep_type_enum = DependencyType(dep_type)
        except ValueError:
            dep_type_enum = DependencyType.SUPPORTS
        return self.dependency_graph.add_dependency(parent_id, child_id, dep_type_enum, strength, evidence)

    def update_expert_authority(self, expert_id: str, **scores) -> None:
        expert_score = self.dynamic_weight_calculator.get_expert_score(expert_id)
        for key in ["domain_expertise", "participation_quality", "consensus_track_record", "influence_score"]:
            if key in scores:
                setattr(expert_score, key, scores[key])
        self.dynamic_weight_calculator.set_expert_score(expert_id, expert_score)

    def _calculate_confidence_level(self, hierarchy_scores: Dict[str, Dict[str, Any]]) -> float:
        if not self.consensus_points:
            return 0.0
        participation_rates = [len(cp.supporters) / max(1, self.discussion_summary.get("total_participants", 5)) for cp in self.consensus_points]
        avg_participation = sum(participation_rates) / len(participation_rates)
        evidence_coverage = sum(len(cp.evidence) for cp in self.consensus_points) / max(1, len(self.consensus_points))
        stability_check = sum(1 for cp in self.consensus_points if len(self._stability_tracker.get(cp.content, [])) >= 3) / max(1, len(self.consensus_points))
        return avg_participation * 0.4 + min(1.0, evidence_coverage / 3) * 0.3 + stability_check * 0.3

    def _analyze_enhanced_consensus(self, overall: float, hierarchy_result: Dict[str, Any], divergence_penalty: Dict[str, Any], momentum: float) -> str:
        parts = []
        if overall >= 0.8: level_desc = "高度共识"
        elif overall >= 0.6: level_desc = "较强共识"
        elif overall >= 0.4: level_desc = "中等共识"
        elif overall >= 0.2: level_desc = "初步共识"
        else: level_desc = "分歧较大"
        parts.append(f"整体共识水平: {level_desc} ({overall:.2f})")
        core = hierarchy_result.get("core_weighted", 0)
        if core > 0.6: parts.append("核心问题已达成高度共识")
        elif core > 0.3: parts.append("核心问题已形成基本共识")
        else: parts.append("核心问题仍需深入讨论")
        strategic = hierarchy_result.get("strategic_weighted", 0)
        if strategic > 0.5: parts.append("战略方向明确")
        elif strategic > 0.2: parts.append("战略方向初步形成")
        if divergence_penalty["total_penalty"] > 0.2: parts.append(f"存在显著分歧(惩罚:{divergence_penalty['total_penalty']:.2f})")
        elif divergence_penalty["total_penalty"] > 0.1: parts.append(f"存在一定分歧(惩罚:{divergence_penalty['total_penalty']:.2f})")
        if momentum > 0.1: parts.append("共识正在增强")
        elif momentum < -0.1: parts.append("共识正在弱化")
        return "。".join(parts)

    def add_consensus_point(self, content: str, supporters: List[str], evidence: List[str] = None, consensus_type: ConsensusType = ConsensusType.AUXILIARY, priority: ConsensusPriority = ConsensusPriority.MEDIUM, topic_keywords: List[str] = None) -> str:
        consensus_point = ConsensusPoint(content=content, consensus_type=consensus_type, priority=priority, supporters=supporters.copy() if supporters else [], evidence=evidence.copy() if evidence else [], topic_keywords=topic_keywords.copy() if topic_keywords else [], round_created=self.current_round)
        consensus_point.importance_score = self._calculate_importance(consensus_type, priority, len(supporters))
        self.consensus_points.append(consensus_point)
        consensus_id = f"consensus_{len(self.consensus_points) - 1}"
        self._link_related_divergences(consensus_id, content)
        return consensus_id

    def add_consensus(self, content: str, consensus_type: ConsensusType, supporters: List[str], strength: float = 0.5, evidence: List[str] = None, priority: ConsensusPriority = ConsensusPriority.MEDIUM, topic_keywords: List[str] = None) -> str:
        return self.add_consensus_point(content=content, supporters=supporters, evidence=evidence, consensus_type=consensus_type, priority=priority, topic_keywords=topic_keywords)

    def _calculate_importance(self, consensus_type: ConsensusType, priority: ConsensusPriority, num_supporters: int) -> float:
        type_score = self.CONSENSUS_TYPE_WEIGHTS.get(consensus_type, 0.5)
        priority_score = self.PRIORITY_WEIGHTS.get(priority, 0.5)
        supporter_score = min(1.0, num_supporters / 5.0)
        return type_score * 0.4 + priority_score * 0.35 + supporter_score * 0.25

    def _link_related_divergences(self, consensus_id: str, content: str) -> None:
        content_lower = content.lower()
        keywords = set(content_lower.split())
        for divergence in self.divergence_points:
            div_keywords = set(divergence.content.lower().split())
            overlap = keywords & div_keywords
            if overlap and len(overlap) >= 2 and consensus_id not in divergence.related_consensus:
                divergence.related_consensus.append(consensus_id)

    def add_divergence_point(self, content: str, proponents: Dict[str, str], consensus_type: ConsensusType = ConsensusType.AUXILIARY) -> str:
        divergence_point = DivergencePoint(content=content, consensus_type=consensus_type, proponents=proponents.copy() if proponents else {}, round_created=self.current_round)
        self.divergence_points.append(divergence_point)
        divergence_id = f"divergence_{len(self.divergence_points) - 1}"
        self._check_debate_requirement(divergence_id, divergence_point)
        return divergence_id

    def _check_debate_requirement(self, divergence_id: str, divergence: DivergencePoint) -> None:
        if len(divergence.opposing_positions) >= 2:
            divergence.mark_for_debate("system", f"检测到{len(divergence.opposing_positions)}组对立立场，需要深度辩论")
        elif divergence.intensity >= 0.8 and len(divergence.proponents) >= 3:
            divergence.mark_for_debate("system", "分歧强度超过阈值，需要深度讨论")
        elif divergence.consensus_type in [ConsensusType.CORE, ConsensusType.STRATEGIC] and divergence.intensity >= 0.5:
            divergence.mark_for_debate("system", "核心/战略层面存在分歧，需要深入讨论")

    def update_consensus_support(self, consensus_id: str, supporter: str, action: str = "add") -> bool:
        try:
            index = int(consensus_id.split("_")[1])
            if 0 <= index < len(self.consensus_points):
                if action == "add":
                    return self.consensus_points[index].add_supporter(supporter)
                elif action == "remove":
                    return self.consensus_points[index].remove_supporter(supporter)
        except (IndexError, ValueError):
            pass
        return False

    def calculate_overall_consensus(self) -> Dict[str, Any]:
        return self.calculate_enhanced_consensus()

    def _identify_debate_requirements(self) -> List[Dict[str, Any]]:
        debate_items = []
        for i, dp in enumerate(self.divergence_points):
            if dp.requires_debate or dp.severity in [ConflictSeverity.CRITICAL, ConflictSeverity.HIGH]:
                debate_items.append({"divergence_id": f"divergence_{i}", "content": dp.content, "severity": dp.severity.value, "intensity": dp.intensity, "opposing_positions": dp.opposing_positions, "participants": list(dp.proponents.keys()), "suggested_strategy": self._recommend_resolution_strategy(dp), "priority": "high" if dp.severity == ConflictSeverity.CRITICAL else "medium"})
        return debate_items

    def _recommend_resolution_strategy(self, divergence: DivergencePoint) -> str:
        if divergence.severity == ConflictSeverity.CRITICAL:
            return ConflictResolutionStrategy.DEBATE.value if divergence.consensus_type in [ConsensusType.CORE, ConsensusType.STRATEGIC] else ConflictResolutionStrategy.MEDIATION.value
        if divergence.severity == ConflictSeverity.HIGH:
            return ConflictResolutionStrategy.VOTING.value if len(divergence.proponents) >= 4 else ConflictResolutionStrategy.DEBATE.value
        if divergence.intensity >= 0.6:
            return ConflictResolutionStrategy.COMPROMISE.value
        return ConflictResolutionStrategy.DATA_DRIVEN.value

    def _calculate_consensus_trend(self) -> str:
        if len(self.consensus_points) < 2:
            return "stable"
        sorted_points = sorted(self.consensus_points, key=lambda x: x.created_at)
        recent_strength = sum(cp.strength for cp in sorted_points[-3:]) / min(3, len(sorted_points))
        early_strength = sum(cp.strength for cp in sorted_points[:3]) / min(3, len(sorted_points))
        if recent_strength > early_strength * 1.1:
            return "improving"
        elif recent_strength < early_strength * 0.9:
            return "declining"
        return "stable"

    def generate_conflict_resolution_plan(self, divergence_id: str) -> Optional[ConflictResolution]:
        try:
            index = int(divergence_id.split("_")[1])
            if index < 0 or index >= len(self.divergence_points):
                return None
            divergence = self.divergence_points[index]
            strategy = self._recommend_resolution_strategy(divergence)
            if strategy == ConflictResolutionStrategy.DEBATE.value:
                suggested_approach = self._generate_debate_plan(divergence)
            elif strategy == ConflictResolutionStrategy.VOTING.value:
                suggested_approach = self._generate_voting_plan(divergence)
            elif strategy == ConflictResolutionStrategy.MEDIATION.value:
                suggested_approach = self._generate_mediation_plan(divergence)
            else:
                suggested_approach = self._generate_compromise_plan(divergence)
            resolution = ConflictResolution(divergence_id=divergence_id, strategy=strategy, suggested_approach=suggested_approach, participants_involved=list(divergence.proponents.keys()), expected_outcome=f"通过{strategy}策略解决分歧")
            self.conflict_resolutions.append(resolution)
            divergence.record_resolution_attempt(strategy, "计划已生成")
            return resolution
        except (IndexError, ValueError):
            return None

    def _generate_debate_plan(self, divergence: DivergencePoint) -> str:
        participants = list(divergence.proponents.keys())
        return f"深度辩论计划：参与专家{', '.join(participants)}，流程：1.各方阐述立场 2.交叉质询 3.寻求共同点 4.形成折中方案"

    def _generate_voting_plan(self, divergence: DivergencePoint) -> str:
        return "投票解决计划：列出所有立场选项，每人一票，简单多数获胜"

    def _generate_mediation_plan(self, divergence: DivergencePoint) -> str:
        return "调解计划：指定中立调解者，分别听取意见，识别共同利益，提出折中方案"

    def _generate_compromise_plan(self, divergence: DivergencePoint) -> str:
        return "妥协方案计划：评估各方立场，识别可接受要素，形成平衡方案"

    def execute_resolution(self, resolution_id: int, success: bool, result: str) -> bool:
        if resolution_id < 0 or resolution_id >= len(self.conflict_resolutions):
            return False
        resolution = self.conflict_resolutions[resolution_id]
        resolution.executed = True
        resolution.execution_result = result
        resolution.executed_at = datetime.now().isoformat()
        try:
            div_index = int(resolution.divergence_id.split("_")[1])
            if 0 <= div_index < len(self.divergence_points):
                divergence = self.divergence_points[div_index]
                if success:
                    divergence.intensity *= 0.5
                divergence.record_resolution_attempt(resolution.strategy.value, result)
        except (IndexError, ValueError):
            pass
        return True

    def get_consensus_status(self) -> Dict[str, Any]:
        overall = self.calculate_overall_consensus()
        return {
            "consensus_points_count": len(self.consensus_points), "divergence_points_count": len(self.divergence_points),
            "overall_consensus_level": overall["overall_level"], "core_consensus_level": overall.get("core_consensus_level", 0),
            "strategic_consensus_level": overall.get("strategic_consensus_level", 0),
            "strong_consensus_points": [{"content": cp.content, "type": cp.consensus_type.value, "supporters": cp.supporters, "strength": cp.strength} for cp in self.consensus_points if cp.strength > 0.7],
            "intense_divergences": [{"content": dp.content, "severity": dp.severity.value, "proponents": list(dp.proponents.keys()), "intensity": dp.intensity, "requires_debate": dp.requires_debate} for dp in self.divergence_points if dp.intensity > 0.7],
            "debate_required": overall.get("debate_required", []), "consensus_trend": overall.get("consensus_trend", "stable")
        }

    def generate_consensus_report(self) -> Dict[str, Any]:
        """
        生成完整的共识报告
        
        Returns:
            包含共识分析、分歧点、建议等的完整报告
        """
        # 获取增强版共识计算结果
        enhanced = self.calculate_enhanced_consensus()
        status = self.get_consensus_status()
        
        # 构建共识点列表
        consensus_points_detail = []
        for cp in self.consensus_points:
            consensus_points_detail.append({
                "content": cp.content,
                "type": cp.consensus_type.value if hasattr(cp.consensus_type, 'value') else str(cp.consensus_type),
                "strength": cp.strength,
                "supporters": cp.supporters,
                "priority": cp.priority.value if hasattr(cp.priority, 'value') else str(cp.priority),
                "round_created": cp.round_created
            })
        
        # 构建分歧点列表
        divergence_points_detail = []
        for dp in self.divergence_points:
            divergence_points_detail.append({
                "content": dp.content,
                "intensity": dp.intensity,
                "severity": dp.severity.value if hasattr(dp.severity, 'value') else str(dp.severity),
                "proponents": list(dp.proponents.keys()) if isinstance(dp.proponents, dict) else dp.proponents,
                "requires_debate": dp.requires_debate,
                "round_created": dp.round_created
            })
        
        return {
            "overall_consensus": {
                "overall_level": enhanced.get("overall_level", 0.0),
                "analysis": enhanced.get("analysis", "无分析数据"),
                "consensus_trend": enhanced.get("consensus_trend", "stable"),
                "confidence_level": enhanced.get("confidence_level", 0.0)
            },
            "hierarchy_analysis": enhanced.get("hierarchy_analysis", {}),
            "multi_dimension_scores": enhanced.get("multi_dimension_scores", {}),
            "key_consensus_points": consensus_points_detail,
            "key_divergence_points": divergence_points_detail,
            "strong_consensus_points": status.get("strong_consensus_points", []),
            "intense_divergences": status.get("intense_divergences", []),
            "debate_required": enhanced.get("debate_required", []),
            "trajectory_prediction": enhanced.get("trajectory_prediction", {}),
            "discussion_phase": enhanced.get("discussion_phase", "unknown"),
            "momentum": enhanced.get("momentum", 0.0),
            "total_rounds_completed": self.current_round,
            "generated_at": datetime.now().isoformat()
        }

    def export_data(self) -> str:
        data = {
            "consensus_points": [cp.to_dict() for cp in self.consensus_points],
            "divergence_points": [dp.to_dict() for dp in self.divergence_points],
            "conflict_resolutions": [{"divergence_id": cr.divergence_id, "strategy": cr.strategy.value, "suggested_approach": cr.suggested_approach, "executed": cr.executed, "result": cr.execution_result} for cr in self.conflict_resolutions],
            "discussion_summary": self.discussion_summary, "adaptive_decay_model": self.adaptive_decay_model.to_dict(),
            "dependency_graph": self.dependency_graph.to_dict(), "dynamic_weight_calculator": self.dynamic_weight_calculator.to_dict(),
            "consensus_aggregator": self.consensus_aggregator.to_dict(), "total_rounds_estimate": self.total_rounds_estimate,
            "exported_at": datetime.now().isoformat()
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def import_data(self, json_data: str) -> bool:
        try:
            data = json.loads(json_data)
            self.consensus_points = [ConsensusPoint(content=cp_data["content"], consensus_type=ConsensusType(cp_data.get("consensus_type", "auxiliary")), priority=ConsensusPriority(cp_data.get("priority", "medium")), supporters=cp_data.get("supporters", []), strength=cp_data.get("strength", 0.0), created_at=cp_data.get("created_at"), evidence=cp_data.get("evidence", []), topic_keywords=cp_data.get("topic_keywords", []), round_created=cp_data.get("round_created", 1), verification_count=cp_data.get("verification_count", 0), importance_score=cp_data.get("importance_score", 0.5)) for cp_data in data.get("consensus_points", [])]
            self.divergence_points = [DivergencePoint(content=dp_data["content"], consensus_type=ConsensusType(dp_data.get("consensus_type", "auxiliary")), proponents=dp_data.get("proponents", {}), intensity=dp_data.get("intensity", 0.0), severity=ConflictSeverity(dp_data.get("severity", "low")), created_at=dp_data.get("created_at"), discussion_history=dp_data.get("discussion_history", []), potential_resolutions=dp_data.get("potential_resolutions", []), related_consensus=dp_data.get("related_consensus", []), round_created=dp_data.get("round_created", 1), resolution_attempts=dp_data.get("resolution_attempts", 0), requires_debate=dp_data.get("requires_debate", False)) for dp_data in data.get("divergence_points", [])]
            self.discussion_summary = data.get("discussion_summary", self.discussion_summary)
            return True
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Invalid data format: {str(e)}")

    def get_serializable_state(self) -> Dict[str, Any]:
        return {
            "consensus_points": [cp.to_dict() for cp in self.consensus_points],
            "divergence_points": [dp.to_dict() for dp in self.divergence_points],
            "conflict_resolutions": [{"divergence_id": cr.divergence_id, "strategy": cr.strategy.value if hasattr(cr.strategy, 'value') else str(cr.strategy), "suggested_approach": cr.suggested_approach, "participants_involved": cr.participants_involved, "expected_outcome": cr.expected_outcome, "created_at": cr.created_at, "executed": cr.executed, "execution_result": cr.execution_result, "executed_at": cr.executed_at} for cr in self.conflict_resolutions],
            "discussion_summary": self.discussion_summary, "current_round": self.current_round, "consensus_history": self.consensus_history,
            "stability_tracker": self._stability_tracker, "adaptive_decay_model": self.adaptive_decay_model.to_dict(),
            "dependency_graph": self.dependency_graph.to_dict(), "dynamic_weight_calculator": self.dynamic_weight_calculator.to_dict(),
            "consensus_aggregator": self.consensus_aggregator.to_dict(), "total_rounds_estimate": self.total_rounds_estimate,
            "conflict_trigger_manager": self.conflict_trigger_manager.to_dict(), "resolution_orchestrator": self.resolution_orchestrator.to_dict(),
            "state_timestamp": datetime.now().isoformat()
        }

    def restore_from_state(self, state: Dict[str, Any]) -> bool:
        try:
            self.consensus_points = []
            for cp_data in state.get("consensus_points", []):
                cp = ConsensusPoint(content=cp_data["content"], consensus_type=ConsensusType(cp_data.get("consensus_type", "auxiliary")), priority=ConsensusPriority(cp_data.get("priority", 3)), supporters=cp_data.get("supporters", []), strength=cp_data.get("strength", 0.0), created_at=cp_data.get("created_at"), evidence=cp_data.get("evidence", []), topic_keywords=cp_data.get("topic_keywords", []), round_created=cp_data.get("round_created", 1), verification_count=cp_data.get("verification_count", 0), importance_score=cp_data.get("importance_score", 0.5))
                cp.related_divergences = cp_data.get("related_divergences", [])
                cp.last_updated = cp_data.get("last_updated", cp.created_at)
                cp.stability_score = cp_data.get("stability_score", 0.5)
                self.consensus_points.append(cp)
            self.divergence_points = []
            for dp_data in state.get("divergence_points", []):
                dp = DivergencePoint(content=dp_data["content"], consensus_type=ConsensusType(dp_data.get("consensus_type", "auxiliary")), proponents=dp_data.get("proponents", {}), intensity=dp_data.get("intensity", 0.0), severity=ConflictSeverity(dp_data.get("severity", "low")), created_at=dp_data.get("created_at"), discussion_history=dp_data.get("discussion_history", []), potential_resolutions=dp_data.get("potential_resolutions", []), related_consensus=dp_data.get("related_consensus", []), round_created=dp_data.get("round_created", 1), resolution_attempts=dp_data.get("resolution_attempts", 0), requires_debate=dp_data.get("requires_debate", False))
                dp.last_updated = dp_data.get("last_updated", dp.created_at)
                dp.opposing_positions = dp_data.get("opposing_positions", [])
                self.divergence_points.append(dp)
            self.discussion_summary = state.get("discussion_summary", self.discussion_summary)
            self.current_round = state.get("current_round", 0)
            self.consensus_history = state.get("consensus_history", [])
            self._stability_tracker = state.get("stability_tracker", {})
            if "adaptive_decay_model" in state:
                self.adaptive_decay_model = AdaptiveDecayModel.from_dict(state["adaptive_decay_model"])
            if "dependency_graph" in state:
                self.dependency_graph = ConsensusDependencyGraph.from_dict(state["dependency_graph"])
            if "dynamic_weight_calculator" in state:
                self.dynamic_weight_calculator = DynamicWeightCalculator.from_dict(state["dynamic_weight_calculator"])
            if "consensus_aggregator" in state:
                self.consensus_aggregator = ConsensusAggregator.from_dict(state["consensus_aggregator"])
            if "total_rounds_estimate" in state:
                self.total_rounds_estimate = state["total_rounds_estimate"]
            if "conflict_trigger_manager" in state:
                self.conflict_trigger_manager = ConflictTriggerManager.from_dict(state["conflict_trigger_manager"], self)
            if "resolution_orchestrator" in state:
                self.resolution_orchestrator = ResolutionOrchestrator.from_dict(state["resolution_orchestrator"])
            return True
        except Exception as e:
            raise ValueError(f"恢复状态失败: {str(e)}")

    def check_and_handle_conflicts(self, current_round: int = None) -> Generator[Dict[str, Any], None, None]:
        if current_round is None:
            current_round = self.current_round
        auto_triggers = self.conflict_trigger_manager.check_and_trigger(current_round)
        if not auto_triggers:
            return
        yield {"step": "conflicts_detected", "count": len(auto_triggers), "alerts": [a.to_dict() for a in auto_triggers]}
        for alert in auto_triggers:
            self.conflict_trigger_manager.acknowledge_alert(alert.alert_id)
            yield {"step": "conflict_acknowledged", "alert_id": alert.alert_id, "divergence_id": alert.divergence_id, "strategy": alert.recommended_strategy.value}
            for step in self._execute_conflict_resolution(alert):
                yield step

    def _execute_conflict_resolution(self, alert: ConflictAlert) -> Generator[Dict[str, Any], None, None]:
        try:
            divergence_index = int(alert.divergence_id.split("_")[1])
            if divergence_index < 0 or divergence_index >= len(self.divergence_points):
                yield {"step": "resolution_error", "error": f"无效的分歧ID: {alert.divergence_id}"}
                return
            divergence = self.divergence_points[divergence_index]
        except (IndexError, ValueError) as e:
            yield {"step": "resolution_error", "error": str(e)}
            return
        session = self.resolution_orchestrator.start_resolution(alert, divergence)
        self.conflict_trigger_manager.start_resolution(alert.alert_id)
        yield {"step": "resolution_started", "session_id": session.session_id, "strategy": session.strategy.value}
        result = None
        for step in self.resolution_orchestrator.execute_session(session, divergence):
            yield step
            if isinstance(step, ResolutionResult):
                result = step
        if result and result.success:
            divergence.record_resolution_attempt(session.strategy.value, result.execution_summary)
            for cp_data in result.new_consensus_points:
                self.add_consensus(content=cp_data.get("content", ""), consensus_type=ConsensusType.AUXILIARY, supporters=list(divergence.proponents.keys()), strength=0.6)
            self.conflict_trigger_manager.complete_resolution(alert.alert_id, True)
            yield {"step": "resolution_completed", "session_id": session.session_id, "success": True, "outcome": result.outcome_type.value, "new_consensus_count": len(result.new_consensus_points)}
        else:
            new_strategy = self.resolution_orchestrator.escalate_strategy(session.session_id, divergence)
            if new_strategy:
                yield {"step": "resolution_escalated", "session_id": session.session_id, "new_strategy": new_strategy.value}
            else:
                self.conflict_trigger_manager.complete_resolution(alert.alert_id, False)
                yield {"step": "resolution_failed", "session_id": session.session_id, "message": "无法解决，已耗尽所有策略"}

    def start_conflict_resolution(self, divergence_id: str, strategy: ConflictResolutionStrategy = None) -> Optional[str]:
        try:
            divergence_index = int(divergence_id.split("_")[1])
            if divergence_index < 0 or divergence_index >= len(self.divergence_points):
                return None
            divergence = self.divergence_points[divergence_index]
        except (IndexError, ValueError):
            return None
        if strategy is None:
            strategy = self.resolution_orchestrator.select_best_strategy(divergence)
        alert = ConflictAlert(alert_id="", divergence_id=divergence_id, trigger_condition=ConflictTriggerCondition.EXPERT_REQUEST, severity=divergence.severity, recommended_strategy=strategy, urgency_score=0.7, participants=list(divergence.proponents.keys()))
        session = self.resolution_orchestrator.start_resolution(alert, divergence)
        return session.session_id

    def get_pending_conflicts(self) -> List[Dict[str, Any]]:
        return [alert.to_dict() for alert in self.conflict_trigger_manager.pending_alerts]

    def get_conflict_resolution_status(self) -> Dict[str, Any]:
        return {"trigger_manager": self.conflict_trigger_manager.get_statistics(), "orchestrator": self.resolution_orchestrator.get_statistics(), "pending_alerts": len(self.conflict_trigger_manager.pending_alerts), "active_sessions": len(self.resolution_orchestrator.active_sessions)}

    def record_discussion_round(self, round_number: int, speeches: List[Dict[str, Any]] = None, consensus_updates: List[Dict[str, Any]] = None, divergence_updates: List[Dict[str, Any]] = None):
        self.set_current_round(round_number)
        self.discussion_summary["total_rounds"] = round_number
        round_record = {"round_number": round_number, "timestamp": datetime.now().isoformat(), "overall_level": self.calculate_overall_consensus().get("overall_level", 0), "consensus_count": len(self.consensus_points), "divergence_count": len(self.divergence_points)}
        self.consensus_history.append(round_record)


# 别名
ConsensusTracker = EnhancedConsensusTracker
