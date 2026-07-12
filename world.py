import random
import config

class World:
    def __init__(self):
        # Spawn position is always the center of the grid
        self.spawn_pos = (16, 16)
        self.vault_locations = [(6, 6), (6, 25), (25, 6), (25, 25)]
        
        # Initialize grid
        self.grid = self._generate_grid()
        
        # Dynamic entities
        self.solved_vaults = set()  # Coordinates of vaults solved in this generation
        self.charge_nodes = set()   # Coordinates of active charge nodes
        self.signs = {}             # (x, y) -> text (str)
        
        # Populate initial resource nodes
        self.spawn_initial_nodes()

    def _generate_grid(self):
        """Generates a 32x32 grid with walls, barrens, chokepoints, and vaults."""
        # 1. Start with everything as WALL
        grid = [['WALL' for _ in range(config.GRID_SIZE)] for _ in range(config.GRID_SIZE)]
        
        # 2. Place vaults (fixed locations)
        for vx, vy in self.vault_locations:
            grid[vy][vx] = 'VAULT'
            
        # Helper to carve out rectangular rooms (BARRENS)
        def carve_room(cx, cy, r):
            for y in range(max(0, cy - r), min(config.GRID_SIZE, cy + r + 1)):
                for x in range(max(0, cx - r), min(config.GRID_SIZE, cx + r + 1)):
                    if grid[y][x] not in ('VAULT',):
                        grid[y][x] = 'BARRENS'

        # Carve spawn room (5x5 room centered at 16,16)
        carve_room(self.spawn_pos[0], self.spawn_pos[1], 2)
        
        # Carve small rooms around vaults
        for vx, vy in self.vault_locations:
            carve_room(vx, vy, 1)
            
        # Helper to carve corridors (CHOKEPOINTS)
        def carve_corridor(x1, y1, x2, y2):
            # L-shaped path: horizontal then vertical
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if grid[y1][x] == 'WALL':
                    grid[y1][x] = 'CHOKEPOINT'
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if grid[y][x2] == 'WALL':
                    grid[y][x2] = 'CHOKEPOINT'
                    
        # Connect spawn room to vault rooms
        for vx, vy in self.vault_locations:
            carve_corridor(self.spawn_pos[0], self.spawn_pos[1], vx, vy)
            
        # Helper to get counts of each biome
        def get_count(b_type):
            return sum(row.count(b_type) for row in grid)

        # 3. Grow BARRENS to meet percentage requirements
        total_cells = config.GRID_SIZE * config.GRID_SIZE
        target_barrens = int(total_cells * config.BARRENS_PCT)
        
        while get_count('BARRENS') < target_barrens:
            adj_walls = []
            for y in range(config.GRID_SIZE):
                for x in range(config.GRID_SIZE):
                    if grid[y][x] == 'WALL':
                        has_barrens = False
                        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < config.GRID_SIZE and 0 <= ny < config.GRID_SIZE:
                                if grid[ny][nx] == 'BARRENS':
                                    has_barrens = True
                                    break
                        if has_barrens:
                            adj_walls.append((x, y))
            if not adj_walls:
                break
            rx, ry = random.choice(adj_walls)
            grid[ry][rx] = 'BARRENS'

        # 4. Grow CHOKEPOINT to meet percentage requirements
        target_choke = int(total_cells * config.CHOKEPOINTS_PCT)
        while get_count('CHOKEPOINT') < target_choke:
            adj_walls = []
            for y in range(config.GRID_SIZE):
                for x in range(config.GRID_SIZE):
                    if grid[y][x] == 'WALL':
                        has_choke = False
                        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < config.GRID_SIZE and 0 <= ny < config.GRID_SIZE:
                                if grid[ny][nx] == 'CHOKEPOINT':
                                    has_choke = True
                                    break
                        if has_choke:
                            adj_walls.append((x, y))
            if not adj_walls:
                break
            rx, ry = random.choice(adj_walls)
            grid[ry][rx] = 'CHOKEPOINT'

        return grid

    def get_cells_by_type(self, biome_type):
        """Returns list of coordinates (x, y) matching biome_type."""
        cells = []
        for y in range(config.GRID_SIZE):
            for x in range(config.GRID_SIZE):
                if self.grid[y][x] == biome_type:
                    cells.append((x, y))
        return cells

    def spawn_initial_nodes(self):
        """Spawns initial charge nodes in the Barrens."""
        barrens = self.get_cells_by_type('BARRENS')
        # Spawn about 12 nodes initially
        num_nodes = min(12, len(barrens))
        sampled = random.sample(barrens, num_nodes)
        for x, y in sampled:
            self.charge_nodes.add((x, y))

    def tick_regen(self, tick_counter):
        """Handles random node regeneration every NODE_REGEN_TICKS ticks."""
        if tick_counter > 0 and tick_counter % config.NODE_REGEN_TICKS == 0:
            barrens = self.get_cells_by_type('BARRENS')
            available = [c for c in barrens if c not in self.charge_nodes]
            if available:
                new_node = random.choice(available)
                self.charge_nodes.add(new_node)

    def reset_for_new_generation(self):
        """Clears vault status for the new generation. Node/signs persist."""
        self.solved_vaults.clear()

    def get_perception_data(self, agent_pos):
        """
        Generates the 7x7 visual representation centered at the agent.
        Returns a dictionary containing:
          - 'ascii_map': list of strings representing the grid
          - 'details': list of strings highlighting points of interest
        """
        ax, ay = agent_pos
        ascii_lines = []
        details = []

        # Chebyshev radius is 3 (offsets -3 to +3)
        for dy in range(-config.VISION_RADIUS, config.VISION_RADIUS + 1):
            line_chars = []
            for dx in range(-config.VISION_RADIUS, config.VISION_RADIUS + 1):
                x = ax + dx
                y = ay + dy

                # Out of bounds acts as a WALL
                if not (0 <= x < config.GRID_SIZE and 0 <= y < config.GRID_SIZE):
                    line_chars.append('#')
                    continue

                cell_biome = self.grid[y][x]
                char = '.'

                is_here = (x, y) == (ax, ay)
                here_tag = " [YOU ARE HERE]" if is_here else ""

                if (x, y) in self.charge_nodes:
                    char = '@' if is_here else 'G'
                    dir_str = self._get_direction_string(dx, dy)
                    details.append(f"- Charge Node at relative position ({dx}, {dy}) {dir_str}{here_tag}")
                elif (x, y) in self.vault_locations:
                    is_solved = (x, y) in self.solved_vaults
                    char = '@' if is_here else ('v' if is_solved else 'V')
                    status = "Solved" if is_solved else "Unsolved"
                    dir_str = self._get_direction_string(dx, dy)
                    details.append(f"- Vault ({status}) at relative position ({dx}, {dy}) {dir_str}{here_tag}")
                elif (x, y) in self.signs:
                    char = '@' if is_here else 'S'
                    text = self.signs[(x, y)]
                    dir_str = self._get_direction_string(dx, dy)
                    details.append(f"- Sign at relative position ({dx}, {dy}) {dir_str} containing text: \"{text}\"{here_tag}")
                elif is_here:
                    char = '@'
                else:
                    char = '#' if cell_biome == 'WALL' else ('C' if cell_biome == 'CHOKEPOINT' else '.')

                line_chars.append(char)
            ascii_lines.append(" ".join(line_chars))

        return {
            "ascii_map": ascii_lines,
            "details": details
        }

    def _get_direction_string(self, dx, dy):
        """Translates coordinate offset into direction descriptor."""
        if dx == 0 and dy == 0:
            return "(here)"
        y_str = "North" if dy < 0 else ("South" if dy > 0 else "")
        x_str = "West" if dx < 0 else ("East" if dx > 0 else "")
        if y_str and x_str:
            return f"[{y_str}-{x_str}]"
        return f"[{y_str or x_str}]"
