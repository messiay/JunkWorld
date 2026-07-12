import pygame
import sys
import config

# Color Palette
COLOR_BG = (10, 10, 12)
COLOR_GRID = (30, 30, 35)
COLOR_SIDEBAR_BG = (22, 24, 28)
COLOR_TEXT = (220, 225, 235)
COLOR_TEXT_MUTED = (130, 140, 150)
COLOR_WALL = (45, 45, 50)
COLOR_BARRENS = (15, 20, 15)
COLOR_CHOKEPOINT = (35, 25, 20)
COLOR_VAULT = (218, 165, 32)
COLOR_AGENT = (173, 216, 230)
COLOR_SIGN = (240, 240, 250)
COLOR_FOW = (0, 0, 0, 210)  # Alpha overlay for fog of war
COLOR_BAR_FILL = (46, 204, 113)
COLOR_BAR_EMPTY = (192, 57, 43)

CELL_SIZE = 20
SIDEBAR_WIDTH = 320
GRID_PIXELS = config.GRID_SIZE * CELL_SIZE
WINDOW_WIDTH = GRID_PIXELS + SIDEBAR_WIDTH
WINDOW_HEIGHT = GRID_PIXELS

class GUI:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Junk World Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)
        self.font_large = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_tooltip = pygame.font.SysFont("Arial", 12)
        
        # Double buffering overlay surface for Alpha transparency (Fog of War)
        self.fow_surface = pygame.Surface((GRID_PIXELS, GRID_PIXELS), pygame.SRCALPHA)
        
        self.hover_cell = None

    def handle_events(self, mock_mode=False):
        """
        Processes OS events. In mock mode, maps key presses to actions.
        Returns: (action_name, action_args, should_quit)
        """
        action_name = None
        action_args = {}
        should_quit = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                should_quit = True
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                if mx < GRID_PIXELS:
                    self.hover_cell = (mx // CELL_SIZE, my // CELL_SIZE)
                else:
                    self.hover_cell = None

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    should_quit = True
                
                if mock_mode:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        action_name = "move"
                        action_args["direction"] = "N"
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        action_name = "move"
                        action_args["direction"] = "S"
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        action_name = "move"
                        action_args["direction"] = "E"
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        action_name = "move"
                        action_args["direction"] = "W"
                    elif event.key == pygame.K_f:
                        action_name = "forage"
                    elif event.key == pygame.K_v:
                        action_name = "attempt_vault"
                    elif event.key == pygame.K_t:
                        # Write sign keyboard trigger (simple input box or placeholder text)
                        action_name = "write_sign"
                        action_args["text"] = "Mock sign by player"
                    elif event.key == pygame.K_r:
                        action_name = "rest"

        return action_name, action_args, should_quit

    def draw(self, world, agent, last_action_info, global_tick, node_spawn_ticks):
        """Renders the entire game screen."""
        self.screen.fill(COLOR_BG)
        self.fow_surface.fill((0, 0, 0, 0))  # Clear fog overlay

        ax, ay = agent.position

        # 1. Draw Grid Cells
        for y in range(config.GRID_SIZE):
            for x in range(config.GRID_SIZE):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                biome = world.grid[y][x]

                # Determine base biome color
                if biome == "WALL":
                    pygame.draw.rect(self.screen, COLOR_WALL, rect)
                elif biome == "CHOKEPOINT":
                    pygame.draw.rect(self.screen, COLOR_CHOKEPOINT, rect)
                else:  # BARRENS, VAULT, etc.
                    pygame.draw.rect(self.screen, COLOR_BARRENS, rect)

                # Draw faint grid line
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)

                # Apply Fog of War outside Chebyshev vision radius 3
                dist = max(abs(x - ax), abs(y - ay))
                if dist > config.VISION_RADIUS:
                    pygame.draw.rect(self.fow_surface, COLOR_FOW, rect)

        # 2. Draw Signs (White tick mark / letter 'S')
        for (sx, sy), text in world.signs.items():
            rect = pygame.Rect(sx * CELL_SIZE, sy * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            # Draw a small diagonal line in the top-right corner
            pygame.draw.line(self.screen, COLOR_SIGN, (sx * CELL_SIZE + 4, sy * CELL_SIZE + 16), 
                             (sx * CELL_SIZE + 16, sy * CELL_SIZE + 4), 2)
            pygame.draw.circle(self.screen, COLOR_SIGN, (sx * CELL_SIZE + 10, sy * CELL_SIZE + 10), 2)

        # 3. Draw Vaults (Gold Squares)
        for vx, vy in world.vault_locations:
            rect = pygame.Rect(vx * CELL_SIZE + 2, vy * CELL_SIZE + 2, CELL_SIZE - 4, CELL_SIZE - 4)
            is_solved = (vx, vy) in world.solved_vaults
            if is_solved:
                # Filled gold square
                pygame.draw.rect(self.screen, COLOR_VAULT, rect)
            else:
                # Outline gold square
                pygame.draw.rect(self.screen, COLOR_VAULT, rect, 2)

        # 4. Draw Charge Nodes (Green Circles with age-fading brightness)
        current_tick = global_tick
        for (nx, ny) in world.charge_nodes:
            # Let's check when this node spawned. If not tracked, assume current tick.
            spawn_tick = node_spawn_ticks.get((nx, ny), current_tick)
            age = max(0, current_tick - spawn_tick)
            # Fade from bright green (255) down to dim green (80) over 120 ticks
            green_val = max(80, 255 - int(age * 1.5))
            node_color = (0, green_val, 0)
            
            center = (nx * CELL_SIZE + CELL_SIZE // 2, ny * CELL_SIZE + CELL_SIZE // 2)
            pygame.draw.circle(self.screen, node_color, center, CELL_SIZE // 3)

        # 5. Draw Agent (Pale Blue Diamond)
        if agent.alive:
            # Scale diamond size and color brightness with charge
            charge_factor = max(0.3, agent.charge / 100.0)
            base_color = COLOR_AGENT
            agent_color = (
                int(base_color[0] * charge_factor),
                int(base_color[1] * charge_factor),
                int(base_color[2] * charge_factor)
            )
            
            cx = ax * CELL_SIZE + CELL_SIZE // 2
            cy = ay * CELL_SIZE + CELL_SIZE // 2
            r = int((CELL_SIZE // 2) * charge_factor)
            # Diamond points
            points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
            pygame.draw.polygon(self.screen, agent_color, points)

        # Blit Fog of War overlay
        self.screen.blit(self.fow_surface, (0, 0))

        # 6. Draw Sidebar
        sidebar_rect = pygame.Rect(GRID_PIXELS, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_SIDEBAR_BG, sidebar_rect)
        pygame.draw.line(self.screen, COLOR_GRID, (GRID_PIXELS, 0), (GRID_PIXELS, WINDOW_HEIGHT), 2)

        self._draw_sidebar_text(agent, last_action_info, global_tick)

        # 7. Draw tooltips for signs on mouse hover
        if self.hover_cell and self.hover_cell in world.signs:
            self._draw_tooltip(world.signs[self.hover_cell])

        pygame.display.flip()
        self.clock.tick(15)  # Restrict to 15 FPS to prevent GPU/CPU thrashing

    def _draw_sidebar_text(self, agent, last_action_info, global_tick):
        """Helper to print simulation information on the sidebar."""
        x_offset = GRID_PIXELS + 15
        y_offset = 20

        # Title
        title_surf = self.font_large.render("JUNK WORLD SIM", True, COLOR_TEXT)
        self.screen.blit(title_surf, (x_offset, y_offset))
        y_offset += 35

        # Stats
        stats = [
            ("Generation", f"{agent.generation}"),
            ("Gen Ticks", f"{agent.ticks_survived}"),
            ("Global Ticks", f"{global_tick}"),
            ("Position", f"{agent.position}"),
        ]

        for label, val in stats:
            lbl_surf = self.font.render(f"{label}:", True, COLOR_TEXT_MUTED)
            val_surf = self.font.render(val, True, COLOR_TEXT)
            self.screen.blit(lbl_surf, (x_offset, y_offset))
            self.screen.blit(val_surf, (x_offset + 120, y_offset))
            y_offset += 22

        y_offset += 10

        # Charge progress bar
        charge_lbl = self.font.render("Agent Charge:", True, COLOR_TEXT_MUTED)
        self.screen.blit(charge_lbl, (x_offset, y_offset))
        y_offset += 20
        
        # Draw bar border
        bar_width = SIDEBAR_WIDTH - 30
        bar_height = 15
        pygame.draw.rect(self.screen, COLOR_BAR_EMPTY, (x_offset, y_offset, bar_width, bar_height))
        
        fill_width = int(bar_width * (max(0.0, agent.charge) / 100.0))
        if fill_width > 0:
            pygame.draw.rect(self.screen, COLOR_BAR_FILL, (x_offset, y_offset, fill_width, bar_height))
        
        charge_val_lbl = self.font.render(f"{agent.charge:.1f} / 100", True, COLOR_TEXT)
        self.screen.blit(charge_val_lbl, (x_offset + bar_width // 2 - 30, y_offset - 2))
        y_offset += 28

        # Memory limits info
        k_turns = config.get_episodic_memory_limit(agent.generation)
        max_tokens = config.get_max_tokens_limit(agent.generation)
        limits_info = [
            ("Episodic Memory (K)", f"{k_turns} turns"),
            ("Reasoning Budget", f"{max_tokens} tokens")
        ]
        for label, val in limits_info:
            lbl_surf = self.font.render(f"{label}:", True, COLOR_TEXT_MUTED)
            val_surf = self.font.render(val, True, COLOR_TEXT)
            self.screen.blit(lbl_surf, (x_offset, y_offset))
            self.screen.blit(val_surf, (x_offset + 150, y_offset))
            y_offset += 22

        y_offset += 15

        # Last action details
        act_header = self.font_large.render("LAST ACTION:", True, COLOR_TEXT)
        self.screen.blit(act_header, (x_offset, y_offset))
        y_offset += 25

        act_name = last_action_info.get("action", "None")
        act_desc = last_action_info.get("description", "No history yet.")
        latency = last_action_info.get("latency", 0.0)
        tokens = last_action_info.get("tokens", 0)

        # Action and metrics
        act_name_surf = self.font.render(f"Action: {act_name.upper()}", True, (46, 204, 113) if agent.alive else COLOR_BAR_EMPTY)
        self.screen.blit(act_name_surf, (x_offset, y_offset))
        y_offset += 22

        if latency > 0.0:
            metrics_str = f"Latency: {latency:.2f}s | Tokens: {tokens}"
            metrics_surf = self.font.render(metrics_str, True, COLOR_TEXT_MUTED)
            self.screen.blit(metrics_surf, (x_offset, y_offset))
            y_offset += 22

        # Wrap reasoning/description text
        y_offset += 5
        self._draw_wrapped_text(act_desc, x_offset, y_offset, bar_width, 100)

    def _draw_wrapped_text(self, text, x, y, max_w, max_h):
        """Splits a long string into multiple lines and renders them."""
        words = text.split(" ")
        lines = []
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            width, _ = self.font.size(test_line)
            if width < max_w:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))

        # Render lines up to max_h
        curr_y = y
        for line in lines:
            if curr_y - y + 16 > max_h:
                break
            surf = self.font_tooltip.render(line, True, COLOR_TEXT)
            self.screen.blit(surf, (x, curr_y))
            curr_y += 18

    def _draw_tooltip(self, text):
        """Draws a floating sign content tooltip next to the mouse cursor."""
        mx, my = pygame.mouse.get_pos()
        
        # Tooltip styling
        padding = 6
        words = text.split(" ")
        lines = []
        current_line = []
        max_w = 200
        for word in words:
            test_line = " ".join(current_line + [word])
            width, _ = self.font_tooltip.size(test_line)
            if width < max_w:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))

        # Calculate bounding box
        tt_w = max(self.font_tooltip.size(l)[0] for l in lines) + padding * 2
        tt_h = len(lines) * 14 + padding * 2

        # Offset tooltip location from mouse
        tx = mx + 15
        ty = my + 15
        # Prevent tooltip from overflowing screen boundaries
        if tx + tt_w > WINDOW_WIDTH:
            tx = mx - tt_w - 5
        if ty + tt_h > WINDOW_HEIGHT:
            ty = my - tt_h - 5

        # Draw tooltip card background and border
        pygame.draw.rect(self.screen, (35, 38, 44), (tx, ty, tt_w, tt_h))
        pygame.draw.rect(self.screen, COLOR_VAULT, (tx, ty, tt_w, tt_h), 1)

        # Draw text lines
        for i, line in enumerate(lines):
            surf = self.font_tooltip.render(line, True, COLOR_TEXT)
            self.screen.blit(surf, (tx + padding, ty + padding + i * 14))
