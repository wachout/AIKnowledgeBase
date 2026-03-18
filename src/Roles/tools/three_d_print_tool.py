# -*- coding: utf-8 -*-
"""
3D打印工具智能体

为第三层具象化智能体提供硬件形态设计能力，支持各种3D打印相关的设计和生成：
- 结构设计（外壳、支架、连接件等）
- 机械部件设计（齿轮、轴承座、传动件等）
- 电子外壳设计（控制盒、传感器外壳等）
- 原型制作指导（材料选择、打印参数、后处理）
"""

import logging
import uuid
import json
import re
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

from .base_tool import (
    BaseTool,
    ToolResult,
    ParameterType,
    ParameterDefinition,
    ParameterSchema,
    QualityAssessment
)

try:
    from Config.llm_config import get_chat, get_chat_long
except Exception:
    get_chat = None
    get_chat_long = None

logger = logging.getLogger(__name__)


# ============================================================================
# 3D打印相关枚举
# ============================================================================

class PrintMaterial:
    """打印材料类型"""
    PLA = "PLA"              # 聚乳酸，常用，环保
    ABS = "ABS"              # ABS塑料，耐冲击
    PETG = "PETG"            # PETG，兼顾强度和柔韧性
    TPU = "TPU"              # 热塑性聚氨酯，柔性材料
    NYLON = "Nylon"          # 尼龙，高强度
    RESIN = "Resin"          # 树脂（光固化）
    METAL = "Metal"          # 金属（SLM/DMLS）
    CARBON_FIBER = "CarbonFiber"  # 碳纤维增强
    WOOD_FILL = "WoodFill"   # 木质填充
    OTHER = "Other"


class DesignType:
    """设计类型"""
    STRUCTURAL = "structural"        # 结构件（外壳、支架）
    MECHANICAL = "mechanical"        # 机械件（齿轮、轴承座）
    ELECTRONIC = "electronic"        # 电子外壳
    CONNECTOR = "connector"          # 连接件
    PROTOTYPE = "prototype"          # 原型/模型
    FIXTURE = "fixture"              # 夹具/工装
    ENCLOSURE = "enclosure"          # 封装外壳
    CUSTOM = "custom"                # 定制设计


class PrintTechnology:
    """打印技术"""
    FDM = "FDM"              # 熔融沉积成型
    SLA = "SLA"              # 光固化
    SLS = "SLS"              # 选择性激光烧结
    DMLS = "DMLS"            # 直接金属激光烧结
    MJF = "MJF"              # 多射流熔融
    DLP = "DLP"              # 数字光处理
    OTHER = "Other"


# ============================================================================
# 3D设计结果
# ============================================================================

@dataclass
class ThreeDDesignResult:
    """3D设计结果"""
    success: bool
    design_type: str
    material: str
    technology: str
    
    # 设计规格
    dimensions: Dict[str, float] = field(default_factory=dict)  # 尺寸 (x, y, z, 单位mm)
    wall_thickness: float = 0.0        # 壁厚 (mm)
    infill_percentage: int = 0         # 填充率 (%)
    
    # 设计描述
    design_description: str = ""       # 设计说明
    structural_features: List[str] = field(default_factory=list)  # 结构特征
    
    # CAD相关
    cad_instructions: str = ""         # CAD建模指导
    openscad_code: str = ""            # OpenSCAD代码（如适用）
    parametric_model: str = ""         # 参数化模型描述
    
    # 打印参数
    print_parameters: Dict[str, Any] = field(default_factory=dict)
    
    # 后处理
    post_processing: List[str] = field(default_factory=list)
    
    # 成本估算
    estimated_print_time: str = ""     # 预计打印时间
    estimated_material_cost: str = ""  # 预计材料成本
    
    # 注意事项
    design_notes: List[str] = field(default_factory=list)
    error: str = ""
    raw_response: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "design_type": self.design_type,
            "material": self.material,
            "technology": self.technology,
            "dimensions": self.dimensions,
            "wall_thickness": self.wall_thickness,
            "infill_percentage": self.infill_percentage,
            "design_description": self.design_description,
            "structural_features": self.structural_features,
            "cad_instructions": self.cad_instructions,
            "openscad_code": self.openscad_code,
            "parametric_model": self.parametric_model,
            "print_parameters": self.print_parameters,
            "post_processing": self.post_processing,
            "estimated_print_time": self.estimated_print_time,
            "estimated_material_cost": self.estimated_material_cost,
            "design_notes": self.design_notes,
            "error": self.error,
            "raw_response": self.raw_response[:2000] if self.raw_response else "",
            "generated_at": self.generated_at
        }


# ============================================================================
# 3D打印工具智能体
# ============================================================================

class ThreeDPrintTool(BaseTool):
    """
    3D打印工具智能体

    为第三层具象化智能体提供硬件形态设计能力：
    - 根据具象化描述生成3D设计方案
    - 提供结构设计、机械部件设计、电子外壳设计等
    - 输出CAD建模指导和OpenSCAD参数化代码
    - 提供打印参数建议和后处理指导
    """

    def __init__(
        self,
        tool_id: str = None,
        llm_adapter=None,
        default_material: str = PrintMaterial.PLA,
        default_technology: str = PrintTechnology.FDM
    ):
        # 定义参数模式
        schema = ParameterSchema(
            parameters=[
                ParameterDefinition(
                    name="task_description",
                    param_type=ParameterType.STRING,
                    description="设计任务描述：需要设计的硬件部件或结构",
                    required=True
                ),
                ParameterDefinition(
                    name="design_type",
                    param_type=ParameterType.STRING,
                    description="设计类型",
                    required=False,
                    default=DesignType.STRUCTURAL,
                    constraints={"enum": [
                        DesignType.STRUCTURAL, DesignType.MECHANICAL,
                        DesignType.ELECTRONIC, DesignType.CONNECTOR,
                        DesignType.PROTOTYPE, DesignType.FIXTURE,
                        DesignType.ENCLOSURE, DesignType.CUSTOM
                    ]}
                ),
                ParameterDefinition(
                    name="material",
                    param_type=ParameterType.STRING,
                    description="打印材料",
                    required=False,
                    default=PrintMaterial.PLA,
                    constraints={"enum": [
                        PrintMaterial.PLA, PrintMaterial.ABS, PrintMaterial.PETG,
                        PrintMaterial.TPU, PrintMaterial.NYLON, PrintMaterial.RESIN,
                        PrintMaterial.METAL, PrintMaterial.CARBON_FIBER, PrintMaterial.OTHER
                    ]}
                ),
                ParameterDefinition(
                    name="technology",
                    param_type=ParameterType.STRING,
                    description="打印技术",
                    required=False,
                    default=PrintTechnology.FDM,
                    constraints={"enum": [
                        PrintTechnology.FDM, PrintTechnology.SLA, PrintTechnology.SLS,
                        PrintTechnology.DMLS, PrintTechnology.MJF, PrintTechnology.DLP,
                        PrintTechnology.OTHER
                    ]}
                ),
                ParameterDefinition(
                    name="context",
                    param_type=ParameterType.STRING,
                    description="上下文信息（如具象化描述、数字化描述等）",
                    required=False,
                    default=""
                ),
                ParameterDefinition(
                    name="constraints",
                    param_type=ParameterType.LIST,
                    description="设计约束条件（如尺寸限制、强度要求等）",
                    required=False,
                    default=[]
                ),
                ParameterDefinition(
                    name="generate_openscad",
                    param_type=ParameterType.BOOLEAN,
                    description="是否生成OpenSCAD参数化代码",
                    required=False,
                    default=True
                )
            ],
            version="1.0.0"
        )

        super().__init__(
            name="three_d_print",
            description="3D打印工具智能体：根据具象化描述生成硬件形态设计方案，提供CAD指导和打印参数",
            tool_type="implementation",
            version="1.0.0",
            parameter_schema=schema
        )

        self.tool_id = tool_id or f"3d_print_{uuid.uuid4().hex[:6]}"
        self.llm_adapter = llm_adapter
        self.default_material = default_material
        self.default_technology = default_technology
        self.design_history: List[ThreeDDesignResult] = []

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        同步执行3D设计生成

        Args:
            parameters: 包含 task_description, design_type, material, technology, context, constraints

        Returns:
            ToolResult 包含3D设计方案
        """
        try:
            task_description = parameters.get("task_description", "")
            if not task_description:
                return ToolResult(
                    success=False,
                    error="缺少任务描述(task_description)",
                    metadata={"tool_id": self.tool_id}
                )

            design_type = parameters.get("design_type", DesignType.STRUCTURAL)
            material = parameters.get("material", self.default_material)
            technology = parameters.get("technology", self.default_technology)
            context = parameters.get("context", "")
            constraints = parameters.get("constraints", [])
            generate_openscad = parameters.get("generate_openscad", True)

            # 构建提示词
            prompt = self._build_design_prompt(
                task_description=task_description,
                design_type=design_type,
                material=material,
                technology=technology,
                context=context,
                constraints=constraints,
                generate_openscad=generate_openscad
            )

            # 调用LLM
            response = self._invoke_llm_sync(prompt)
            if not response:
                return ToolResult(
                    success=False,
                    error="LLM调用失败或返回为空",
                    metadata={"tool_id": self.tool_id}
                )

            # 解析响应
            result = self._parse_design_response(response, design_type, material, technology)
            self.design_history.append(result)

            if result.success:
                return ToolResult(
                    success=True,
                    data=result.to_dict(),
                    metadata={
                        "tool_id": self.tool_id,
                        "design_type": design_type,
                        "material": material,
                        "technology": technology
                    },
                    quality_assessment=self._assess_design_quality(result)
                )
            else:
                return ToolResult(
                    success=False,
                    data=result.to_dict(),
                    error=result.error or "3D设计生成失败",
                    metadata={"tool_id": self.tool_id}
                )

        except Exception as e:
            logger.exception(f"3D设计生成异常: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"tool_id": self.tool_id}
            )

    async def execute_async(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        异步执行3D设计生成

        Args:
            parameters: 包含 task_description, design_type, material, technology, context, constraints

        Returns:
            ToolResult 包含3D设计方案
        """
        try:
            task_description = parameters.get("task_description", "")
            if not task_description:
                return ToolResult(
                    success=False,
                    error="缺少任务描述(task_description)",
                    metadata={"tool_id": self.tool_id}
                )

            design_type = parameters.get("design_type", DesignType.STRUCTURAL)
            material = parameters.get("material", self.default_material)
            technology = parameters.get("technology", self.default_technology)
            context = parameters.get("context", "")
            constraints = parameters.get("constraints", [])
            generate_openscad = parameters.get("generate_openscad", True)

            # 构建提示词
            prompt = self._build_design_prompt(
                task_description=task_description,
                design_type=design_type,
                material=material,
                technology=technology,
                context=context,
                constraints=constraints,
                generate_openscad=generate_openscad
            )

            # 异步调用LLM
            response = await self._invoke_llm_async(prompt)
            if not response:
                return ToolResult(
                    success=False,
                    error="LLM调用失败或返回为空",
                    metadata={"tool_id": self.tool_id}
                )

            # 解析响应
            result = self._parse_design_response(response, design_type, material, technology)
            self.design_history.append(result)

            if result.success:
                return ToolResult(
                    success=True,
                    data=result.to_dict(),
                    metadata={
                        "tool_id": self.tool_id,
                        "design_type": design_type,
                        "material": material,
                        "technology": technology
                    },
                    quality_assessment=self._assess_design_quality(result)
                )
            else:
                return ToolResult(
                    success=False,
                    data=result.to_dict(),
                    error=result.error or "3D设计生成失败",
                    metadata={"tool_id": self.tool_id}
                )

        except Exception as e:
            logger.exception(f"3D设计生成异常: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"tool_id": self.tool_id}
            )

    async def generate_design_stream(
        self,
        task_description: str,
        design_type: str = None,
        material: str = None,
        technology: str = None,
        context: str = "",
        constraints: List[str] = None,
        generate_openscad: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        流式生成3D设计方案

        Args:
            task_description: 任务描述
            design_type: 设计类型
            material: 打印材料
            technology: 打印技术
            context: 上下文信息
            constraints: 约束条件
            generate_openscad: 是否生成OpenSCAD代码

        Yields:
            生成的设计内容片段
        """
        design_type = design_type or DesignType.STRUCTURAL
        material = material or self.default_material
        technology = technology or self.default_technology
        constraints = constraints or []

        prompt = self._build_design_prompt(
            task_description=task_description,
            design_type=design_type,
            material=material,
            technology=technology,
            context=context,
            constraints=constraints,
            generate_openscad=generate_openscad
        )

        response_parts = []
        async for chunk in self._invoke_llm_stream(prompt):
            yield chunk
            response_parts.append(chunk)

        # 解析完整响应并保存到历史
        full_response = "".join(response_parts)
        result = self._parse_design_response(full_response, design_type, material, technology)
        self.design_history.append(result)

    def _build_design_prompt(
        self,
        task_description: str,
        design_type: str,
        material: str,
        technology: str,
        context: str = "",
        constraints: List[str] = None,
        generate_openscad: bool = True
    ) -> str:
        """构建3D设计提示词"""
        constraints = constraints or []
        constraints_block = ""
        if constraints:
            constraints_list = "\n".join(f"- {c}" for c in constraints)
            constraints_block = f"""
## 设计约束条件

{constraints_list}
"""

        context_block = ""
        if context:
            context_block = f"""
## 上下文信息（来自具象化描述）

{context}
"""

        openscad_instruction = ""
        if generate_openscad:
            openscad_instruction = """
6. **OpenSCAD代码**：生成参数化的OpenSCAD代码，便于后续修改和定制"""

        return f"""# Role：3D打印设计专家

## Background
你是一位经验丰富的3D打印和工业设计专家，擅长将具象化的需求描述转化为可打印的3D设计方案。
你需要根据任务描述和上下文信息，生成完整的3D设计方案，包括结构设计、打印参数和后处理指导。

## 任务信息

- **设计任务**: {task_description}
- **设计类型**: {design_type}
- **打印材料**: {material}
- **打印技术**: {technology}
{context_block}{constraints_block}
## 设计要求

1. **结构设计**：考虑打印可行性（悬垂角度、支撑需求、收缩补偿）
2. **尺寸精度**：考虑打印机精度和后处理余量
3. **强度分析**：确保结构强度满足使用需求
4. **装配考虑**：设计合适的配合公差和装配特征
5. **材料特性**：充分利用{material}的材料特性{openscad_instruction}

## 材料特性参考

- **PLA**: 易打印，硬度高，但耐热性差（~60°C）
- **ABS**: 耐冲击，耐热（~100°C），需要加热平台
- **PETG**: 平衡强度和柔韧性，耐化学腐蚀
- **TPU**: 柔性材料，适合密封件和减震部件
- **Nylon**: 高强度，耐磨，吸湿需干燥
- **Resin**: 高精度，表面光滑，但脆性较大
- **Metal**: 高强度，可用于功能件，成本高

## 输出格式（JSON，放在 ```json 代码块中）

```json
{{
  "design_description": "设计方案详细说明",
  "dimensions": {{"x": 100, "y": 50, "z": 30, "unit": "mm"}},
  "wall_thickness": 2.0,
  "infill_percentage": 20,
  "structural_features": ["特征1", "特征2"],
  "cad_instructions": "CAD建模步骤指导",
  "openscad_code": "// OpenSCAD参数化代码（如需要）",
  "parametric_model": "参数化模型描述",
  "print_parameters": {{
    "layer_height": 0.2,
    "print_speed": 50,
    "nozzle_temp": 200,
    "bed_temp": 60,
    "supports": "tree",
    "adhesion": "brim"
  }},
  "post_processing": ["后处理步骤1", "后处理步骤2"],
  "estimated_print_time": "预计打印时间",
  "estimated_material_cost": "预计材料成本",
  "design_notes": ["注意事项1", "注意事项2"]
}}
```

请生成3D设计方案：
"""

    def _invoke_llm_sync(self, prompt: str) -> Optional[str]:
        """同步调用LLM"""
        try:
            if self.llm_adapter:
                response = self.llm_adapter.invoke(prompt)
                return response.content if hasattr(response, "content") else str(response)

            if get_chat:
                llm = get_chat(temperature=0.2, streaming=False)
                response = llm.invoke(prompt)
                return response.content if hasattr(response, "content") else str(response)

            logger.warning("无可用LLM适配器")
            return None
        except Exception as e:
            logger.exception(f"LLM同步调用失败: {e}")
            return None

    async def _invoke_llm_async(self, prompt: str) -> Optional[str]:
        """异步调用LLM"""
        try:
            import asyncio

            if self.llm_adapter:
                if hasattr(self.llm_adapter, "ainvoke"):
                    response = await self.llm_adapter.ainvoke(prompt)
                else:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, lambda: self.llm_adapter.invoke(prompt)
                    )
                return response.content if hasattr(response, "content") else str(response)

            if get_chat:
                llm = get_chat(temperature=0.2, streaming=False)
                if hasattr(llm, "ainvoke"):
                    response = await llm.ainvoke(prompt)
                else:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, lambda: llm.invoke(prompt)
                    )
                return response.content if hasattr(response, "content") else str(response)

            logger.warning("无可用LLM适配器")
            return None
        except Exception as e:
            logger.exception(f"LLM异步调用失败: {e}")
            return None

    async def _invoke_llm_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """流式调用LLM"""
        try:
            if self.llm_adapter and hasattr(self.llm_adapter, "astream"):
                async for chunk in self.llm_adapter.astream(prompt):
                    if hasattr(chunk, "content"):
                        yield chunk.content
                    else:
                        yield str(chunk)
                return

            if get_chat:
                llm = get_chat(temperature=0.2, streaming=True)
                if hasattr(llm, "astream"):
                    async for chunk in llm.astream(prompt):
                        if hasattr(chunk, "content"):
                            yield chunk.content
                        else:
                            yield str(chunk)
                    return

            # 回退到同步调用
            response = await self._invoke_llm_async(prompt)
            if response:
                yield response
        except Exception as e:
            logger.exception(f"LLM流式调用失败: {e}")
            yield f"[错误] LLM调用失败: {e}"

    def _parse_design_response(
        self, response: str, design_type: str, material: str, technology: str
    ) -> ThreeDDesignResult:
        """解析LLM返回的3D设计响应"""
        result = ThreeDDesignResult(
            success=False,
            design_type=design_type,
            material=material,
            technology=technology,
            raw_response=response
        )

        try:
            # 尝试解析JSON
            m = re.search(r"```json\s*([\s\S]*?)\s*```", response)
            if m:
                json_str = m.group(1)
                # 清理控制字符
                json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', json_str)
                data = json.loads(json_str)

                result.success = True
                result.design_description = data.get("design_description", "")
                result.dimensions = data.get("dimensions", {})
                result.wall_thickness = data.get("wall_thickness", 0.0)
                result.infill_percentage = data.get("infill_percentage", 0)
                result.structural_features = data.get("structural_features", [])
                result.cad_instructions = data.get("cad_instructions", "")
                result.openscad_code = data.get("openscad_code", "")
                result.parametric_model = data.get("parametric_model", "")
                result.print_parameters = data.get("print_parameters", {})
                result.post_processing = data.get("post_processing", [])
                result.estimated_print_time = data.get("estimated_print_time", "")
                result.estimated_material_cost = data.get("estimated_material_cost", "")
                result.design_notes = data.get("design_notes", [])
                return result

            # 尝试提取OpenSCAD代码块
            scad_match = re.search(r"```(?:openscad|scad)\s*([\s\S]*?)\s*```", response, re.IGNORECASE)
            if scad_match:
                result.success = True
                result.openscad_code = scad_match.group(1).strip()
                result.design_description = "从响应中提取的OpenSCAD代码"
                return result

            # 无法解析，将整个响应作为设计描述
            if response.strip():
                result.success = True
                result.design_description = response.strip()

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"解析3D设计响应失败: {e}")
            result.error = f"解析失败: {e}"
            # 尝试提取任何代码块
            m = re.search(r"```[\w]*\s*([\s\S]*?)\s*```", response)
            if m:
                result.success = True
                result.design_description = m.group(1).strip()

        return result

    def _assess_design_quality(self, result: ThreeDDesignResult) -> QualityAssessment:
        """评估3D设计质量"""
        assessment = QualityAssessment()

        if not result.success:
            assessment.relevance_score = 0.0
            assessment.confidence_score = 0.0
            assessment.completeness_score = 0.0
            assessment.quality_level = "LOW"
            return assessment

        # 相关性评估
        relevance = 0.5  # 基础分
        if result.design_description:
            relevance += 0.2
        if result.dimensions:
            relevance += 0.15
        if result.structural_features:
            relevance += 0.15
        assessment.relevance_score = min(relevance, 1.0)

        # 可信度评估
        confidence = 0.4
        if result.wall_thickness > 0:
            confidence += 0.1
        if result.infill_percentage > 0:
            confidence += 0.1
        if result.print_parameters:
            confidence += 0.15
        if result.cad_instructions:
            confidence += 0.1
        if result.openscad_code:
            confidence += 0.15
        assessment.confidence_score = min(confidence, 1.0)

        # 完整性评估
        completeness = 0.2
        if result.dimensions:
            completeness += 0.1
        if result.print_parameters:
            completeness += 0.15
        if result.post_processing:
            completeness += 0.1
        if result.estimated_print_time:
            completeness += 0.1
        if result.design_notes:
            completeness += 0.1
        if result.openscad_code:
            completeness += 0.15
        if result.cad_instructions:
            completeness += 0.1
        assessment.completeness_score = min(completeness, 1.0)

        assessment.determine_quality_level()
        assessment.assessment_details = {
            "has_dimensions": bool(result.dimensions),
            "has_openscad": bool(result.openscad_code),
            "has_print_params": bool(result.print_parameters),
            "has_post_processing": bool(result.post_processing)
        }

        return assessment

    def get_supported_materials(self) -> List[str]:
        """获取支持的打印材料列表"""
        return [
            PrintMaterial.PLA, PrintMaterial.ABS, PrintMaterial.PETG,
            PrintMaterial.TPU, PrintMaterial.NYLON, PrintMaterial.RESIN,
            PrintMaterial.METAL, PrintMaterial.CARBON_FIBER, PrintMaterial.OTHER
        ]

    def get_supported_technologies(self) -> List[str]:
        """获取支持的打印技术列表"""
        return [
            PrintTechnology.FDM, PrintTechnology.SLA, PrintTechnology.SLS,
            PrintTechnology.DMLS, PrintTechnology.MJF, PrintTechnology.DLP,
            PrintTechnology.OTHER
        ]

    def get_supported_design_types(self) -> List[str]:
        """获取支持的设计类型列表"""
        return [
            DesignType.STRUCTURAL, DesignType.MECHANICAL, DesignType.ELECTRONIC,
            DesignType.CONNECTOR, DesignType.PROTOTYPE, DesignType.FIXTURE,
            DesignType.ENCLOSURE, DesignType.CUSTOM
        ]

    def get_design_history(self) -> List[Dict[str, Any]]:
        """获取设计历史"""
        return [r.to_dict() for r in self.design_history]

    def clear_history(self):
        """清空设计历史"""
        self.design_history.clear()

    def get_material_recommendations(self, use_case: str) -> Dict[str, Any]:
        """根据用例推荐材料"""
        recommendations = {
            "prototype": {
                "primary": PrintMaterial.PLA,
                "reason": "易打印，成本低，适合快速验证"
            },
            "functional": {
                "primary": PrintMaterial.PETG,
                "reason": "强度适中，耐化学腐蚀，适合功能件"
            },
            "mechanical": {
                "primary": PrintMaterial.NYLON,
                "reason": "高强度，耐磨，适合机械部件"
            },
            "flexible": {
                "primary": PrintMaterial.TPU,
                "reason": "柔性材料，适合密封件和减震部件"
            },
            "high_precision": {
                "primary": PrintMaterial.RESIN,
                "reason": "高精度，表面光滑，适合精密部件"
            },
            "high_strength": {
                "primary": PrintMaterial.CARBON_FIBER,
                "reason": "高强度重量比，适合承载结构"
            },
            "heat_resistant": {
                "primary": PrintMaterial.ABS,
                "reason": "耐热性好（~100°C），适合高温环境"
            }
        }
        return recommendations.get(use_case, recommendations["prototype"])
