"""自研 GitHub MCP Server 运行入口（独立可运行）。

运行方式:
  python mcp/run_github_server.py            # stdio，供 MCP client 连接
  mcp dev mcp/run_github_server.py           # MCP Inspector 可视化调试
  mcp install mcp/run_github_server.py       # 装进 Claude Desktop
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from opscopilot.tools.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    main()
