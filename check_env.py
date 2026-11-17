# check_env.py —— 检查虚拟环境与依赖是否安装成功
import sys

# 1. 打印 Python 版本和解释器路径
print("Python 版本：", sys.version)
print("解释器路径：", sys.executable)

# 2. 检查三个核心依赖是否可用
try:
    import fastapi
    import uvicorn
    import PySide6

    print("FastAPI 版本：", fastapi.__version__)
    print("Uvicorn 版本：", uvicorn.__version__)
    print("PySide6 版本：", PySide6.__version__)
    print("环境检查通过。")
except ImportError as e:
    print("依赖缺失：", e)
    print("请确认已激活 .venv，并重新执行 pip install -r requirements.txt")