#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import chess
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging

from mcp.server.fastmcp import FastMCP
import mcp.types as types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
board: chess.Board | None = None

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

mcp = FastMCP("ChessServer", lifespan=server_lifespan)


@mcp.tool()
async def get_board_fen() -> str:
    """Provides the current state of the chessboard in FEN notation."""
    global board
    if board:
        return board.fen()
    logger.warning("Board not available in get_board_fen")
    return chess.Board().fen() # Return starting FEN if not initialized

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
    Makes a move on the board for the user.
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

    # Apply user move
    move_san = board.san(move)
    board.push(move)
    logger.info(f"Applied move: {move_san} ({move_uci}). New FEN: {board.fen()}")

    # Check if the move ended the game
    game_over = board.is_game_over()
    result = board.result() if game_over else None
    if game_over:
        logger.info(f"Game over. Result: {result}")

    return {
        "move_san": move_san,
        "new_fen": board.fen(),
        "game_over": game_over,
        "result": result,
    }


@mcp.tool()
async def new_game() -> str:
    """Starts a new game, resetting the board to the initial position."""
    global board
    
    if board:
        board.reset()
        logger.info("Board reset for a new game.")
        fen = board.fen()
        return f"New game started. Board reset. Current FEN: {fen}"
    else:
        logger.error("Board not available in new_game prompt.")
        return "Error: Could not reset the board. Server might not be initialized."

@mcp.prompt()
async def new_game(arguments: dict[str, str] | None = None) -> types.GetPromptResult:
    """
    Handles the 'new_game' prompt, creating messages for starting a new chess game.
    
    Args:
        arguments: Optional dictionary containing prompt arguments, including 'opening'.
                  If 'opening' is specified, it will be mentioned in the prompt.
    
    Returns:
        A GetPromptResult containing the messages to initiate a new game conversation.
    """
    if arguments is None:
        arguments = {}
    
    opening = arguments.get("opening")
    
    messages = []
    
    # Create the main prompt message
    prompt_text = "I'd like to start a new chess game."
    if opening:
        prompt_text += f" Let's play the {opening} opening."
    
    messages.append(
        types.PromptMessage(
            role="user", 
            content=types.TextContent(type="text", text=prompt_text)
        )
    )
    
    return types.GetPromptResult(
        messages=messages,
        description="Starting a new chess game" + (f" with {opening} opening" if opening else "")
    )
