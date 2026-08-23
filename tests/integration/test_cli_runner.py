"""
tests/integration/test_cli_runner.py
Integration tests for CLI argument parsing, subcommands dispatch, and configuration loading.
"""

import os
from pathlib import Path
import pytest

from src.main import build_parser, load_config, get_cookies


def test_cli_parser_help_output():
    """Verify CLI parser help structure."""
    parser = build_parser()
    help_text = parser.format_help()
    assert "auto_post" in help_text
    assert "scrape" in help_text
    assert "generate" in help_text
    assert "post" in help_text
    assert "run" in help_text


def test_cli_parser_run_subcommand():
    """Verify 'run' subcommand argument parsing."""
    parser = build_parser()
    args = parser.parse_args(["run", "--dry-run", "--platforms", "youtube"])
    assert args.command == "run"
    assert args.dry_run is True
    assert args.platforms == "youtube"


def test_cli_parser_scrape_subcommand():
    """Verify 'scrape' subcommand argument parsing."""
    parser = build_parser()
    args = parser.parse_args(["scrape", "--platform", "youtube", "--max-posts", "3", "--dry-run"])
    assert args.command == "scrape"
    assert args.platform == "youtube"
    assert args.max_posts == 3
    assert args.dry_run is True


def test_cli_parser_generate_subcommand():
    """Verify 'generate' subcommand argument parsing."""
    parser = build_parser()
    args = parser.parse_args(["generate", "--niche", "stories", "--platform", "youtube", "--dry-run"])
    assert args.command == "generate"
    assert args.niche == "stories"
    assert args.platform == "youtube"
    assert args.dry_run is True


def test_cli_parser_post_subcommand():
    """Verify 'post' subcommand argument parsing."""
    parser = build_parser()
    args = parser.parse_args(["post", "--platform", "youtube", "--content", "Nội dung", "--dry-run"])
    assert args.command == "post"
    assert args.platform == "youtube"
    assert args.content == "Nội dung"
    assert args.dry_run is True


def test_cli_parser_invalid_subcommand_raises_exit():
    """Verify invalid subcommand raises SystemExit."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["invalid_command_name"])


def test_load_config_sources_yaml():
    """Verify loading config/sources.yaml returns expected structure."""
    config = load_config("sources.yaml")
    assert isinstance(config, dict)
    assert "youtube" in config
    assert "sources" in config["youtube"]


def test_load_config_niches_yaml():
    """Verify loading config/niches.yaml contains stories, humor, health niches."""
    config = load_config("niches.yaml")
    assert isinstance(config, dict)
    assert "niches" in config
    niches = config["niches"]
    assert "stories" in niches
    assert "humor" in niches
    assert "health" in niches


def test_get_cookies_from_env(monkeypatch):
    """Verify get_cookies reads YT_COOKIES environment variable."""
    monkeypatch.setenv("YT_COOKIES", '[{"name": "test", "value": "val"}]')
    cookies = get_cookies("youtube")
    assert cookies is not None
    assert "test" in cookies
