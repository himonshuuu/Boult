from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional
from urllib.parse import quote

import asyncpg

import config
from core import Boult
from utils.db import DatabaseManager

class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name='discord.state')

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelname == 'WARNING' and 'referencing an unknown' in record.msg:
            return False
        return True

RESET = "\x1b[0m"

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
ITALIC = "\x1b[3m"
UNDERLINE = "\x1b[4m"

COLORS_MAP = {
    'BLACK': '30',
    'RED': '31',
    'GREEN': '32',
    'YELLOW': '33',
    'BLUE': '34',
    'MAGENTA': '35',
    'CYAN': '36',
    'WHITE': '37',
    
    'BRIGHT_BLACK': '90',
    'BRIGHT_RED': '91',
    'BRIGHT_GREEN': '92',
    'BRIGHT_YELLOW': '93',
    'BRIGHT_BLUE': '94',
    'BRIGHT_MAGENTA': '95',
    'BRIGHT_CYAN': '96',
    'BRIGHT_WHITE': '97',
}

for color_name, color_code in COLORS_MAP.items():
    globals()[color_name] = f"\x1b[{color_code}m"
    globals()[f"BG_{color_name}"] = f"\x1b[{int(color_code)+10}m"

LOG_COLORS = {
    "DEBUG": f"{DIM}{BLUE}",
    "INFO": GREEN,
    "WARNING": f"{BOLD}{YELLOW}",
    "ERROR": f"{BOLD}{BRIGHT_RED}",
    "CRITICAL": f"{BOLD}{BG_BRIGHT_RED}{WHITE}",
}


class CustomFormatter(logging.Formatter):
    """
    A custom formatter that adds colors and styling to log messages.
    
    Format:
    [timestamp] LEVEL name: message
    """
    
    def __init__(self, fmt=None, datefmt=None, style='{', validate=True):
        super().__init__(fmt, datefmt, style, validate)
        self.default_msec_format = '%s.%03d'

    def format(self, record):

        orig_levelname = record.levelname
        orig_name = record.name
        
        level_color = LOG_COLORS.get(record.levelname, RESET)
        record.levelname = f"{level_color}{record.levelname:8}{RESET}"
        record.name = f"{CYAN}{record.name}{RESET}"
    
        formatted_msg = super().format(record)
        
        record.levelname = orig_levelname
        record.name = orig_name
        
        return formatted_msg

    def formatException(self, ei):
        exception_text = super().formatException(ei)
        return f"{BRIGHT_RED}{exception_text}{RESET}"


async def create_pool() -> asyncpg.Pool:
    def _encode_jsonb(value):
        return json.dumps(value)

    def _decode_jsonb(value):
        return json.loads(value)

    async def init(con):
        await con.set_type_codec(
            'jsonb',
            schema='pg_catalog',
            encoder=_encode_jsonb,
            decoder=_decode_jsonb,
            format='text'
        )

    return await asyncpg.create_pool(
        user=config.pgsql.pg_user,
        password=config.pgsql.pg_auth,
        host=config.pgsql.pg_host,
        port=config.pgsql.pg_port,
        database=config.pgsql.pg_dbname,
        init=init,
        command_timeout=300,
        max_size=20,
        min_size=20
    )

async def run_bot(args) -> int:
    """Run the bot with proper cleanup"""
    bot: Optional[Boult] = None

    db_manager = DatabaseManager()
    await db_manager.initialize(f"postgresql://{config.pgsql.pg_user}:{quote(config.pgsql.pg_auth)}@{config.pgsql.pg_host}:{config.pgsql.pg_port}/{config.pgsql.pg_dbname}")

    log.info('Starting bot...')
    bot = Boult(dev=args.dev, db_manager=db_manager)
    bot.logger = log

    async with bot:
        await bot.boot() 

    return 0

def setup_logging(debug: bool = False) -> logging.Logger:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    

    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = CustomFormatter(
        "{asctime} {levelname:<8} {name} {message}", dt_fmt, style="{"
    )

    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(
            filename="boult.log",
            encoding='utf-8',
            mode="a",
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
        )
    ]

    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    # Set levels for noisy loggers :)
    for logger_name in ('asyncio', 'wavelink', 'discord.voice_state', 'discord.state', 'discord.client', 'discord.gateway', 'discord.http'):
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)

    if debug:
        logger.setLevel(logging.DEBUG)

    return logger

def main(args) -> int:
    """Main entry point for the application."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(run_bot(args))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Boult Discord Bot')
    parser.add_argument('--dev', action='store_true', default=False,
                      help='Run in development mode')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging and asyncio debug mode')

    args = parser.parse_args()

    if args.debug:
        os.environ['PYTHONASYNCIODEBUG'] = '1'
        logging.getLogger('asyncio').setLevel(logging.DEBUG)

    log = setup_logging(args.debug)
    try:
        sys.exit(main(args))
    except Exception as e:
        log.error(f'Fatal error during startup: {e}', exc_info=True)
        os._exit(1)
    except KeyboardInterrupt:
        log.info('Received signal to terminate bot')
        os._exit(0)
    finally:
        log.info('Shutting down...')
        os._exit(0)