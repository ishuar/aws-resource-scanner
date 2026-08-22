# Shell Completion

Enable tab-completion for the `aws-inventory` CLI.

> [!IMPORTANT]
> Completion only works when `aws-inventory` is on your `PATH`, because
> the shell runs that command to fetch suggestions. `poetry run
> aws-inventory <TAB>` never completes — the shell is completing
> `poetry`, not `aws-inventory`. Install it as a tool
> (`uv tool install aws-resource-inventory` or `pipx install
> aws-resource-inventory`), or activate the project virtualenv first.

## Enable Auto-Completion

### For Zsh (macOS default)

```bash
# Show completion script for your shell
aws-inventory --show-completion

# Install completion for current shell
aws-inventory --install-completion

# Or manually add to your shell config
aws-inventory --show-completion >> ~/.zshrc
source ~/.zshrc
```

### For Bash

```bash
# Install completion for current shell
aws-inventory --install-completion

# Or manually add to your bash config
aws-inventory --show-completion >> ~/.bashrc
source ~/.bashrc
```

### For Fish

```bash
# Install completion for current shell
aws-inventory --install-completion

# Or manually add to fish config
aws-inventory --show-completion >> ~/.config/fish/completions/aws-inventory.fish
```

## What completes

- Commands: `aws-inventory <TAB>` → `scan`
- Option names: `aws-inventory scan --<TAB>` → `--regions`, `--service`,
  `--profile`, `--tag-key`, …
- Service names: `aws-inventory scan --service <TAB>` → `ec2`, `s3`,
  `ecs`, `efs`, `elb`, `vpc`, `rds`, `autoscaling`

## Verification

After installation, restart your terminal or source your shell config, then test:

```bash
aws-inventory <TAB><TAB>
```

You should see the available commands and options.
