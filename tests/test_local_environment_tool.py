import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.agent_loop import TOOLS
from agent.core.action_engine import Action, ActionExecutor, ActionNode, ActionValidator, SideEffectAnalyzer


def main():
    names = {item["function"]["name"] for item in TOOLS}
    assert "inspect_local_environment" in names
    assert "scan_iot_devices" in names
    assert os.path.isdir(ActionExecutor.OMEGA_WORKSPACE)

    executor = ActionExecutor(ActionValidator(), SideEffectAnalyzer())
    for name in ("inspect_local_environment", "scan_iot_devices"):
        ok, result = asyncio.run(executor._dispatch_action(ActionNode(Action(name=name), {})))
        assert ok is True
        assert result["inspection_scope"] == "local_only"
        assert result["network_probe_performed"] is False
        assert "No remote or IoT device scan was performed." in result["note"]

    print("LOCAL_ENVIRONMENT_TOOL_REGRESSION_OK")


if __name__ == "__main__":
    main()
