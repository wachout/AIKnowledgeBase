# -*- coding:utf-8 -*-
"""
统一的LLM配置工具
从.env文件中读取大模型配置。
QWEN_TYPE / MINMAX_TYPE / MULTIMODAL_TYPE 为 True 时表示使用该模型。
"""

import os
from typing import Optional
from dotenv import load_dotenv
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_openai import ChatOpenAI

# 加载.env文件
load_dotenv()


def _env_bool(key: str, default: bool = False) -> bool:
    """将环境变量解析为 bool：'true'/'1'/'yes' 为 True，否则为 False。"""
    val = (os.getenv(key, "") or "").strip().lower()
    return val in ("true", "1", "yes")


class LLMConfig:
    """LLM配置类，按 QWEN_TYPE / MINMAX_TYPE / MULTIMODAL_TYPE 选择使用哪套配置"""

    def __init__(self):
        # QWEN（通义/DeepSeek 等兼容 dashscope）
        self.qwen_api_key = os.getenv("QWEN_API_KEY", "") or os.getenv("LLM_API_KEY", "")
        self.qwen_base_url = os.getenv("QWEN_BASE_URL", "") or os.getenv("LLM_BASE_URL", "")
        self.qwen_model_id = os.getenv("QWEN_MODEL_ID", "") or os.getenv("LLM_MODEL_ID", "")
        self.qwen_model_name = os.getenv("QWEN_MODEL_NAME", "") or os.getenv("LLM_MODEL_NAME", "")
        self.qwen_type = _env_bool("QWEN_TYPE", False)

        # MINMAX
        self.minmax_api_key = os.getenv("MINMAX_API_KEY", "")
        self.minmax_base_url = os.getenv("MINMAX_BASE_URL", "")
        self.minmax_model_id = os.getenv("MINMAX_MODEL_ID", "")
        self.minmax_model_name = os.getenv("MINMAX_MODEL_NAME", "")
        self.minmax_type = _env_bool("MINMAX_TYPE", False)

        # 多模态
        self.multimodal_api_key = os.getenv("MULTIMODAL_API_KEY", "")
        self.multimodal_base_url = os.getenv("MULTIMODAL_BASE_URL", "")
        self.multimodal_model_id = os.getenv("MULTIMODAL_MODEL_ID", "")
        self.multimodal_model_name = os.getenv("MULTIMODAL_MODEL_NAME", "")
        self.multimodal_type = _env_bool("MULTIMODAL_TYPE", False)

        # 兼容旧逻辑：若未配置 *_TYPE，则根据“哪套有 key”决定默认
        if not self.qwen_type and not self.minmax_type:
            if self.qwen_api_key and self.qwen_base_url and self.qwen_model_id:
                self.qwen_type = True
            elif self.minmax_api_key and self.minmax_base_url and (self.minmax_model_id or self.minmax_model_name):
                self.minmax_type = True

        # 当前启用的文本模型：优先 QWEN_TYPE，其次 MINMAX_TYPE
        if self.qwen_type and self.qwen_api_key and self.qwen_base_url and self.qwen_model_id:
            self._active_text = "qwen"
        elif self.minmax_type and self.minmax_api_key and self.minmax_base_url and (self.minmax_model_id or self.minmax_model_name):
            self._active_text = "minmax"
        else:
            self._active_text = None

        if self._active_text is None:
            raise ValueError(
                "未找到可用的文本模型配置。请将 QWEN_TYPE 或 MINMAX_TYPE 设为 True，并配置对应的 QWEN_* 或 MINMAX_* 环境变量。"
            )

    # 兼容旧调用：api_key/base_url/model_id/model_name 返回当前启用模型的配置
    @property
    def api_key(self) -> str:
        return self.qwen_api_key if self._active_text == "qwen" else self.minmax_api_key

    @property
    def base_url(self) -> str:
        return self.qwen_base_url if self._active_text == "qwen" else self.minmax_base_url

    @property
    def model_id(self) -> str:
        return (self.qwen_model_id if self._active_text == "qwen" else (self.minmax_model_id or self.minmax_model_name or ""))

    @property
    def model_name(self) -> str:
        return (self.qwen_model_name or self.qwen_model_id) if self._active_text == "qwen" else (self.minmax_model_name or self.minmax_model_id or "MiniMax-M2.5")

    def get_chat_tongyi(self, temperature: float = 0.3, streaming: bool = False, enable_thinking: bool = False):
        """
        创建对话模型实例（根据 QWEN_TYPE / MINMAX_TYPE 选择 Qwen 或 MiniMax）。

        Args:
            temperature: 温度参数
            streaming: 是否启用流式输出
            enable_thinking: 是否启用思考模式（仅 Qwen 支持）

        Returns:
            ChatTongyi 或 ChatOpenAI 实例
        """
        if self._active_text == "qwen":
            if not self.qwen_api_key or not self.qwen_base_url or not self.qwen_model_id:
                raise ValueError("QWEN_TYPE=True 但 QWEN_API_KEY / QWEN_BASE_URL / QWEN_MODEL_ID 未在 .env 中配置完整")
            llm = ChatTongyi(
                temperature=temperature,
                model=self.qwen_model_id,
                api_key=self.qwen_api_key,
                base_url=self.qwen_base_url,
                streaming=streaming,
            )
            if not enable_thinking:
                llm = llm.bind(enable_thinking=False)
            return llm

        if self._active_text == "minmax":
            if not self.minmax_api_key or not self.minmax_base_url:
                raise ValueError("MINMAX_TYPE=True 但 MINMAX_API_KEY / MINMAX_BASE_URL 未在 .env 中配置完整")
            model = self.minmax_model_id or self.minmax_model_name or "MiniMax-M2.5"
            return ChatOpenAI(
                temperature=temperature,
                model=model,
                api_key=self.minmax_api_key,
                base_url=self.minmax_base_url,
                streaming=streaming,
            )

        raise ValueError("未找到可用的文本模型配置（QWEN_TYPE 或 MINMAX_TYPE 至少一个为 True 且配置完整）")

    def get_chat_openai(self, temperature: float = 0.7, streaming: bool = False):
        """
        创建 ChatOpenAI 兼容实例（与 get_chat_tongyi 使用同一套启用的文本模型，但统一为 OpenAI 接口）。

        Args:
            temperature: 温度参数
            streaming: 是否启用流式输出

        Returns:
            ChatOpenAI 实例
        """
        if self._active_text == "qwen":
            if not self.qwen_api_key or not self.qwen_base_url:
                raise ValueError("QWEN 配置不完整")
            model = self.qwen_model_id or self.qwen_model_name
            return ChatOpenAI(
                temperature=temperature,
                model=model,
                api_key=self.qwen_api_key,
                base_url=self.qwen_base_url,
                streaming=streaming,
            )
        if self._active_text == "minmax":
            if not self.minmax_api_key or not self.minmax_base_url:
                raise ValueError("MINMAX 配置不完整")
            model = self.minmax_model_id or self.minmax_model_name or "MiniMax-M2.5"
            return ChatOpenAI(
                temperature=temperature,
                model=model,
                api_key=self.minmax_api_key,
                base_url=self.minmax_base_url,
                streaming=streaming,
            )
        raise ValueError("未找到可用的文本模型配置")

    def get_multimodal_llm(self, temperature: float = 0.3, streaming: bool = False):
        """
        创建多模态模型实例。仅当 MULTIMODAL_TYPE=True 且 MULTIMODAL_* 配置完整时返回。

        Args:
            temperature: 温度参数
            streaming: 是否启用流式输出

        Returns:
            ChatOpenAI 实例（多模态模型）
        """
        if not self.multimodal_type:
            raise ValueError("MULTIMODAL_TYPE 未设置为 True，多模态模型未启用。请在 .env 中设置 MULTIMODAL_TYPE=True。")
        if not self.multimodal_api_key:
            raise ValueError("MULTIMODAL_API_KEY not found in .env file")
        if not self.multimodal_base_url:
            raise ValueError("MULTIMODAL_BASE_URL not found in .env file")

        model = self.multimodal_model_id or self.multimodal_model_name
        if not model:
            raise ValueError("MULTIMODAL_MODEL_ID 或 MULTIMODAL_MODEL_NAME not found in .env file")

        return ChatOpenAI(
            temperature=temperature,
            model=model,
            api_key=self.multimodal_api_key,
            base_url=self.multimodal_base_url,
            streaming=streaming,
        )


# 全局单例
_llm_config: Optional[LLMConfig] = None


def get_llm_config() -> LLMConfig:
    """获取LLM配置单例"""
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig()
    return _llm_config


def get_chat_tongyi(temperature: float = 0.3, streaming: bool = False, enable_thinking: bool = False):
    """便捷函数：根据 QWEN_TYPE / MINMAX_TYPE 获取当前启用的对话模型"""
    return get_llm_config().get_chat_tongyi(temperature, streaming, enable_thinking)


def get_chat_openai(temperature: float = 0.7, streaming: bool = False):
    """便捷函数：获取 OpenAI 兼容接口的对话模型（与 get_chat_tongyi 同源）"""
    return get_llm_config().get_chat_openai(temperature, streaming)


def get_multimodal_llm(temperature: float = 0.3, streaming: bool = False):
    """便捷函数：仅当 MULTIMODAL_TYPE=True 时返回多模态模型"""
    return get_llm_config().get_multimodal_llm(temperature, streaming)
