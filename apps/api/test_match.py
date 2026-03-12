import sys
sys.path.insert(0, './app')
from core.model_registry import get_model_by_name

print("gpt image 1.5", get_model_by_name("gpt image 1.5").get("air_id") if get_model_by_name("gpt image 1.5") else None)
print("flux-2-dev", get_model_by_name("flux-2-dev").get("air_id") if get_model_by_name("flux-2-dev") else None)
print("sora 2 pro", get_model_by_name("sora 2 pro").get("air_id") if get_model_by_name("sora 2 pro") else None)
