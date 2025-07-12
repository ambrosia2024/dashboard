# api_test/scio/utils.py

def print_model_info(models, title):
    print(f"\n{'='*40}\n{title}\n{'='*40}")
    for i, model in enumerate(models, start=1):
        print(f"\nModel {i}:")
        print(f"  ID               : {model.get('id')}")
        print(f"  Name             : {model.get('name')}")
        print(f"  CPU Cores        : {model.get('cpu_cores_required')}")
        print(f"  GPU Count        : {model.get('gpu_count_required')}")
        print(f"  GPU Memory (GB)  : {model.get('gpu_memory_gb_required')}")
        print(f"  RAM Required (GB): {model.get('ram_gb_required')}")
        print(f"  Image Tag        : {model.get('image_tag')}")
        print(f"  FSKX URL         : {model.get('url')}")
