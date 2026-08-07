import asyncio
from agent.core.omega_brain_v2 import OmegaBrainV2

async def main():
    brain = OmegaBrainV2(sandbox_root="./sandbox")  # uses get_default_client() -> real Groq
    result = await brain.process_task("Write a haiku about databases to haiku.txt", {})
    print(result["reasoning"]["steps"])
    write = await brain.actions.write_file("haiku.txt", result["reasoning"]["steps"])
    print(write)

asyncio.run(main())
