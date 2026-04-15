import logging
from typing import Any, List, Optional, Union, Dict
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from src.utils.quota_shield import quota_shield, VLIQuotaExhaustedError

logger = logging.getLogger(__name__)

class QuotaProtectedLLM:
    """
    A wrapper for LangChain ChatModels that intercepts calls to enforce 
    TPM/RPM quotas via QuotaShield.
    """
    def __init__(self, llm: BaseChatModel, tier: str):
        self.llm = llm
        self.tier = tier

    def __getattr__(self, name):
        """Delegate everything else to the internal LLM."""
        return getattr(self.llm, name)

    async def ainvoke(
        self,
        input: Union[str, List[BaseMessage]],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        # 1. Estimate tokens (Roughly 4 chars per token fallback)
        input_str = str(input)
        estimated_input_tokens = len(input_str) // 4
        # Multiplier to account for complexity (System prompt, tools, etc.)
        total_estimate = estimated_input_tokens + 1000 # 1000 buffer for system/output
        
        # 2. Check Shield
        if not quota_shield.allow_request(self.tier, total_estimate):
            fail_msg = f"[QUOTA_SHIELD] Request blocked for tier '{self.tier}'. RPM/TPM limit reached."
            logger.error(fail_msg)
            raise VLIQuotaExhaustedError(fail_msg)

        # 3. Execute with telemetry
        try:
            result = await self.llm.ainvoke(input, config, **kwargs)
            
            # 4. Optional: Extract usage metadata and update shield more accurately
            # (In this simple version, we let the rotation handle it, 
            # but we could call quota_shield.update_usage here).
            
            return result
        except Exception as e:
            # Re-raise. If it's a 429 from the actual provider, that reinforces the shield.
            raise e

    def invoke(
        self,
        input: Union[str, List[BaseMessage]],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        # Sync version (same logic)
        input_str = str(input)
        total_estimate = (len(input_str) // 4) + 1000
        
        if not quota_shield.allow_request(self.tier, total_estimate):
             raise VLIQuotaExhaustedError(f"Quota exhausted for {self.tier}")
             
        return self.llm.invoke(input, config, **kwargs)

    # Note: For full coverage, especially when used in LangGraph, 
    # we should also ensure stream() and astream() are covered if used.
    # For now, ainvoke and invoke cover 90% of VLI usage.
