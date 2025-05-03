import chess
import chess.svg
import cairosvg
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging
import click
from mcp.server.fastmcp import FastMCP, Image
import mcp.types as types
from PIL import Image as PILImage
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
board: chess.Board | None = None
user_color: chess.Color = chess.WHITE # Added: Keep track of user's color

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage chess board lifecycle."""
    global board
    logger.info("Starting server lifespan...")
    board = chess.Board()
    try:
        yield {"board": board}
    finally:
        logger.info("Shutting down server lifespan...")
        board = None
        logger.info("Server lifespan ended.")

mcp = FastMCP("ChessServer", lifespan=server_lifespan, dependencies=["chess", "cairosvg", "Pillow"])

def svg_board_to_png(svg_board: str) -> dict:
    png_data = cairosvg.svg2png(bytestring=svg_board.encode("utf-8"))
    
    original_image = PILImage.open(io.BytesIO(png_data))
    width, height = original_image.size

    target_aspect = 2
    current_aspect = width / height

    if current_aspect > target_aspect:
        # Image is wider than 2:1
        target_width = width
        target_height = int(width / target_aspect)
    else:
        # Image is narrower than or equal to 2:1
        target_height = height
        target_width = int(height * target_aspect)

    background = PILImage.new('RGB', (target_width, target_height), (0, 0, 0))

    paste_x = (target_width - width) // 2
    paste_y = (target_height - height) // 2

    background.paste(original_image, (paste_x, paste_y))

    output_buffer = io.BytesIO()
    background.save(output_buffer, format='PNG')
    padded_png_data = output_buffer.getvalue()

    return Image(data=padded_png_data, format="png")

@mcp.tool()
async def get_board_visualization() -> dict:
    """Provides the current state of the chessboard as an image."""
    global board, user_color # Added user_color
    if board:
        # Added orientation based on user_color
        return svg_board_to_png(chess.svg.board(board, orientation=user_color))
        
    logger.warning("Board not available in get_board_fen")
    # Default orientation is WHITE if board isn't initialized
    return svg_board_to_png(chess.svg.board(chess.Board(), orientation=chess.WHITE))
    

@mcp.tool()
async def get_turn() -> str:
    """Indicates whose turn it is ('white' or 'black')."""
    global board
    if board:
        return "white" if board.turn == chess.WHITE else "black"
    logger.warning("Board not available in get_turn")
    return "white" # Default to white if not initialized

@mcp.tool()
async def get_valid_moves() -> list[str]:
    """Lists all legal moves for the current player in UCI notation."""
    global board
    if board and not board.is_game_over():
        return [move.uci() for move in board.legal_moves]
    elif board and board.is_game_over():
        return [] # No valid moves if game is over
    logger.warning("Board not available in get_valid_moves")
    return [] # Return empty list if not initialized


@mcp.tool()
async def make_move(move_uci: str) -> dict:
    """
    Makes a move on the board for the user and returns the new board state in SVG for visualization.
    Args:
        move_uci: The player's move in UCI format (e.g., 'e2e4').
    Returns:
        A dictionary containing the move in SAN format, the new board FEN,
        whether the game is over, and the result if applicable.
    """
    global board
    
    if not board:
        logger.error("Board not initialized in make_move.")
        return {"error": "Server not fully initialized."}

    logger.info(f"Received move: {move_uci}")
    try:
        move = board.parse_uci(move_uci)
    except ValueError:
        logger.warning(f"Invalid UCI move received: {move_uci}")
        return {"error": f"Invalid UCI move format: {move_uci}"}

    if move not in board.legal_moves:
        logger.warning(f"Illegal move received: {move_uci}")
        return {"error": f"Illegal move: {move_uci}"}

    move_san = board.san(move)
    board.push(move)
    svg = chess.svg.board(board)
    logger.info(f"Applied move: {move_san} ({move_uci}). New FEN: {board.fen()}")

    game_over = board.is_game_over()
    result = board.result() if game_over else None
    if game_over:
        logger.info(f"Game over. Result: {result}")

    return {
        "move_san": move_san,
        "game_over": game_over,
        "fen": board.fen()
    }


@mcp.tool()
async def new_game(user_plays_white: bool = True) -> str:
    """
    Starts a new game, resetting the board to the initial position.

    Args:
        user_plays_white: Whether the user will play as white. Defaults to True.
    
    Returns:
        A confirmation message indicating the game has started and the user's color.
    """
    global board, user_color # Added user_color here
    
    if board:
        board.reset()
        user_color = chess.WHITE if user_plays_white else chess.BLACK # Added: Set user_color
        logger.info(f"Board reset for a new game. User plays {'white' if user_plays_white else 'black'}.")
        fen = board.fen()
        color_name = "white" if user_plays_white else "black" # Changed variable name for clarity
        return f"New game started. Board reset. You are playing as {color_name}. Current FEN: {fen}"
    else:
        logger.error("Board not available in new_game prompt.")
        return "Error: Could not reset the board. Server might not be initialized."

@mcp.prompt()
async def new_game(arguments: dict[str, str] | None = None) -> types.GetPromptResult:
    """
    Handles the 'new_game' prompt, creating messages for starting a new chess game.

    Returns:
        A GetPromptResult containing the messages to initiate a new game conversation.
    """
    
    messages = []
    
    prompt_text = "I'd like to start a new chess game. Visualize the board after both players made a move"
    
    messages.append(
        types.PromptMessage(
            role="user", 
            content=types.TextContent(type="text", text=prompt_text)
        )
    )
    
    return types.GetPromptResult(
        messages=messages,
        description="Starting a new chess game"
    )


@click.command()
def main() -> int:
    logger.info(f"Starting Chess Server.")
    mcp.run()


if __name__ == "__main__":
    main()
