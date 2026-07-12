import argparse
import sys
import pygame
import config
from simulation import Simulation
from gui import GUI

def main():
    parser = argparse.ArgumentParser(description="Junk World Simulation Platform")
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["llm", "mock"], 
        default="llm",
        help="Simulation run mode: 'llm' (automatic AI agent) or 'mock' (manual keyboard controls)"
    )
    parser.add_argument(
        "--model", 
        type=str, 
        default=None,
        help="Ollama model name (overrides config.DEFAULT_MODEL)"
    )
    parser.add_argument(
        "--api", 
        type=str, 
        default=None,
        help="Ollama API base URL (overrides config.OLLAMA_API_URL)"
    )
    args = parser.parse_args()

    # Create Pygame GUI interface
    gui = GUI()

    # Initialize Simulation engine
    sim = Simulation(mode=args.mode, model_name=args.model)
    if args.api:
        sim.llm_client.api_url = args.api

    print(f"===========================================================")
    print(f"Junk World Simulator started in {args.mode.upper()} mode.")
    if args.mode == "mock":
        print("KEYBOARD CONTROLS:")
        print("  - Arrow Keys / WASD: Move Agent")
        print("  - F: Forage (must be standing on green charge node 'G')")
        print("  - V: Attempt Vault (must be standing on yellow vault outline 'V')")
        print("  - T: Write Sign (writes mock text)")
        print("  - R: Rest (explicit no-op)")
        print("  - ESC / Close window: Quit")
    else:
        print(f"  Target LLM Model: {sim.llm_client.model_name}")
        print(f"  Target LLM API: {sim.llm_client.api_url}")
    print(f"===========================================================")

    running = True
    while running:
        # 1. Process Pygame events (window closure, mouse movement, keyboard controls in mock mode)
        action_name, action_args, should_quit = gui.handle_events(mock_mode=(args.mode == "mock"))
        if should_quit:
            running = False
            break

        # 2. Advance Simulation step
        if args.mode == "mock":
            # In mock mode, only execute simulation step if user triggers an action key
            if action_name:
                sim.step(action_name, action_args)
        else:
            # In LLM mode, step automatically
            sim.step()

        # 3. Draw updated simulation screen
        gui.draw(
            world=sim.world,
            agent=sim.agent,
            last_action_info=sim.last_action_info,
            global_tick=sim.global_tick,
            node_spawn_ticks=sim.node_spawn_ticks
        )

    pygame.quit()

if __name__ == "__main__":
    main()
