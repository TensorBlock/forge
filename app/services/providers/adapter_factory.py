import os
from typing import Any

from .anthropic_adapter import AnthropicAdapter
from .azure_adapter import AzureAdapter
from .base import ProviderAdapter
from .bedrock_adapter import BedrockAdapter
from .cohere_adapter import CohereAdapter
from .fireworks_adapter import FireworksAdapter
from .google_adapter import GoogleAdapter
from .mock_adapter import MockAdapter
from .openai_adapter import OpenAIAdapter
from .perplexity_adapter import PerplexityAdapter
from .tensorblock_adapter import TensorblockAdapter
from .zhipu_adapter import ZhipuAdapter
from .vertex_adapter import VertexAdapter
from .alibaba_adapter import AlibabaAdapter
from .zai_adapter import ZAIAdapter


class ProviderAdapterFactory:
    """Factory for creating provider adapters"""

    _adapters: dict[str, type[ProviderAdapter]] = {
        "tensorblock": {
            "base_url": os.getenv("TENSORBLOCK_BASE_URL"),
            "adapter": TensorblockAdapter,
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "adapter": OpenAIAdapter,
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "adapter": AnthropicAdapter,
        },
        "gemini": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "adapter": GoogleAdapter,
        },
        "xai": {
            "base_url": "https://api.x.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "fireworks": {
            "base_url": "https://api.fireworks.ai/inference/v1",
            "adapter": FireworksAdapter,
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "adapter": OpenAIAdapter,
        },
        "together": {
            "base_url": "https://api.together.xyz/v1",
            "adapter": OpenAIAdapter,
        },
        "nebius": {
            "base_url": "https://api.studio.nebius.com/v1",
            "adapter": OpenAIAdapter,
        },
        "novita": {
            "base_url": "https://api.novita.ai/v3/openai",
            "adapter": OpenAIAdapter,
        },
        "nscale": {
            "base_url": "https://inference.api.nscale.com/v1",
            "adapter": OpenAIAdapter,
        },
        "hyperbolic": {
            "base_url": "https://api.hyperbolic.xyz/v1",
            "adapter": OpenAIAdapter,
        },
        "deepinfra": {
            "base_url": "https://api.deepinfra.com/v1/openai",
            "adapter": OpenAIAdapter,
        },
        "nvidia": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "adapter": OpenAIAdapter,
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "adapter": OpenAIAdapter,
        },
        "perplexity": {
            "base_url": "https://api.perplexity.ai",
            "adapter": PerplexityAdapter,
        },
        "maritaca": {
            "base_url": "https://chat.maritaca.ai/api",
            "adapter": OpenAIAdapter,
        },
        "featherless.ai": {
            "base_url": "https://api.featherless.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "alibaba": {
            "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            "adapter": AlibabaAdapter,
        },
        "cerebras": {
            "base_url": "https://api.cerebras.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "enfer": {
            "base_url": "https://api.enfer.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "inference.net": {
            "base_url": "https://api.inference.net/v1",
            "adapter": OpenAIAdapter,
        },
        "kluster.ai": {
            "base_url": "https://api.kluster.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "lambda": {
            "base_url": "https://api.lambda.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "mancer": {
            "base_url": "https://neuro.mancer.tech/oai/v1",
            "adapter": OpenAIAdapter,
        },
        "redpill.ai": {
            "base_url": "https://api.redpill.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "parasail": {
            "base_url": "https://api.parasail.io/v1",
            "adapter": OpenAIAdapter,
        },
        "nineteen.ai": {
            "base_url": "https://api.nineteen.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "targon": {
            "base_url": "https://api.targon.com/v1",
            "adapter": OpenAIAdapter,
        },
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "adapter": OpenAIAdapter,
        },
        "sambanova": {
            "base_url": "https://api.sambanova.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "cohere": {
            "base_url": "https://api.cohere.com",
            "adapter": CohereAdapter,
        },
        "mistral": {
            "base_url": "https://api.mistral.ai/v1",
            "adapter": OpenAIAdapter,
        },
        "siliconflow": {
            "base_url": "https://api.siliconflow.cn/v1",
            "adapter": OpenAIAdapter,
        },
        "moonshot": {
            "base_url": "https://api.moonshot.cn/v1",
            "adapter": OpenAIAdapter,
        },
        "hunyuan": {
            "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
            "adapter": OpenAIAdapter,
        },
        "baichuan": {
            "base_url": "https://api.baichuan-ai.com/v1",
            "adapter": OpenAIAdapter,
        },
        "stepfun": {
            "base_url": "https://api.stepfun.com/v1",
            "adapter": OpenAIAdapter,
        },
        "01": {
            "base_url": "https://api.lingyiwanwu.com/v1",
            "adapter": OpenAIAdapter,
        },
        "zhipu": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "adapter": ZhipuAdapter,
        },
        "z.ai": {
            "base_url": "https://api.z.ai/api/paas/v4",
            "adapter": ZAIAdapter,
        },
        "azure": {
            "adapter": AzureAdapter,
        },
        "bedrock": {
            "adapter": BedrockAdapter,
        },
        "vertex": {
            "adapter": VertexAdapter,
        },
        "customized": {
            "adapter": OpenAIAdapter,
        },
        "mock": {
            "adapter": MockAdapter,
        },
    }

    @classmethod
    def get_adapter(
        cls,
        provider_name: str,
        base_url: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> ProviderAdapter:
        """Get an adapter for the given provider"""
        normalized_provider_name = provider_name.lower()  # Normalize to lowercase

        # Use normalized_provider_name for lookup
        adapter_info = cls._adapters.get(
            normalized_provider_name, cls._adapters["customized"]
        )
        adapter_class = adapter_info["adapter"]
        effective_base_url = base_url or adapter_info.get("base_url")

        # Pass the normalized_provider_name to the adapter constructor for consistency
        return adapter_class(
            normalized_provider_name, effective_base_url, config=config
        )

    @classmethod
    def get_all_adapters(cls) -> dict[str, dict[str, Any]]:
        """Get all available adapters"""
        return cls._adapters.copy()

    @classmethod
    def get_adapter_cls(cls, provider_name: str) -> type[ProviderAdapter]:
        """Get the adapter class for the given provider"""
        normalized_provider_name = provider_name.lower()
        return cls._adapters.get(normalized_provider_name, {}).get(
            "adapter", OpenAIAdapter
        )
