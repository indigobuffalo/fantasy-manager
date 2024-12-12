"""fantasy-manager

Usage:
    fantasy-manager <command> [<args>...]
    fantasy-manager --help
    
The available commands are:

roster   Change the players on your roster (e.g. add, drop or submit waiver claims for players)
lineup   Make changes to your lineup

For more details, see 'fantasy-manager <command> --help
"""

from cli.command import CliCommand, error_result
