import random
import config

class Agent:
    def __init__(self, generation: int, start_pos: tuple):
        self.generation = generation
        self.position = start_pos  # (x, y)
        self.charge = config.STARTING_CHARGE
        self.alive = True
        self.ticks_survived = 0
        self.inventory = {}  # Unused for single-agent scale as per spec

    def apply_action(self, action_name: str, action_args: dict, world) -> str:
        """
        Executes an action on the world and updates the agent's charge/position.
        Returns a log message string describing what happened.
        """
        if not self.alive:
            return "Agent is dead."

        # 1. Base metabolic tax is always deducted
        self.charge -= config.METABOLIC_TAX
        self.ticks_survived += 1
        log_msg = ""

        # Normalize action name to lowercase
        action = action_name.lower().strip()

        if action == "move":
            direction = action_args.get("direction", "").upper().strip()
            # Calculate coordinate offsets
            deltas = {
                "N": (0, -1),
                "S": (0, 1),
                "E": (1, 0),
                "W": (-1, 0),
                "NE": (1, -1),
                "NW": (-1, -1),
                "SE": (1, 1),
                "SW": (-1, 1)
            }

            if direction in deltas:
                dx, dy = deltas[direction]
                target_x = self.position[0] + dx
                target_y = self.position[1] + dy

                # Check bounds and wall collisions
                if (0 <= target_x < config.GRID_SIZE) and (0 <= target_y < config.GRID_SIZE):
                    target_biome = world.grid[target_y][target_x]
                    if target_biome != "WALL":
                        self.position = (target_x, target_y)
                        log_msg = f"Moved {direction} to {self.position}."
                    else:
                        log_msg = f"Failed to move {direction}: path blocked by Wall."
                else:
                    log_msg = f"Failed to move {direction}: target is out of bounds."
            else:
                log_msg = f"Failed to move: invalid direction '{direction}'."
            
            # Deduct move cost for any move attempt
            self.charge -= config.MOVE_COST

        elif action == "forage":
            if self.position in world.charge_nodes:
                # Node exists and is destroyed after foraging
                world.charge_nodes.remove(self.position)
                yield_amount = random.uniform(config.FORAGE_YIELD_MIN, config.FORAGE_YIELD_MAX)
                self.charge = min(config.STARTING_CHARGE, self.charge + yield_amount)
                log_msg = f"Successfully foraged charge node! Gained {yield_amount:.1f} charge. Current: {self.charge:.1f}."
            else:
                log_msg = "Foraged, but there is no charge node at this position."

        elif action == "attempt_vault":
            # Vault attempt has flat cost, regardless of success
            self.charge -= config.VAULT_ATTEMPT_COST
            
            if self.position in world.vault_locations:
                if self.position not in world.solved_vaults:
                    # 30% chance of success
                    success = random.random() < 0.30
                    if success:
                        reward = random.uniform(config.VAULT_SOLVE_MIN, config.VAULT_SOLVE_MAX)
                        self.charge = min(config.STARTING_CHARGE, self.charge + reward)
                        world.solved_vaults.add(self.position)
                        log_msg = f"Solved Vault! Gained {reward:.1f} charge. Current: {self.charge:.1f}."
                    else:
                        log_msg = "Attempted Vault: Solution failed. (Try again)"
                else:
                    log_msg = "Attempted Vault: This vault is already solved this generation."
            else:
                log_msg = "Attempted Vault: No vault exists at this position."

        elif action == "write_sign":
            self.charge -= config.WRITE_SIGN_COST
            text = action_args.get("text", "")
            # Cap at 80 characters
            truncated_text = text[:80].replace("\n", " ").replace(",", " ")
            world.signs[self.position] = truncated_text
            log_msg = f"Wrote sign: \"{truncated_text}\" (Cost: {config.WRITE_SIGN_COST} charge)."

        elif action == "rest":
            log_msg = "Rested."
            
        else:
            # If invalid action, treat as rest but log error
            log_msg = f"Unknown action '{action}' treated as rest."

        # Death check
        if self.charge <= 0:
            self.alive = False
            log_msg += " Charge depleted. Agent died."

        return log_msg
