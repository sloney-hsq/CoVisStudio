from pathlib import Path
import os
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def load_settings(env_file=None):
    credential_file = Path(env_file) if env_file is not None else ROOT / '.env.local'
    local_values = dotenv_values(credential_file)
    values = {**os.environ, **local_values}
    key_values = local_values if any(name in local_values for name in ('QWEN_API_KEY', 'DASHSCOPE_API_KEY')) else os.environ
    return {
        'api_key': key_values.get('QWEN_API_KEY') or key_values.get('DASHSCOPE_API_KEY') or '',
        'credential_file': str(credential_file.resolve()),
        'text_model': values.get('QWEN_TEXT_MODEL', 'qwen3.8-omni-flash'),
        'realtime_model': values.get('QWEN_REALTIME_MODEL', 'qwen3.8-omni-flash-realtime'),
        'text_url': values.get('QWEN_TEXT_URL', 'https://llm-ynielphi7sx0d0wc.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions'),
        'realtime_url': values.get('QWEN_REALTIME_URL', 'wss://llm-ynielphi7sx0d0wc.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime'),
        'voice': values.get('QWEN_VOICE', 'Maia'),
        'data_dir': Path(values.get('OLIST_DATA_DIR', 'C:/VerbalVis/datasets/olist/data')),
        'trace_dir': ROOT / 'traces',
        # Diagnostic runs only; formal study windows stay at 60 s regardless.
        'voice_budget_seconds': int(values.get('COVIS_VOICE_BUDGET_SECONDS', '60')),
        'backchannel_hold': values.get('COVIS_BACKCHANNEL_HOLD', '1') != '0',
    }
