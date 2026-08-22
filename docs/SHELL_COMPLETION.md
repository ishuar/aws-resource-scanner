# Shell Completion

Enable tab-completion for the `aws-inventory` CLI.

## Enable Auto-Completion

### For Zsh (macOS default)

```bash
# Show completion script for your shell
poetry run aws-inventory --show-completion

# Install completion for current shell
poetry run aws-inventory --install-completion

# Or manually add to your shell config
poetry run aws-inventory --show-completion >> ~/.zshrc
source ~/.zshrc
```

### For Bash

```bash
# Install completion for current shell
poetry run aws-inventory --install-completion

# Or manually add to your bash config
poetry run aws-inventory --show-completion >> ~/.bashrc
source ~/.bashrc
```

### For Fish

```bash
# Install completion for current shell
poetry run aws-inventory --install-completion

# Or manually add to fish config
poetry run aws-inventory --show-completion >> ~/.config/fish/completions/aws-inventory.fish
```

## What completes

- Commands: `aws-inventory <TAB>` → `scan`
- Option names: `aws-inventory scan --<TAB>` → `--regions`, `--service`,
  `--profile`, `--tag-key`, …

## Verification

After installation, restart your terminal or source your shell config, then test:

```bash
aws-inventory <TAB><TAB>
```

You should see the available commands and options.
