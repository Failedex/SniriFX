<h1 align="center">SniriFX</h1>
<p align="center">An impractical ipc script that mimics niri</p>

https://github.com/user-attachments/assets/8b5948b3-e002-451c-9607-2fee639af38a

## About

An impractical sway script that mimics the scrollable-tiling behavior of [Niri](https://github.com/YaLTeR/niri), including the animations.

SniriFX is a rewrite of [citsfsip](https://github.com/Failedex/citsfsip), but includes a much more complicated tiling system. Although it has cleaner code and fewer bugs than it's predecessor, I would still consider it impractical and not fit for normal usage. 

**Just like citsfsip, this wasn't made to be practical. Rather, it was made because it was possible.**

## Limitations and issues

- Due to how windows are displayed in sway, this only works for a single screen (there may be ways around this). 
- Workspaces are managed separately from sway, which had to be done for animations to work.
- Moving windows between workspaces have yet to be implemented, as it causes mysterious issues I have yet to pinpoint. If you figure out what's happening, let me know.
- Floating windows don't work, because all windows are actually on floating mode. 
- Certain apps may not behave nicely when being resized or moved at 60Hz.

## Dependencies

- python3 
- i3ipc python

## Usage

> [!IMPORTANT]
> `niri.py` has global variables you need to modify which involves:
> - `TRUE_SCREEN_HEIGHT`, your screen height in px
> - `SCREEN`, a rectangle the represents your window display area (you may add gaps and reserve bar space here)

Additionally, you can also modify: 
- `DWIDTH`, the change in width when increasing or decreasing window size 
- `FPS`, frames per second for the animations
- `DURATION`, the duration of the animation
- `DX`, the animation function (check out `anims.py`)

Then run `niri.py` in any way you like
```
python niri.py
```

## Key bindings

Default key bindings are shown below 

| Binding                | Action       |
| --- | --- |
| `Mod4+k`                 | focus up     |
| `Mod4+j`                 | focus down   |
| `Mod4+h`                 | focus left   |
| `Mod4+l`                 | focus right  |
| `Mod4+e`qual             | increase width |
| `Mod4+m`inus             | decrease width | 
| `Mod4+Shift+c`           | screen width |
| `Mod4+Ctrl+h`            | merge left |
| `Mod4+Ctrl+l`            | merge right |
| `Mod4+Shift+h`           | swap left |
| `Mod4+Shift+l`           | swap right |
| `Mod4+Shift+j`           | swap down |
| `Mod4+Shift+k`           | swap up |
| `Mod4+c`                 | center |

These key binds can be changed in line 304 of `niri.py`

## Dotfiles for January post of the month

If you're looking for the full dotfiles, they aren't here.

I originally wanted to make the rice in Niri, but since it's IPC doesn't support window positions yet, I couldn't build the window overview I had in mind. Rather than wait, I figured it'd be funnier to just recreate Niri myself, which is how the project came to be.

That said, the post was more of a stunt than a proper rice. The bar was thrown together in a day, and I'm not proud of it, so I hope you understand why I won't be sharing the dotfiles.

Fortunately, I can point you towards [MereWhimsy](https://github.com/Failedex/MereWhimsy), which was the base for the dotfiles of the post, and [Ax-Shell](https://github.com/Axenide/Ax-Shell), which inspired the style of the bar.

If you do want to recreate this rice for whatever reason, I recommend modifying the script to output window information in JSON, and have your shell listen to it.
