import os
import sys
import asyncio
import time
import logging
import signal
from typing import Dict, Any

# Configure structured formatting for OMEGA ASI Console output
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("OmegaMain")

# Ensure correct app module indexing paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import Core Architectural Blocks
from agent.core.omega_brain_v2 import OmegaBrainV2
from agent.core.perception import MultiModalPerception, RealTimeMonitor
from agent.core.action_engine import ActionPlanner, ActionExecutor, ActionValidator, SideEffectAnalyzer, Action
from agent.core.self_engineer import CodeAnalyzer, PerformanceProfiler, ImprovementProposer, SafeDeployer, TestRunner, GitIntegration
from agent.oracle.grading_system import OracleGrader, GradeHistory, BenchmarkSuite, LeaderboardManager
from agent.oracle.grading_patch import evaluate_task_output_real
OracleGrader.evaluate_task_output_real = evaluate_task_output_real

class OmegaAgentSystem:
    """
    Unified application container orchestration.
    Coordinates loop updates, metrics watching, action triggers, and self-modification.
    """
    def __init__(self):
        self.brain = OmegaBrainV2(sandbox_root=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../sandbox")))
        self.perception = MultiModalPerception()
        self.monitor = RealTimeMonitor(self.perception, polling_interval=1.0)
        
        # Action space configurations
        self.actions = [
            Action(name="read_file", preconditions={"file_exists": True}, effects={"file_read": True}, cost=1.0, target="agent/core/omega_brain.py"),
            Action(name="compile_code", preconditions={"file_read": True}, effects={"compiled": True}, cost=2.0, target="agent/core/omega_brain.py"),
            Action(name="deploy_canary", preconditions={"compiled": True}, effects={"canary_active": True}, cost=3.0)
        ]
        self.planner = ActionPlanner(self.actions)
        self.validator = ActionValidator()
        self.analyzer = SideEffectAnalyzer()
        self.executor = ActionExecutor(self.validator, self.analyzer)
        
        # Self engineering system setups
        self.code_analyzer = CodeAnalyzer(root_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        self.profiler = PerformanceProfiler()
        self.proposer = ImprovementProposer(self.code_analyzer)
        self.test_runner = TestRunner(root_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        self.deployer = SafeDeployer(root_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        self.git = GitIntegration(repo_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
        
        # Oracle configurations
        self.grader = OracleGrader()
        self.history = GradeHistory()
        self.benchmarks = BenchmarkSuite()
        self.leaderboard = LeaderboardManager()
        
        self.is_running = False

        # --- Real goal queue instead of one frozen task ---
        self.task_queue = [
            "Ensure system codebase is parsed and compiled.",
            "Review agent/core/action_engine.py for unused imports or dead code.",
            "Summarize the current state of agent/main.py in one sentence.",
        ]
        self._task_index = 0

    async def start(self):
        self.is_running = True
        logger.info("Initializing OMEGA AGENT ASI core components...")
        
        # Start background health telemetry monitors
        await self.monitor.start()
        
        # Warmup reasoning databases and memories
        try:
            await self.brain.memory.store("system_status", "ACTIVE", mem_type="semantic", importance=0.9)
        except (AttributeError, TypeError) as e:
            logger.warning(f"OmegaBrainV2 memory API differs — skipping legacy warmup call ({e}).")
        
        logger.info("System fully booted. Entering continuous operational loop.")
        await self._main_loop()

    async def stop(self):
        logger.info("Graceful shutdown initiated. Saving metrics...")
        self.is_running = False
        await self.monitor.stop()
        
        # Consolidate running memory states before quitting
        try:
            await self.brain.memory.consolidate_memories()
        except (AttributeError, TypeError):
            pass
        logger.info("OMEGA AGENT offline. State consolidated safely.")

    async def _main_loop(self):
        loop_counter = 0
        while self.is_running:
            loop_counter += 1
            logger.info(f"--- Operational Loop Cycle {loop_counter} ---")
            
            try:
                # 1. Run a sample scenario simulation to demonstrate integrated capabilities
                cycle_start = time.monotonic()
                world_state = await self.perception.ingest("structured", {
                    "file_exists": True,
                    "compiled": False,
                    "network_latency": getattr(self, "_last_cycle_ms", 0.0),
                    "system_load": os.getloadavg()[0]
                })
                
                # 2. Query brain for next runnable plan goals
                current_task = self.task_queue[self._task_index % len(self.task_queue)]
                self._task_index += 1
                task_resp = await self.brain.process_task(current_task, world_state.inputs)
                strategy = task_resp.get('reasoning', {}).get('solution_strategy',
                    task_resp.get('reasoning', {}).get('strategy', 'unknown'))
                logger.info(f"Brain reasoning strategy: {strategy}")
                
                # 3. Create execution plan
                start_state = {"file_exists": True, "compiled": False}
                goal_state = {"compiled": True}
                plan_nodes = self.planner.plan(start_state, goal_state)
                
                if plan_nodes:
                    # Execute
                    results = await self.executor.execute_plan(plan_nodes, start_state)
                    success_rate = sum(1 for r in results if r.success) / len(results) if results else 0.0
                    
                    # Log latencies to performance profiler
                    for r in results:
                        self.profiler.log_latency(r.action_name, r.execution_time)
                        
                    # 4. Trigger self-improvement checks if performance profile patterns are available
                    prof_data = self.profiler.get_profile_report()
                    proposal = await self.proposer.propose_optimization("agent/core/omega_brain.py", prof_data)
                    
                    if proposal and loop_counter == 1:
                        # In loop 1, we show a mock proposal deploy validation flow
                        deploy_ok = await self.deployer.deploy_with_canary(proposal, self.test_runner)
                        logger.info(f"Canary self-update success state: {deploy_ok}")
                        
                    # 5. Evaluate results against Oracle Grader rubrics
                    output_summary = "; ".join(
                        f"{r.action_name}: {'OK' if r.success else 'FAILED - ' + str(r.error)}"
                        for r in results
                    ) if results else "no actions executed"
                    grade = await self.grader.evaluate_task_output_real(
                        "Ensure system codebase is parsed and compiled.",
                        output_summary,
                        notes=f"Automatic scoring profile for step completion cycle {loop_counter}"
                    )
                    
                    self.history.record_grade(grade)
                    self.leaderboard.update_leaderboard(f"run_loop_{loop_counter}", grade)
                    
                self._last_cycle_ms = (time.monotonic() - cycle_start) * 1000
                # Safe rate limiter
                await asyncio.sleep(5.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in main operational flow: {e}", exc_info=True)
                await asyncio.sleep(2.0)


async def main():
    agent = OmegaAgentSystem()
    
    # Register OS signals for seamless container lifecycle shutdowns
    def handle_shutdown(sig, frame):
        logger.info(f"Received terminal OS signal: {sig}")
        asyncio.create_task(agent.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, handle_shutdown)
        except ValueError:
            pass # Skip if run inside secondary threads
            
    try:
        await agent.start()
    except Exception as e:
        logger.critical(f"Unhandled fatal runtime crash: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
