from dataclasses import dataclass


@dataclass(frozen=True)
class FeedbackServiceConstants:
    FEEDBACK_EXTRACTORS_CONFIG_NAME = "agent_feedback_configs"
    # ===============================
    # prompt ids
    # ===============================
    RAW_FEEDBACK_SHOULD_GENERATE_PROMPT_ID = "raw_feedback_should_generate"
    RAW_FEEDBACK_EXTRACTION_CONTEXT_PROMPT_ID = "raw_feedback_extraction_context"
    RAW_FEEDBACK_EXTRACTION_PROMPT_ID = "raw_feedback_extraction_main"
    FEEDBACK_GENERATION_PROMPT_ID = "feedback_generation"

    # ===============================
    # agent success evaluation prompt ids
    # ===============================
    AGENT_SUCCESS_EVALUATION_SHOULD_EVALUATE_PROMPT_ID = (
        "agent_success_evaluation_should_evaluate"
    )
    AGENT_SUCCESS_EVALUATION_PROMPT_ID = "agent_success_evaluation"
