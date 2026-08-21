# Shell Completion Setup for AWS Scanner

The AWS Scanner CLI supports shell auto-completion for enhanced productivity.

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

## Usage Benefits

With auto-completion enabled, you can:

- Tab-complete commands: `aws-inventory <TAB>`
- Tab-complete options: `aws-inventory scan --<TAB>`
- Tab-complete values for some options
- Get suggestions for service names, regions, etc.

## Examples

```bash
# Type this and press TAB
aws-inventory <TAB>
# Shows: scan

# Type this and press TAB
aws-inventory scan --<TAB>
# Shows: --regions, --service, --profile, --tag-key, etc.

# Type this and press TAB
aws-inventory scan --service <TAB>
# Shows: ec2, s3, ecs, elb, vpc, autoscaling
```

## Verification

After installation, restart your terminal or source your shell config, then test:

```bash
aws-inventory <TAB><TAB>
```

You should see the available commands and options.
