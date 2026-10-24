# 🍰 sweets

A plate of desserts slowly spinning in your terminal, rendered in 3D ASCII.
it does nothing useful, it just looks nice while you take a break and also works for putting things up in linux rices i guess.

## Installation

You need **Python 3.8 or newer**. There's nothing else to install: sweets only uses the
Python standard library.

It runs on **Linux** and **macOS**. On Windows, run it inside
[WSL](https://learn.microsoft.com/windows/wsl/install), because native Windows Python doesn't
ship `curses`.

1. Get the code:

   ```sh
   git clone https://github.com/mint2222222/sweets.git
   cd sweets
   ```

2. Try it straight away:

   ```sh
   python3 sweets.py
   ```

3. Optional: make `sweets` a command you can run from anywhere by linking it into a folder on
   your `PATH`:

   ```sh
   mkdir -p ~/.local/bin
   ln -s "$PWD/sweets.py" ~/.local/bin/sweets
   ```

   If `sweets` still isn't found, add `~/.local/bin` to your `PATH`: put
   `export PATH="$HOME/.local/bin:$PATH"` in your `~/.bashrc` or `~/.zshrc` and open a new
   terminal.

**Updating:** run `git pull` in the `sweets` folder. The link keeps working.

**Uninstalling:** `rm ~/.local/bin/sweets`, then delete the folder.

## Usage

```sh
sweets                   # a pile of macarons
sweets cheesecake        # pick one: macarons, cheesecake, tiramisu, pancakes, donuts, mochi, birthday
sweets --random          # surprise me
sweets --birthday Mina   # birthday cake with flickering candles
sweets --screensaver     # a new dessert every 30 seconds
sweets --clock           # a small clock in the corner
sweets --once            # one full turn, then exit (nice in a shell greeting)
sweets --help            # everything else
```

### Keys

| key | does |
| --- | --- |
| `space` | next dessert |
| `e` | eat it, one bite at a time |
| `r` | serve again |
| `c` | toggle the clock |
| `s` | toggle screensaver mode |
| `+` / `-` | spin faster / slower |
| `q` | quit |

### Colour

Monochrome is the default. For colour:

```sh
sweets --color           # gruvbox
sweets --color term      # your terminal's own 16 colours, so it matches your theme
sweets --color amber     # retro amber monitor
sweets --color green     # retro green monitor
```

### Tips

- Bigger terminal windows show more detail. Around 120×36 or larger looks best.
- The first full turn renders every frame live. After that the frames are cached, so it costs
  next to nothing.

## Self-check

```sh
python3 test_sweets.py
```

---

<sub><i>the owls are not what they seem.🦉</i></sub>
