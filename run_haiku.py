import asyncio
from agent.core.omega_brain_v2 import OmegaBrainV2

async def main():
    brain = OmegaBrainV2(sandbox_root="./sandbox")

    prompt = ("Write a single haiku about databases. Respond with ONLY the "
              "haiku itself, three lines, no title, no explanation, no quotes.")
    haiku_text = await brain.llm.complete(prompt, temperature=0.7, max_tokens=60)
    haiku_text = haiku_text.strip()

    print("Generated haiku:")
    print(haiku_text)

    write = await brain.actions.write_file("haiku.txt", haiku_text + "\n")
    print(write)

asyncio.run(main())
