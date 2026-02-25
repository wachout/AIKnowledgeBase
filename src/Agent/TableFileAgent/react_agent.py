# -*- coding:utf-8 -*-
"""
ReActAgent - 通用推理+行动智能体
工具调用、数据分析、工具使用
ReAct架构：用户指令，思考，行动，观察
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi

logger = logging.getLogger(__name__)


class ReActAgent:
    """ReAct智能体：推理+行动循环"""
    
    def __init__(self, max_iterations: int = 3):
        self.llm = get_chat_tongyi(temperature=0.5, enable_thinking=False)
        self.max_iterations = max_iterations
        
        self.react_prompt = ChatPromptTemplate.from_template(
            """你是一个ReAct智能体，采用"思考-行动-观察"的循环模式解决问题。

当前任务: {task}
历史观察: {observations}
当前迭代: {iteration}/{max_iterations}

请按照以下格式输出：
Thought: [你的思考过程，分析当前情况，决定下一步行动]
Action: [要执行的动作，格式：ACTION_NAME(参数1, 参数2, ...)]
Action Input: [动作的输入参数，JSON格式]

可用的动作：
- analyze_data: 分析数据
- calculate_statistics: 计算统计指标
- generate_chart: 生成图表
- interpret_result: 解读结果

输出格式（严格按照以下格式）：
Thought: ...
Action: ...
Action Input: ...
"""
        )
    
    def run(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        运行ReAct循环
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            执行结果
        """
        observations = []
        context = context or {}
        
        for iteration in range(1, self.max_iterations + 1):
            try:
                # 构建提示
                prompt = self.react_prompt.format(
                    task=task,
                    observations="\n".join(observations[-3:]) if observations else "无",
                    iteration=iteration,
                    max_iterations=self.max_iterations
                )
                
                # 调用LLM
                response = self.llm.invoke(prompt)
                content = response.content if hasattr(response, 'content') else str(response)
                
                # 解析响应
                action_result = self._parse_and_execute_action(content, context)
                observations.append(f"迭代{iteration}: {action_result.get('observation', '')}")
                
                # 检查是否完成任务
                if action_result.get("done", False):
                    return {
                        "success": True,
                        "result": action_result.get("result"),
                        "observations": observations,
                        "iterations": iteration
                    }
                
            except Exception as e:
                logger.error(f"❌ ReAct迭代{iteration}失败: {e}")
                observations.append(f"迭代{iteration}出错: {str(e)}")
        
        return {
            "success": False,
            "error": "达到最大迭代次数",
            "observations": observations
        }
    
    def _parse_and_execute_action(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """解析并执行动作"""
        try:
            # 简单解析（实际应该更robust）
            if "Action:" in content:
                action_line = [line for line in content.split("\n") if "Action:" in line][0]
                action = action_line.split("Action:")[1].strip()
                
                # 执行动作
                if "analyze_data" in action:
                    return {"observation": "数据已分析", "done": False}
                elif "calculate_statistics" in action:
                    return {"observation": "统计计算完成", "done": False}
                elif "generate_chart" in action:
                    return {"observation": "图表已生成", "done": False}
                elif "interpret_result" in action:
                    return {"observation": "结果已解读", "done": True, "result": context}
            
            return {"observation": "未识别到有效动作", "done": False}
            
        except Exception as e:
            logger.error(f"❌ 解析动作失败: {e}")
            return {"observation": f"解析失败: {str(e)}", "done": False}
