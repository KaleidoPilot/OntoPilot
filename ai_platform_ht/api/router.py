from fastapi import APIRouter
from pathlib import Path
import importlib.util
import sys

router = APIRouter()

# Directory where endpoint modules are located
endpoints_dir = Path(__file__).resolve().parent / "endpoints"

if endpoints_dir.exists():
    # Iterate over all python files in the endpoints directory and subdirectories
    # 记录已经加载过的模块名称，避免 .py 和 .pyc 重复加载同一个路由
    loaded_modules = set()
    
    # 支持 .py 源码以及编译后的 .pyc 文件
    for ext in ("*.py", "*.pyc"):
        for file_path in endpoints_dir.rglob(ext):
            # Skip __init__.py(c) and non-python files
            if file_path.name in ("__init__.py", "__init__.pyc"):
                continue
            
            # 仅加载各模块 api 目录下的路由文件（或者根目录下的路由文件如 test.py）
            # 忽略 modular, sql 等目录，避免无关文件被当作路由加载
            if len(file_path.parts) > len(endpoints_dir.parts) + 1:
                parent_dir_name = file_path.parent.name
                if parent_dir_name != "api":
                    continue

            try:
                # Create a unique module name based on relative path to avoid conflicts
                rel_path = file_path.relative_to(endpoints_dir)
                
                # 对于 .pyc 文件，它可能在 __pycache__ 目录下，我们需要处理这种特殊路径
                if "__pycache__" in rel_path.parts:
                    continue # 忽略直接扫描到的 __pycache__ 目录里的东西，防止重复或路径错乱
                    
                # 统一剥离后缀 (.py 或 .pyc) 来生成模块名
                module_suffix = str(rel_path.with_suffix("")).replace("\\", ".").replace("/", ".")
                module_name = f"api.endpoints.{module_suffix}"
                
                # 防止同一个路由文件因为同时存在 .py 和 .pyc 而被加载两次
                if module_name in loaded_modules:
                    continue
                loaded_modules.add(module_name)

                # 强制每次重新加载，避免缓存导致改名后报错
                if module_name in sys.modules:
                    del sys.modules[module_name]

                # Dynamically load the module
                # importlib 可以自动识别 .py 和 .pyc
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    # Check if the module has a 'router' attribute that is an APIRouter
                    if hasattr(module, "router") and isinstance(module.router, APIRouter):
                        # 构建更简洁的前缀，例如 csgl/api/csglApi -> /csgl
                        module_parts = list(rel_path.parts)
                        if len(module_parts) >= 3 and module_parts[1] == "api":
                            prefix_name = module_parts[0]
                        else:
                            # 确保从 .pyc 或 .py 获取到的 stem 是纯名字
                            prefix_name = rel_path.with_suffix("").name
                            
                        prefix = f"/{prefix_name}"
                        
                        router.include_router(module.router, prefix=prefix, tags=[prefix_name])
                        print(f"Loaded router from {rel_path} with prefix {prefix}")
            except Exception as e:
                print(f"Failed to load router from {file_path.relative_to(endpoints_dir)}: {e}")
else:
    print(f"Endpoints directory not found: {endpoints_dir}")
