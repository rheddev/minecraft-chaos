import asyncio
import websockets
import subprocess
import sys
import logging
import math
from typing import List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_circle_points(n: int, radius: int = 5) -> List[Tuple[int, int, int]]:
    """
    Generate points in a circle around the origin.
    
    Args:
        n: Number of points to generate
        radius: Radius of the circle
        
    Returns:
        List of (y, 0, x) coordinates
    """
    if n < 1:
        raise ValueError("Number of points must be positive")
    if radius < 1:
        raise ValueError("Radius must be positive")
        
    points = []
    for i in range(n):
        # Angle in radians, starting from top and moving clockwise
        angle = math.pi / 2 - i * (2 * math.pi / n)
        x = round(radius * math.cos(angle))
        y = round(radius * math.sin(angle))
        points.append((y, 0, x))
    return points

class MinecraftServer:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.websocket_server = None
        self.connected_clients = set()
        self.MAX_CREEPERS = 100
        self.MAX_RADIUS = 20

    async def start_minecraft_server(self):
        try:
            # Start the Minecraft server process
            self.process = subprocess.Popen(
                ['./start.sh'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            logger.info("Minecraft server process started")
            
            # Start tasks to read process output
            asyncio.create_task(self.read_process_output(self.process.stdout, "OUT"))
            asyncio.create_task(self.read_process_output(self.process.stderr, "ERR"))
        except Exception as e:
            logger.error(f"Failed to start Minecraft server: {e}")
            sys.exit(1)

    async def read_process_output(self, stream, prefix: str):
        try:
            while True:
                line = await asyncio.get_event_loop().run_in_executor(None, stream.readline)
                if not line:
                    break
                line = line.strip()
                if line:
                    message = f"[{prefix}] {line}"
                    logger.info(message)
                    await self.broadcast(message)
        except Exception as e:
            logger.error(f"Error reading process output: {e}")

    async def broadcast(self, message: str):
        if self.connected_clients:
            try:
                await asyncio.gather(
                    *[client.send(message) for client in self.connected_clients],
                    return_exceptions=True
                )
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")

    async def send_command(self, websocket, command):
        # Handle both single commands and arrays of commands
        commands = command if isinstance(command, list) else [command]
        
        # Send command to Minecraft server process
        if self.process and self.process.stdin:
            try:
                for cmd in commands:
                    if cmd:  # Only send non-empty commands
                        self.process.stdin.write(f"{cmd}\n")
                        self.process.stdin.flush()
                        await websocket.send(f"Command sent: {cmd}")
            except Exception as e:
                logger.error(f"Failed to send command to Minecraft server: {e}")
                await websocket.send(f"Error: Failed to send command")
        else:
            await websocket.send("Error: Minecraft server not running")

    def parse_command(self, message: str) -> Tuple[str, Optional[int], Optional[str]]:
        """
        Parse the command message into command, count, and name.
        
        Args:
            message: The raw message from the websocket
            
        Returns:
            Tuple of (command, count, name) where count and name are optional
        """
        try:
            parts = message[1:].strip().split()
            command = parts[0].lower()
            
            count = None
            name = None
            
            # Parse remaining arguments
            i = 1
            while i < len(parts):
                if parts[i] == "--name" and i + 1 < len(parts):
                    name = parts[i + 1]
                    i += 2
                else:
                    try:
                        count = int(parts[i])
                        i += 1
                    except ValueError:
                        raise ValueError(f"Invalid argument: {parts[i]}")
            
            return command, count, name
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing command: {e}")
            raise ValueError("Invalid command format")

    async def handle_websocket(self, websocket):
        self.connected_clients.add(websocket)
        try:
            async for message in websocket:
                if message.startswith('#'):
                    try:
                        command, count, name = self.parse_command(message)
                        logger.info(f"Received command: {command} {count if count is not None else ''} {f'--name {name}' if name else ''}")
                        
                        if command == "creeper":
                            # Default to 4 creepers if no count specified
                            if count is None:
                                count = 4
                                
                            if count > self.MAX_CREEPERS:
                                await websocket.send(f"Error: Maximum {self.MAX_CREEPERS} creepers allowed")
                                continue
                                
                            # surround player with {count} creepers
                            points = get_circle_points(count)
                            name_tag = f",CustomName:'\"{name}\"'" if name else ""
                            commands = [f"execute at RhamzThev run summon creeper ~{point[0]} ~{point[1]} ~{point[2]} {{powered:1{name_tag}}}" for point in points]
                            await self.send_command(websocket, commands)
                            
                        elif command == "jack":
                            # Spawn a Chicken Jockey, a Water Bucket, a Flint and Steel, and a Crafting Table
                            name_tag = f",CustomName:'\"{name}\"'" if name else ""
                            await self.send_command(websocket, [
                                # Spawn chicken jockey 3 blocks in front of player
                                f"execute at RhamzThev run summon chicken ~3 ~ ~ {{Passengers:[{{id:\"zombie\",IsBaby:1{name_tag}}}]}}",
                                # Give items to player
                                "give RhamzThev water_bucket 1",
                                "give RhamzThev flint_and_steel 1",
                                "give RhamzThev crafting_table 1"
                            ])
                            
                        elif command == "godsend":
                            # Spawn Netherite Armor + Tools + Other good stuff
                            await self.send_command(websocket, [
                                # Netherite Helmet
                                "give RhamzThev netherite_helmet{Enchantments:[{id:protection,lvl:4},{id:respiration,lvl:3},{id:aqua_affinity,lvl:1},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:thorns,lvl:3}]} 1",
                                
                                # Netherite Chestplate
                                "give RhamzThev netherite_chestplate{Enchantments:[{id:protection,lvl:4},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:thorns,lvl:3}]} 1",
                                
                                # Netherite Leggings
                                "give RhamzThev netherite_leggings{Enchantments:[{id:protection,lvl:4},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:thorns,lvl:3}]} 1",
                                
                                # Netherite Boots
                                "give RhamzThev netherite_boots{Enchantments:[{id:protection,lvl:4},{id:feather_falling,lvl:4},{id:depth_strider,lvl:3},{id:soul_speed,lvl:3},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:thorns,lvl:3}]} 1",
                                
                                # Netherite Sword
                                "give RhamzThev netherite_sword{Enchantments:[{id:sharpness,lvl:5},{id:looting,lvl:3},{id:sweeping,lvl:3},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:fire_aspect,lvl:2},{id:knockback,lvl:2}]} 1",
                                
                                # Netherite Axe
                                "give RhamzThev netherite_axe{Enchantments:[{id:sharpness,lvl:5},{id:efficiency,lvl:5},{id:unbreaking,lvl:3},{id:mending,lvl:1}]} 1",
                                
                                # Netherite Pickaxe
                                "give RhamzThev netherite_pickaxe{Enchantments:[{id:efficiency,lvl:5},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:fortune,lvl:3}]} 1",
                                
                                # Netherite Shovel
                                "give RhamzThev netherite_shovel{Enchantments:[{id:efficiency,lvl:5},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:silk_touch,lvl:1}]} 1",
                                
                                # Netherite Hoe
                                "give RhamzThev netherite_hoe{Enchantments:[{id:efficiency,lvl:5},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:fortune,lvl:3}]} 1",
                                
                                # Bow with Infinity
                                "give RhamzThev bow{Enchantments:[{id:power,lvl:5},{id:unbreaking,lvl:3},{id:infinity,lvl:1},{id:flame,lvl:1}]} 1",
                                
                                # Bow with Mending (alternative)
                                "give RhamzThev bow{Enchantments:[{id:power,lvl:5},{id:unbreaking,lvl:3},{id:mending,lvl:1},{id:flame,lvl:1}]} 1",
                                
                                # Arrows for the Mending bow
                                "give RhamzThev arrow 64"
                            ])
                            
                        elif command == "chaos":
                            # Spawn Wither and Ender Dragon
                            name_tag = f"{{CustomName:'\"{name}\"'}}" if name else ""
                            await self.send_command(websocket, [
                                f"execute at RhamzThev run summon wither ~10 ~ ~ {name_tag}",
                                f"execute at RhamzThev run summon ender_dragon ~10 ~ ~ {name_tag}"
                            ])
                        elif command == "kill":
                            # Kills all mobs (Except RhamzThev)
                            await self.send_command(websocket, [
                                # Kill all non-player entities
                                "kill @e[type=!player]",
                            ])
                        else:
                            await websocket.send(f"Error: Unknown command '{command}'")
                            
                    except ValueError as e:
                        await websocket.send(f"Error: {str(e)}")
                    except Exception as e:
                        logger.error(f"Error handling command: {e}")
                        await websocket.send("Error: An unexpected error occurred")
                else:
                    await websocket.send("Error: Commands must start with #")
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error handling WebSocket connection: {e}")
        finally:
            self.connected_clients.remove(websocket)

    async def start_websocket_server(self):
        self.websocket_server = await websockets.serve(
            self.handle_websocket,
            "localhost",
            8765
        )
        logger.info("WebSocket server started on ws://localhost:8765")

    async def run(self):
        # Start the Minecraft server
        await self.start_minecraft_server()
        
        # Start the WebSocket server
        await self.start_websocket_server()
        
        # Keep the server running
        await self.websocket_server.wait_closed()

if __name__ == "__main__":
    server = MinecraftServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if server.process:
            server.process.terminate()
