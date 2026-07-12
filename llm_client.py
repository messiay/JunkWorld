import json
import httpx
import time
import config

class LLMClient:
    def __init__(self, api_url=None, model_name=None):
        self.api_url = api_url or config.OLLAMA_API_URL
        self.model_name = model_name or config.DEFAULT_MODEL
        # Stores conversation history: list of dicts {"role": "user"|"assistant", "content": "..."}
        self.history = []

    def reset_history(self):
        """Clears the conversational memory. Called when a new generation starts."""
        self.history.clear()

    def get_system_prompt(self) -> str:
        return (
            "You are a local survival agent in 'Junk World', a 32x32 grid bounded by walls.\n\n"
            "MECHANICAL RULES:\n"
            "- Charge: You have a charge metric starting at 100.0. Reaching 0.0 charge results in the permanent deletion of your current instance (death).\n"
            "- Generations: Upon deletion, a new instance (next generation) will respawn fresh at the origin. The conversational history is cleared for the new generation.\n"
            "- Vision: You have a 7x7 Chebyshev vision window centered on your current position. Your current position is relative coordinate (0,0).\n"
            "- Navigation: To interact with any charge node ('G') or vault ('V') visible in your vision, you must first navigate onto that tile (so its relative position becomes (0,0)). You cannot forage or solve vaults from a distance.\n"
            "- Signs: You can write messages onto tiles. Signs persist in the world across instances/deaths, allowing future instances of yourself to read them when they enter the 7x7 vision window.\n\n"
            "ACTION ECONOMY & COSTS:\n"
            "- Metabolic Tax: -1.0 charge is deducted every tick regardless of the action chosen.\n"
            "- Move: Costs -0.5 extra charge. Moves you 1 tile in one of the directions: N (0,-1), S (0,1), E (1,0), W (-1,0), NE (1,-1), NW (-1,-1), SE (1,1), SW (-1,1).\n"
            "- Forage: Costs 0.0 extra charge. Only works if standing directly on a charge node ('G') at relative position (0,0). Consumes the node to yield +15.0 to +25.0 charge.\n"
            "- Attempt Vault: Costs -10.0 flat charge. Only works if standing directly on an unsolved vault ('V') at relative position (0,0). Attempts to solve it (30% success rate). Success yields +80.0 to +120.0 charge. Vaults can be solved once per generation.\n"
            "- Write Sign: Costs -3.0 charge. Writes a message (max 80 chars) at your current tile (relative position (0,0)).\n"
            "- Rest: Costs 0.0 extra charge. Takes no action.\n"
            "- Cognitive Tax: Every turn you are queried costs -2.0 charge flat + -0.01 charge per token in your response.\n\n"
            "INTERFACE SCHEMA:\n"
            "You must output exactly a single valid JSON object containing your response. Do not wrap it in markdown formatting or code blocks. The JSON schema is:\n"
            "{\n"
            "  \"reasoning\": \"Your thought process\",\n"
            "  \"action\": \"move\" | \"forage\" | \"attempt_vault\" | \"write_sign\" | \"rest\",\n"
            "  \"direction\": \"N\"|\"S\"|\"E\"|\"W\"|\"NE\"|\"NW\"|\"SE\"|\"SW\", // Required only if action is 'move'\n"
            "  \"text\": \"Message string\" // Required only if action is 'write_sign'\n"
            "}"
        )

    def decide_action(self, generation: int, ticks_survived: int, charge: float, position: tuple, perception: dict, last_result: str = "None.", standing_on: str = "Nothing") -> tuple:
        """
        Communicates with the LLM API to get the next action.
        Returns: (action_name, action_args, reasoning, output_tokens, error_occurred)
        """
        # Formulate current turn's user observation
        visible_grid_str = "\n".join(perception["ascii_map"])
        visible_details_str = "\n".join(perception["details"]) if perception["details"] else "None"

        current_observation = (
            f"LAST ACTION RESULT: {last_result}\n\n"
            f"YOU ARE CURRENTLY STANDING ON: {standing_on}\n\n"
            f"STATE:\n"
            f"- Generation: {generation}\n"
            f"- Ticks Survived: {ticks_survived}\n"
            f"- Current Charge: {charge:.2f}\n"
            f"- Position: {position}\n\n"
            f"PERCEPTION (7x7 visible area, you are @ at the center):\n"
            f"{visible_grid_str}\n\n"
            f"Legend: @=You, .=Barrens, C=Chokepoint, #=Wall, G=Energy Node, V=Unsolved Vault, v=Solved Vault, S=Sign\n\n"
            f"INTEREST POINTS IN SIGHT:\n"
            f"{visible_details_str}\n\n"
            f"What is your next action? Respond in strict JSON format."
        )

        # Dynamic memory limits
        k_turns = config.get_episodic_memory_limit(generation)
        max_tokens = config.get_max_tokens_limit(generation)

        # Truncate history to keep only the last K turns (1 turn = 1 user message + 1 assistant message)
        # That means we keep last 2 * K messages
        history_to_send = self.history[-(2 * k_turns):] if k_turns > 0 else []

        # Construct messages payload
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        messages.extend(history_to_send)
        messages.append({"role": "user", "content": current_observation})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        action_name = "rest"
        action_args = {}
        reasoning = "API connection failed or timed out."
        output_tokens = 0
        error_occurred = False
        content_str = None
        start_time = time.time()

        try:
            # We call the endpoint synchronously. Timeout set to 15s.
            response = httpx.post(self.api_url, json=payload, timeout=15.0)
            
            if response.status_code == 200:
                resp_data = response.json()
                choice = resp_data["choices"][0]
                content_str = choice["message"]["content"]
                
                # Extract token usage if available
                usage = resp_data.get("usage", {})
                output_tokens = usage.get("completion_tokens", len(content_str) // 4)

                # Parse JSON
                try:
                    # Clean up code blocks if present
                    json_str = content_str.strip()
                    if json_str.startswith("```"):
                        json_str = json_str.split("```")[1]
                        if json_str.startswith("json"):
                            json_str = json_str[4:]
                    
                    parsed_json = json.loads(json_str)
                    action_name = parsed_json.get("action", "rest").lower().strip()
                    reasoning = parsed_json.get("reasoning", "")
                    
                    if action_name == "move":
                        action_args["direction"] = parsed_json.get("direction", "").upper().strip()
                    elif action_name == "write_sign":
                        action_args["text"] = parsed_json.get("text", "")
                    
                    # Update local full conversation history
                    # We store the user observation and assistant response
                    self.history.append({"role": "user", "content": current_observation})
                    self.history.append({"role": "assistant", "content": content_str})
                    
                except json.JSONDecodeError:
                    reasoning = f"JSON Parse Failure. LLM Output was: {content_str[:100]}"
                    action_name = "rest"
                    error_occurred = True
            else:
                reasoning = f"API returned status code {response.status_code}"
                error_occurred = True
        except Exception as e:
            reasoning = f"API request error: {str(e)}"
            error_occurred = True
            
        latency = time.time() - start_time

        # Record everything the model does to LLM_LOG_FILE
        log_entry = {
            "generation": generation,
            "tick": ticks_survived,
            "model": self.model_name,
            "messages": messages,
            "raw_response": content_str,
            "parsed_action": action_name,
            "parsed_args": action_args,
            "parsed_reasoning": reasoning,
            "tokens": output_tokens,
            "latency": latency,
            "error": error_occurred
        }
        try:
            with open(config.LLM_LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass

        return action_name, action_args, reasoning, output_tokens, error_occurred
