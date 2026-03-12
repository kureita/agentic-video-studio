import sys
import json
sys.path.insert(0, '.')
from app.core.model_registry import get_model_by_name

for m in ["gpt image 1.5", "flux-2-dev", "sora 2 pro", "gpt-image-1-5", "FLUX.2 [max]"]:
    model = get_model_by_name(m)
    print(f"{m} -> {model.get('air_id') if model else None}")
