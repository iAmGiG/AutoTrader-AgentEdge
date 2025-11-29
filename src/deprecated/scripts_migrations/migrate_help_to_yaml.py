#!/usr/bin/env python
"""
Script to migrate help commands from help_system.py to help_commands.yaml

Extracts the hardcoded dictionary from HelpSystem._build_help_data() and
converts it to YAML format.
"""

import ast
from pathlib import Path

import yaml


def extract_help_data():
    """Extract help data from help_system.py"""
    help_system_path = Path("src/cli/help_system.py")

    with open(help_system_path, encoding="utf-8") as f:
        content = f.read()

    # Parse the Python file
    tree = ast.parse(content)

    # Find the _build_help_data method
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_build_help_data":
            # The return statement contains the dict
            for stmt in node.body:
                if isinstance(stmt, ast.Return):
                    # Execute the dict literal to get actual Python object
                    # Safe: eval() on controlled source (our own help_system.py)
                    help_dict = eval(  # noqa: S307
                        compile(ast.Expression(body=stmt.value), "<string>", "eval")
                    )
                    return help_dict

    return None


def convert_to_yaml_friendly(data):
    """Convert Python dict to YAML-friendly format"""
    result = {}
    for cmd, cmd_data in data.items():
        # Convert tuple strings to multiline strings
        result[cmd] = {}
        for key, value in cmd_data.items():
            if isinstance(value, str) and "\n" in value:
                # Use literal block scalar for multiline
                result[cmd][key] = value
            else:
                result[cmd][key] = value

    return result


def main():
    """Main entry point for help command migration."""
    print("Extracting help commands from help_system.py...")
    help_data = extract_help_data()

    if not help_data:
        print("❌ Could not extract help data")
        return

    print(f"[OK] Found {len(help_data)} commands")

    # Convert to YAML-friendly format
    yaml_data = convert_to_yaml_friendly(help_data)

    # Write to YAML file
    output_path = Path("config_defaults/help_commands.yaml")

    print(f"Writing to {output_path}...")

    with open(output_path, "w", encoding="utf-8") as f:
        # Write header
        f.write("# CLI Help Command Documentation\n")
        f.write("# Auto-generated from help_system.py _build_help_data()\n")
        f.write(
            "# Format: command_name -> "
            "{category, description, usage, examples, aliases, tags, related, details}\n\n"
        )

        # Write YAML with better formatting
        yaml.dump(
            yaml_data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )

    print(f"[OK] Successfully wrote {len(yaml_data)} commands to {output_path}")
    print("\nNext steps:")
    print("1. Review the generated YAML file")
    print("2. Update HelpSystem class to load from YAML")
    print("3. Test help system functionality")


if __name__ == "__main__":
    main()
