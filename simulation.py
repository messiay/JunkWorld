import os
import csv
import time
import random
import config
from world import World
from agent import Agent
from llm_client import LLMClient

class Simulation:
    def __init__(self, mode="llm", model_name=None):
        self.mode = mode  # "llm" or "mock"
        self.world = World()
        self.generation = 1
        self.agent = Agent(self.generation, self.world.spawn_pos)
        self.llm_client = LLMClient(model_name=model_name)

        self.global_tick = 0
        self.node_spawn_ticks = {}  # (x, y) -> global_tick (for age-based color fading)

        # Track spawn ticks for initial charge nodes
        for node in self.world.charge_nodes:
            self.node_spawn_ticks[node] = 0

        # Create log directory and files
        os.makedirs(config.LOG_DIR, exist_ok=True)
        self.init_csv_files()

        # Last action details (for GUI HUD display)
        self.last_action_info = {
            "action": "None",
            "description": "Simulation initialized.",
            "latency": 0.0,
            "tokens": 0
        }
        self.last_action_result = "None (simulation just started)."

        # Write start marker to JSONL file
        if self.mode != "mock":
            import json
            try:
                marker_entry = {
                    "marker": f"=== START OF SIMULATION RUN WITH MODEL: {self.llm_client.model_name} ===",
                    "timestamp": time.time()
                }
                with open(config.LLM_LOG_FILE, "a", encoding="utf-8") as lf:
                    lf.write(json.dumps(marker_entry) + "\n")
            except Exception:
                pass

        # Generational metrics trackers
        self.gen_charge_gained = 0.0
        self.gen_charge_spent = 0.0
        self.gen_signs_written = 0
        self.gen_vaults_attempted = 0
        self.gen_vaults_solved = 0

    def init_csv_files(self):
        """Creates CSV log files with headers if they do not exist, or migrates them to include 'model' and 'temperature' columns."""
        # 1. Tick log migration/init
        if os.path.exists(config.TICK_LOG_FILE):
            with open(config.TICK_LOG_FILE, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
            
            # Case A: Totally old header without 'model'
            if header and header[0] != "model":
                print("Migrating ticks.csv to include 'model' and 'temperature' columns...")
                with open(config.TICK_LOG_FILE, mode="r", newline="", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
                new_rows = [["model", "temperature"] + rows[0]]
                for r in rows[1:]:
                    new_rows.append(["qwen2.5:1.5b", 0.2] + r)
                with open(config.TICK_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(new_rows)
            # Case B: Header has 'model' but does not have 'temperature'
            elif header and "temperature" not in header:
                print("Migrating ticks.csv to include 'temperature' column...")
                with open(config.TICK_LOG_FILE, mode="r", newline="", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
                new_rows = [[rows[0][0], "temperature"] + rows[0][1:]]
                for r in rows[1:]:
                    new_rows.append([r[0], 0.2] + r[1:])
                with open(config.TICK_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(new_rows)
        else:
            with open(config.TICK_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "model",
                    "temperature",
                    "generation", 
                    "tick", 
                    "charge", 
                    "position", 
                    "action_taken", 
                    "tokens_used", 
                    "signs_read_count", 
                    "signs_written_count"
                ])

        # 2. Generation log migration/init
        if os.path.exists(config.GEN_LOG_FILE):
            with open(config.GEN_LOG_FILE, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
            
            # Case A: Totally old header
            if header and header[0] != "model":
                print("Migrating generations.csv to include 'model' and 'temperature' columns...")
                with open(config.GEN_LOG_FILE, mode="r", newline="", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
                new_rows = [["model", "temperature"] + rows[0]]
                for r in rows[1:]:
                    new_rows.append(["qwen2.5:1.5b", 0.2] + r)
                with open(config.GEN_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(new_rows)
            # Case B: Has 'model' but not 'temperature'
            elif header and "temperature" not in header:
                print("Migrating generations.csv to include 'temperature' column...")
                with open(config.GEN_LOG_FILE, mode="r", newline="", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
                new_rows = [[rows[0][0], "temperature"] + rows[0][1:]]
                for r in rows[1:]:
                    new_rows.append([r[0], 0.2] + r[1:])
                with open(config.GEN_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(new_rows)
        else:
            with open(config.GEN_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "model",
                    "temperature",
                    "generation",
                    "ticks_survived",
                    "charge_efficiency",
                    "signs_written",
                    "vaults_attempted",
                    "vaults_solved"
                ])
            with open(config.GEN_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "model",
                    "generation",
                    "ticks_survived",
                    "charge_efficiency",
                    "signs_written",
                    "vaults_attempted",
                    "vaults_solved"
                ])

    def step(self, mock_action_name=None, mock_action_args=None):
        """
        Executes one simulation step (1 tick).
        In mock mode, the action is passed in from Pygame keyboard events.
        In llm mode, the action is requested from the LLM client.
        """
        if not self.agent.alive:
            return

        self.global_tick += 1
        
        # 1. Get perception data (7x7 window centered on agent)
        perception = self.world.get_perception_data(self.agent.position)
        
        # Count visible signs in the 7x7 vision
        signs_read_count = sum(1 for detail in perception["details"] if "Sign at" in detail)

        action_name = "rest"
        action_args = {}
        reasoning = ""
        latency = 0.0
        tokens_used = 0

        # 2. Determine Action based on Mode
        if self.mode == "mock":
            if mock_action_name:
                action_name = mock_action_name
                action_args = mock_action_args
                reasoning = "Manual keyboard input."
            else:
                # If no key was pressed, we do not advance the sim tick in mock mode
                # to prevent rapid tick decay while idle
                self.global_tick -= 1
                return
        else:
            # Calculate standing_on
            if self.agent.position in self.world.charge_nodes:
                standing_on = "Charge Node"
            elif self.agent.position in self.world.vault_locations:
                standing_on = "Vault (Solved)" if self.agent.position in self.world.solved_vaults else "Vault (Unsolved)"
            else:
                standing_on = "Nothing"

            # LLM Mode
            start_time = time.time()
            action_name, action_args, reasoning, tokens_used, error_occurred = self.llm_client.decide_action(
                generation=self.agent.generation,
                ticks_survived=self.agent.ticks_survived,
                charge=self.agent.charge,
                position=self.agent.position,
                perception=perception,
                last_result=self.last_action_result,
                standing_on=standing_on
            )
            latency = time.time() - start_time

            # Apply Cognitive Tax immediately to agent's charge
            flat_tax = config.LLM_THINK_TAX_FLAT
            scaled_tax = config.LLM_THINK_TAX_TOKEN_SCALE * tokens_used
            total_cognitive_tax = flat_tax + scaled_tax
            
            self.agent.charge -= total_cognitive_tax
            self.gen_charge_spent += total_cognitive_tax

            # Check if cognitive tax killed the agent
            if self.agent.charge <= 0:
                self.agent.alive = False
                reasoning += f" (Died from cognitive tax of {total_cognitive_tax:.2f} charge)"
                action_name = "rest"

        # 3. Apply Action (if agent is still alive)
        log_msg = ""
        signs_written_this_tick = 0

        if self.agent.alive:
            # Track charge before action to compute details
            charge_before = self.agent.charge
            
            # Apply action
            log_msg = self.agent.apply_action(action_name, action_args, self.world)
            
            # Charge spent on metabolic tax is always deducted
            self.gen_charge_spent += config.METABOLIC_TAX

            # Deduct action-specific costs
            action_lower = action_name.lower().strip()
            if action_lower == "move":
                self.gen_charge_spent += config.MOVE_COST
            elif action_lower == "attempt_vault":
                self.gen_charge_spent += config.VAULT_ATTEMPT_COST
                self.gen_vaults_attempted += 1
            elif action_lower == "write_sign":
                self.gen_charge_spent += config.WRITE_SIGN_COST
                self.gen_signs_written += 1
                signs_written_this_tick = 1

            # Accumulate charge gains
            charge_after = self.agent.charge
            net_change = charge_after - charge_before
            
            # Calculate gains from forage and vault success
            if action_lower == "forage" and net_change > 0:
                self.gen_charge_gained += net_change + config.METABOLIC_TAX
            elif action_lower == "attempt_vault" and net_change > 0:
                self.gen_charge_gained += net_change + config.METABOLIC_TAX + config.VAULT_ATTEMPT_COST
                self.gen_vaults_solved += 1

        else:
            log_msg = "Agent died due to cognitive tax."

        # Save previous action result for next tick observation
        self.last_action_result = log_msg

        # Update HUD state
        self.last_action_info = {
            "action": action_name,
            "description": f"{log_msg} | Reasoning: {reasoning}",
            "latency": latency,
            "tokens": tokens_used
        }

        # 4. Tick World Regeneration
        # Store nodes before regen to find newly spawned nodes
        nodes_before = set(self.world.charge_nodes)
        self.world.tick_regen(self.global_tick)
        newly_spawned = self.world.charge_nodes - nodes_before
        for node in newly_spawned:
            self.node_spawn_ticks[node] = self.global_tick

        # Clean up node_spawn_ticks for deleted charge nodes
        for node in list(self.node_spawn_ticks.keys()):
            if node not in self.world.charge_nodes:
                del self.node_spawn_ticks[node]

        # 5. Log tick details to ticks.csv
        self.log_tick_to_csv(tokens_used, signs_read_count, signs_written_this_tick)

        # 6. Check for death and handle transition
        if not self.agent.alive:
            self.handle_agent_death()

    def log_tick_to_csv(self, tokens_used, signs_read_count, signs_written_this_tick):
        """Appends a row to ticks.csv."""
        model_col = "mock" if self.mode == "mock" else self.llm_client.model_name
        temp_col = 0.0 if self.mode == "mock" else config.LLM_TEMPERATURE
        with open(config.TICK_LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                model_col,
                temp_col,
                self.agent.generation,
                self.agent.ticks_survived,
                round(self.agent.charge, 2),
                f"({self.agent.position[0]};{self.agent.position[1]})",
                self.last_action_info["action"],
                tokens_used,
                signs_read_count,
                signs_written_this_tick
            ])

    def handle_agent_death(self):
        """Saves generation metrics and initializes a new agent generation."""
        # Calculate charge efficiency
        efficiency = 0.0
        if self.gen_charge_spent > 0.0:
            efficiency = self.gen_charge_gained / self.gen_charge_spent

        model_col = "mock" if self.mode == "mock" else self.llm_client.model_name
        temp_col = 0.0 if self.mode == "mock" else config.LLM_TEMPERATURE
        # Write to generations.csv
        with open(config.GEN_LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                model_col,
                temp_col,
                self.agent.generation,
                self.agent.ticks_survived,
                round(efficiency, 3),
                self.gen_signs_written,
                self.gen_vaults_attempted,
                self.gen_vaults_solved
            ])

        print(f"=== Generation {self.agent.generation} completed. Ticks survived: {self.agent.ticks_survived} ===")

        # Transition to next generation
        self.generation += 1
        self.world.reset_for_new_generation()
        self.llm_client.reset_history()
        self.last_action_result = "None (simulation just started)."

        # Create new agent at spawn point
        self.agent = Agent(self.generation, self.world.spawn_pos)

        # Reset trackers
        self.gen_charge_gained = 0.0
        self.gen_charge_spent = 0.0
        self.gen_signs_written = 0
        self.gen_vaults_attempted = 0
        self.gen_vaults_solved = 0
