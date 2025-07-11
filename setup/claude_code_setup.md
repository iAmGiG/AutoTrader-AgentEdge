#  Using Claude Code (Anthropic CLI)

[ClaudeCode](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview#before-you-begin)

## Overview

Claude Code is a Node‑based CLI for running Anthropic agents locally. Getting it working smoothly often comes down to having the right Node.js version, a sane npm prefix, and a recent C++ tool‑chain for any native bindings (e.g., better‑sqlite3).

## cmds that helped

- node -v [node.js version]
- npm install -g n (npm install node)
- sudo n latest (node latest, I think)
- nvm install node (other ways around not having sudo)
- curl -o- <https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh> | bash (get nvm fast)
- export NVM_DIR="$HOME/.nvm"
- source "$NVM DIR/nvm.sh"
- nvm install 18
- nvm use --delete-prefix v18.20.8

### 🧰 Version Checks

```bash
node  -v      # current Node.js
npm   -v      # current npm
nvm   -v      # Node Version Manager (if installed)
nvm ls-remote # list all Node versions (v24.0.1 is current as of 2025‑05‑13)
```

### Install & Initialise nvm (without sudo)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
```

> Tip: drop those two export / source lines in your ~/.bashrc right before the Conda block so nvm always loads first.

### Install / Switch Node.js versions

```bash
nvm install 24.0.1                # latest production release
nvm use --delete-prefix v24.0.1   # switch & clear npm prefix conflicts
nvm alias default 24.0.1          # make it the default for new shells
```

###  💡 Why Node ≥ 20?

The claude CLI passes --enable‑source‑maps on launch; that flag exists only in Node 12.12+ and is required by modern stack traces. (as the default Node was 10.x.x in this environment)

### Fixing npm Global Installs (no sudo)

1. Clear any leftover prefix

    ```bash
    npm config delete prefix
    ```

2. Optional personal prefix

    ```bash
    mkdir -p ~/.npm-global
    echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
    ```

3. Upgrade npm (compatible with Node 24)

    ```bash
    npm install -g npm # Installs the latest npm supported by the current Node.js version
    ```

###  Install Claude Code CLI

Install a modern compiler inside your Conda env first

```bash
conda activate [env]
conda install -c conda-forge gxx_linux-64 gcc_linux-64
```

```bash
# Then install claude
nvm use --delete-prefix v24.0.1
npm install -g @anthropic-ai/claude-code
```

```bash
npm install -g @anthropic-ai/claude-code
claude --version              # Verify install
```

### Verify

```bash
node   -v       # v24.0.1
npm    -v       # 11.x
claude --version
claude          # launches prompt (no “bad option: --enable-source-maps” error)
```

### Troubleshooting Table

| Symptom                                                                                | Fix                                                                                                                   |
| -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **`node: bad option: --enable-source-maps`**                                           | Use Node 12.12+ (ideally ≥ 20). `nvm use v24`. Ensure nvm block is above Conda init in `~/.bashrc`.                   |
| **`npm ERR! EACCES … /usr/local/lib/node_modules`**                                    | Remove global prefix (`npm config delete prefix`) and/or use personal prefix (`~/.npm-global`).                       |
| **`g++: error: unrecognized option ‘-std=gnu++20’`** while installing `better-sqlite3` | `conda install -c conda-forge gxx_linux-64 gcc_linux-64` (modern compiler) **or** reinstall CLI with `--no-optional`. |
| CLI not found after install                                                            | Ensure `~/.npm-global/bin` or nvm’s `…/bin` is first in `$PATH`.                                                      |
| Node reverts to Conda’s copy in new shells                                             | Place nvm init block *before* `# >>> conda initialize >>>` in `~/.bashrc`.                                            |

### Clean Restart in VS Code Terminal (if needed)
>
1. Press **Ctrl + C** in the terminal to stop any running claude process.
2. Trash 🗑️ the terminal tab.
3. Click ➕ to open a new terminal and run claude.
