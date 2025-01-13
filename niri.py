#! /usr/bin/env python3
from i3ipc import Con, Rect, Event, WindowEvent
from i3ipc.aio import Connection
from i3ipc.events import WindowEvent
import time
import asyncio

# import subprocess
# import os
import json
from iconfetch import fetch

"""
TODO buglist:
    - highest window should be focused first
    - workspace support
Add to readme:
    - mouse_warping none
    - all bindings
    - only works on single monitor
"""

SCREEN = Rect(dict(
    x = 5,
    y = 55,
    width = 1910,
    height = 1020
))

DWIDTH = 100
FPS = 60
DURATION = 0.3
try: 
    import anims
    DX = anims.ease_out_quad
except:
    DX = lambda t: 1 - (1-t)*(1-t)

class Window(Rect):
    def __init__(self, data, id):
        self.id: int = id
        self.next: Window | None = None
        self.prev: Window | None = None
        super().__init__(data)

    def __eq__(self, other):
        if not other:
            return False

        if self.x != other.x:
            return False
        if self.y != other.y:
            return False
        if self.width != other.width:
            return False
        if self.height != other.height:
            return False
        return True

    async def set(self, x = None, y = None, width = None, height = None) -> None:
        margin = 5 
        if x is not None:
            self.x = x + margin
        if y is not None:
            self.y = y + margin
        if width is not None:
            self.width = width - 2*margin
        if height is not None:
            self.height = height - 2*margin

    async def move(self, i3, a, dx) -> None:
        x = a.x + (self.x-a.x)*dx
        y = a.y + (self.y-a.y)*dx
        width = a.width + (self.width-a.width)*dx
        height = a.height + (self.height-a.height)*dx

        await i3.command(f"[con_id={self.id}] resize set width {int(width)}px height {int(height)}px")
        await i3.command(f"[con_id={self.id}] move absolute position {int(x)}px {int(y)}px")

    async def focus(self, i3) -> None: 
        await i3.command(f"[con_id={self.id}] focus")

class Container(): 
    def __init__(self):
        self.next: Container | None = None
        self.prev: Container | None = None
        self.stack: Window | None = None
        self.size: int = 0
        self.width: int = SCREEN.width//2

    async def add_win(self, win): 
        self.size += 1
        win.next = self.stack
        if self.stack:
            self.stack.prev = win
        win.prev = None
        self.stack = win

    async def remove_win(self, win): 
        self.size -= 1
        if win.prev:
            win.prev.next = win.next
        else:
            self.stack = win.next
        if win.next:
            win.next.prev = win.prev

    async def swap_win(self, a: Window, b: Window) -> None:
        a.next, b.next = b.next, a.next
        if a.next:
            a.next.prev = a
        if b.next: 
            b.next.prev = b
        a.prev, b.prev = b.prev, a.prev
        if a.prev:
            a.prev.next = a
        else: 
            self.stack = a
        if b.prev:
            b.prev.next = b
        else: 
            self.stack = b

    async def organise(self, x: int) -> None:
        height = SCREEN.height // self.size
        p = SCREEN.y + SCREEN.height
        cur = self.stack
        while cur: 
            p -= height
            await cur.set(
                x = x,
                y = p,
                width = self.width, 
                height = height
            )
            cur = cur.next

    async def has_win(self, id) -> Window | None: 
        cur = self.stack
        while cur:
            if cur.id == id:
                return cur
            cur = cur.next
        return None

    async def move_wins(self, i3, tree): 
        global animid
        # if another animation starts running, this one will be cancelled
        aid = animid

        current = []
        cur = self.stack
        while cur: 
            win = tree.find_by_id(cur.id)
            if not win: 
                print("WTF")
                exit(1)
            win.rect.y -= win.deco_rect.height
            win.rect.height += win.deco_rect.height
            current.append(win.rect)

            cur = cur.next

        start = time.time()
        frames = int(DURATION * FPS)

        for _ in range(frames):
            fstart = time.time()
            t = (fstart - start)/DURATION
            dx = DX(t)

            if t >= 1: 
                dx = 1

            cur = self.stack
            j = 0 
            while cur:
                if aid != animid: 
                    return 

                await cur.move(i3, current[j], dx)
                j+= 1
                cur = cur.next

            if t >= 1:
                return

            await asyncio.sleep(max(1/FPS-(fstart-time.time()), 0))

class Niri():
    def __init__(self):
        self.stack: Container | None = None
        self.anchor: Container | None = None
        self.focus: Container | None = None
        # 0 is left, 1 is right
        self.anchordir: float = 0

    async def setup(self): 
        self.i3 = await Connection().connect()

        await self.i3.command("bindsym Mod4+k mark '_up'")
        await self.i3.command("bindsym Mod4+j mark '_down'")
        await self.i3.command("bindsym Mod4+h mark '_left'")
        await self.i3.command("bindsym Mod4+l mark '_right'")
        await self.i3.command("bindsym Mod4+equal mark '_incwidth'")
        await self.i3.command("bindsym Mod4+minus mark '_decwidth'")
        await self.i3.command("bindsym Mod4+Ctrl+h mark '_moveleft'")
        await self.i3.command("bindsym Mod4+Ctrl+l mark '_moveright'")
        await self.i3.command("bindsym Mod4+Shift+h mark '_swapleft'")
        await self.i3.command("bindsym Mod4+Shift+l mark '_swapright'")
        await self.i3.command("bindsym Mod4+Shift+j mark '_movedown'")
        await self.i3.command("bindsym Mod4+Shift+k mark '_moveup'")
        await self.i3.command("bindsym Mod4+c mark '_center'")
        await self.i3.command("bindsym Mod4+Shift+c mark '_fullwidth'")

        self.i3.on(Event.WINDOW_FOCUS, self.focus_win) # type: ignore
        self.i3.on(Event.WINDOW_CLOSE, self.close_win) # type: ignore
        self.i3.on(Event.WINDOW_MARK, self.mark_win) # type: ignore

        await self.i3.main()

    async def add_win(self, e:WindowEvent) -> None:
        await e.container.command("floating enable") #type: ignore
        ncont:Container = Container()
        new = Window(dict(
            x = 0, 
            y = 0, 
            width = 100, 
            height = 100
        ), e.container.id) #type: ignore

        await ncont.add_win(new)

        if self.focus:
            ncont.prev = self.focus
            ncont.next = self.focus.next    
            if self.focus.next:
                self.focus.next.prev = ncont
            self.focus.next = ncont
            await self.focus_cont(ncont)
        else:
            ncont.next = self.stack
            self.stack = ncont
            await self.anchor_set(ncont, 0)
        self.focus = ncont

    async def focus_win(self, i3, e) -> None: 
        res = await self.cont_with_win(e.container.id)
        if not res:
            # Add window
            await self.add_win(e)
            return
        self.focus = res[0]
        await self.focus_cont(res[0])

    async def close_win(self, i3, e) -> None:
        res = await self.cont_with_win(e.container.id)
        if not res:
            return
        cont, win = res
        
        if cont.size == 1: 
            fd = int(2*self.anchordir - 1) * (-1 if cont != self.anchordir else 1)
            new_focus = None
            if fd < 0: 
                if cont.prev: 
                    new_focus = cont.prev
                elif cont.next:
                    new_focus = cont.next
            else:
                if cont.next:
                    new_focus = cont.next
                elif cont.prev: 
                    new_focus = cont.prev

            if self.anchor == cont:
                self.anchor = new_focus

            await cont.remove_win(win)
            await self.remove_cont(cont)

            if new_focus and new_focus.stack:
                await new_focus.stack.focus(self.i3) 
            else:
                self.focus = None
        else:
            await cont.remove_win(win)
            if win.next:
                await win.next.focus(self.i3)
            elif win.prev:
                await win.prev.focus(self.i3)
    
    async def mark_win(self, i3, e):
        marks = e.container.marks

        if len(marks) == 0:
            return

        await e.container.command("unmark")

        res = await self.cont_with_win(e.container.id)
        if not res:
            return
        cont, win = res

        if "_left" in marks:
            if cont.prev and cont.prev.stack: 
                await cont.prev.stack.focus(self.i3)

        if "_right" in marks:
            if cont.next and cont.next.stack: 
                await cont.next.stack.focus(self.i3)

        if "_down" in marks:
            if win.prev: 
                await win.prev.focus(self.i3)

        if "_up" in marks:
            if win.next: 
                await win.next.focus(self.i3)

        if "_decwidth" in marks:
            cont.width -= DWIDTH
            cont.width = max(cont.width, 150)
            await self.focus_cont(cont)

        if "_incwidth" in marks:
            cont.width += DWIDTH
            cont.width = min(cont.width, SCREEN.width)
            await self.focus_cont(cont)

        if "_fullwidth" in marks:
            cont.width = SCREEN.width
            await self.focus_cont(cont)

        if "_moveleft" in marks:
            await cont.remove_win(win)
            if cont.size == 0:
                if cont.prev: 
                    await self.remove_cont(cont)
                    await cont.prev.add_win(win)
                    if self.anchor == cont:
                        self.anchor = cont.prev
                    await self.focus_cont(cont.prev)
            else:
                ncont:Container = Container() # type: ignore
                await ncont.add_win(win)
                ncont.prev = cont.prev
                ncont.next = cont
                if cont.prev:
                    cont.prev.next = ncont
                else:
                    self.stack = ncont
                cont.prev = ncont
                await self.focus_cont(ncont)

        if "_moveright" in marks:
            await cont.remove_win(win)
            if cont.size == 0:
                if cont.next: 
                    await cont.next.add_win(win)
                    await self.remove_cont(cont)
                    if self.anchor == cont:
                        self.anchor = cont.next
                    await self.focus_cont(cont.next)
            else:
                ncont:Container = Container()
                await ncont.add_win(win)
                ncont.next = cont.next
                ncont.prev = cont
                if cont.next:
                    cont.next.prev = ncont
                cont.next = ncont
                await self.focus_cont(ncont)

        if "_swapleft" in marks:
            if cont.prev:
                if self.anchor == cont:
                    self.anchor = cont.prev
                await self.swap_con(cont.prev, cont)
                await self.focus_cont(cont)

        if "_swapright" in marks:
            if cont.next:
                if self.anchor == cont:
                    self.anchor = cont.next
                await self.swap_con(cont, cont.next)
                await self.focus_cont(cont)

        if "_moveup" in marks:
            if win.next:
                await cont.swap_win(win, win.next)
                await self.focus_cont(cont)

        if "_movedown" in marks:
            if win.prev:
                await cont.swap_win(win.prev, win)
                await self.focus_cont(cont)

        if "_center" in marks:
            await self.anchor_set(cont, 0.5)

    async def remove_cont(self, cont): 
        if cont.prev:
            cont.prev.next = cont.next
        else:
            self.stack = cont.next
        if cont.next:
            cont.next.prev = cont.prev

    async def cont_with_win(self, id) -> tuple[Container, Window] | None:
        cur = self.stack

        while cur:
            win = await cur.has_win(id)
            if win:
                return (cur, win)
            cur = cur.next
        return None

    async def swap_con(self, a: Container, b: Container) -> None:
        a.next, b.next = b.next, a.next
        if a.next:
            a.next.prev = a
        if b.next: 
            b.next.prev = b
        a.prev, b.prev = b.prev, a.prev
        if a.prev:
            a.prev.next = a
        else: 
            self.stack = a
        if b.prev:
            b.prev.next = b
        else: 
            self.stack = b

    async def focus_cont(self, cont: Container) -> None:
        if not self.anchor: 
            return 

        # if left of screen has space, anchor at start
        if self.anchordir == 1:
            width = 0
            cur = self.anchor
            while cur: 
                width += cur.width
                cur = cur.prev

            if width <= SCREEN.width: 
                if self.stack:
                    await self.anchor_set(self.stack, 0)
        
        P = self.anchordir * SCREEN.width + SCREEN.x

        # if window is too off, anchor there
        for d in [-1, 1]:
            p = P

            if self.anchordir == 0.5:
                p += -1*d*self.anchor.width//2

            cur = self.anchor
            while cur:
                p += cur.width * d
                if cur == cont: 
                    if p > SCREEN.x + SCREEN.width or p < SCREEN.x:
                        await self.anchor_set(cur, (d + 1) // 2) 
                        return
                    break
                if d > 0:
                    cur = cur.next
                else:
                    cur = cur.prev
        
        # it's all chill, set anim anyway
        await self.anchor_set(self.anchor, self.anchordir)


    async def anchor_set(self, cont: Container, adir: float): 
        self.anchordir = adir
        self.anchor = cont
        
        if not self.anchor: 
            return

        P = (SCREEN.width * adir + SCREEN.x) - (adir*cont.width)
        for d in [1, -1]:
            p = P
            cur = self.anchor
            while cur: 
                if d == -1 and cur == self.anchor:
                    cur = cur.prev
                    continue
                if d == -1:
                    p -= cur.width
                    await cur.organise(p)
                else:
                    await cur.organise(p)
                    p += cur.width

                if d > 0:
                    cur = cur.next
                else:
                    cur = cur.prev
        
        await self.move_all()

    async def move_all(self):
        global animid
        cur = self.stack 
        tree = await self.i3.get_tree()

        animid += 1
        async with asyncio.TaskGroup() as tg:
            # tg.create_task(self.updateinfo())
            while cur: 
                tg.create_task(cur.move_wins(self.i3, tree))
                cur = cur.next

    async def updateinfo(self): 
        translate = {
            "com.github.xournalpp.xournalpp": "xournalpp",
            "sterm": "foot",
            "sranger": "folder",
            "sncmpcpp": "music",
        }

        data = {}
        data["focus"] = 0
        data["windows"] = []

        tree = await self.i3.get_tree()
        ccur = self.stack
        p = 5
        while ccur: 
            if ccur == self.anchor: 
                data["focus"] = p + self.anchordir*(ccur.width - SCREEN.width) - 5

            wcur = ccur.stack
            while wcur: 
                win: Con|None = tree.find_by_id(wcur.id)
                if win: 
                    app_id = app_id.lower()
                    app_id = translate.get(win.app_id, win.app_id)
                    path = fetch(app_id) or fetch("unknown")
                    rect = {}
                    rect["x"] = p + 5
                    rect["y"] = wcur.y - 55
                    rect["width"] = wcur.width
                    rect["height"] = wcur.height
                    data["windows"].append({
                        "app_id": win.app_id,
                        "name": win.name,
                        "pid": win.pid,
                        "focused": win.focused,
                        "rect": rect,
                        "path": path
                    })
                wcur = wcur.next

            p += ccur.width

            ccur = ccur.next

        data["width"] = max(1920, p+5)
        data = json.dumps(data)
        # eww_bin= [subprocess.getoutput("which eww"), "-c", f"{os.path.expanduser('~/.config/eww/whimsy')}"]
        # subprocess.Popen(eww_bin+["update", f"nirijson={data}"])
        print(data, flush=True)

if __name__ == "__main__": 
    animid: int = 0
    niri = Niri()
    asyncio.run(niri.setup())
