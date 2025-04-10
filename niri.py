#! /usr/bin/env python3
from i3ipc import Con, Rect, Event, WindowEvent, WorkspaceEvent
from i3ipc.aio import Connection
from i3ipc.events import WindowEvent
import time
import asyncio

import subprocess
import os
import json
from iconfetch import fetch

"""
TODO buglist:
    - highest window should be focused first
    - workspaces not being removed
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

class Node: 
    def __init__(self)-> None: 
        self.next: Node | None = None
        self.prev: Node | None = None

class LinkedList:
    def __init__(self) -> None:
        self.stack: Node | None = None
        self.size = 0
    
    def add(self, new: Node, root: Node | None = None) -> None: 
        self.size += 1
        if root:
            new.prev = root
            new.next = root.next
            if root.next:
                root.next.prev = new
            root.next = new
        else:
            new.next = self.stack
            if self.stack:
                self.stack.prev = new
            new.prev = None
            self.stack = new

    def remove(self, node: Node) -> None:
        self.size -= 1
        if node.prev:
            node.prev.next = node.next
        else:
            self.stack = node.next
        if node.next:
            node.next.prev = node.prev

    def swap(self, a: Node, b: Node) -> None:
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

    def debug_print(self): 
        cur = self.stack
        while cur:
            print(cur, end = ' ')
            cur = cur.next

class Window(Rect, Node):
    def __init__(self, data, id):
        self.id: int = id
        self.next: Window | None
        self.prev: Window | None
        Node.__init__(self)
        Rect.__init__(self, data)

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

    async def move(self, i3: Connection, a: Rect, dx: float, dy:int=0) -> None:
        x = a.x + (self.x-a.x)*dx
        y = a.y + ((self.y+dy)-a.y)*dx
        width = a.width + (self.width-a.width)*dx
        height = a.height + (self.height-a.height)*dx

        await i3.command(f"[con_id={self.id}] resize set width {int(width)}px height {int(height)}px")
        await i3.command(f"[con_id={self.id}] move absolute position {int(x)}px {int(y)}px")

    async def focus(self, i3:Connection) -> None: 
        await i3.command(f"[con_id={self.id}] focus")

    async def move_win(self, i3:Connection, tree, dy=0): 
        global animid
        aid = animid
        win = tree.find_by_id(self.id)
        if not win:
            print("WTF")
            exit(1)
        win.rect.y -= win.deco_rect.height
        win.rect.height += win.deco_rect.height

        start = time.time()
        frames = int(DURATION * FPS)

        for _ in range(frames): 
            fstart = time.time()
            t = (fstart - start) / DURATION
            dx = DX(t)

            if t >= 1:
                dx = 1

            if aid != animid:
                return

            await self.move(i3, win.rect, dx, dy)
            
            if t >= 1:
                return 

            await asyncio.sleep(max(1/FPS-(fstart-time.time()), 0))

class Container(Node, LinkedList): 
    def __init__(self):
        self.next: Container | None
        self.prev: Container | None
        self.stack: Window | None
        Node.__init__(self)
        LinkedList.__init__(self)
        self.width: int = SCREEN.width//2

    async def organise(self, x: int) -> None:
        # theres an annoying edge case I can't fix
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

class Workspace(Node, LinkedList):
    def __init__(self):
        self.anchor: Container | None = None
        self.focus: Container | None = None
        # 0 is left, 1 is right
        self.anchordir: float = 0

        self.stack: Container | None
        self.next: Workspace | None
        self.prev: Workspace | None
        Node.__init__(self)
        LinkedList.__init__(self)

    async def cont_with_win(self, id: int) -> tuple[Container, Window] | None:
        cur = self.stack

        while cur:
            win = await cur.has_win(id)
            if win:
                return (cur, win)
            cur = cur.next
        return None

    async def focus_cont(self, cont: Container) -> None:
        if not self.anchor: 
            self.anchor = cont
            self.anchordir = 0
            self.focus = cont

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


class Niri(LinkedList):
    def __init__(self):
        self.stack: Workspace
        LinkedList.__init__(self)
        self.add(Workspace())
        self.current: Workspace = self.stack

    async def setup(self): 
        self.i3 = await Connection().connect()

        await self.i3.command("mouse_warping none")
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
        # self.i3.on(Event.WORKSPACE_FOCUS, self.focus_workspace) # type: ignore

        await self.i3.main()

    async def add_win(self, e:WindowEvent) -> None:
        await e.container.command("floating enable")  #type: ignore
        ncont:Container = Container()
        new = Window(dict(
            x = 0,
            y = 0,
            width = 100, 
            height = 100
        ), e.container.id) # type: ignore

        ncont.add(new)
        self.current.add(ncont, self.current.focus)
        self.current.focus = ncont

        await self.current.focus_cont(ncont)
        await self.move_all()

    async def focus_win(self, i3:Connection, e:WindowEvent) -> None: 
        res = await self.workspace_with_win(e.container.id) # type: ignore
        if not res: 
            await self.add_win(e)
            return
        workspace, cont, _ = res
        workspace.focus = cont
        self.current = workspace
        await workspace.focus_cont(cont)
        await self.move_all()

    async def close_win(self, i3:Connection, e:WindowEvent) -> None: 
        res = await self.workspace_with_win(e.container.id) # type: ignore
        if not res: 
            return
        workspace, cont, win = res
        
        if cont.size == 1:
            fd = int(2*workspace.anchordir-1) * (-1 if cont != workspace.anchordir else 1)
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
            
            if workspace.anchor == cont: 
                workspace.anchor = new_focus

            cont.remove(win)
            workspace.remove(cont)
            workspace.focus = new_focus

            if new_focus and new_focus.stack and self.current == workspace: 
                await new_focus.stack.focus(i3)
            # else:
            #     await self.updateinfo()
        else: 
            cont.remove(win)
            if self.current == workspace:
                if win.next:
                    await win.next.focus(i3)
                elif win.prev: 
                    await win.prev.focus(i3)

        # if workspace empty and not focused, delete it
        if workspace.size == 0 and self.size > 1: 
            self.remove(workspace)

    async def mark_win(self, i3: Connection, e: WindowEvent) -> None: 
        marks = e.container.marks

        if len(marks) == 0:
            return 

        await e.container.command("unmark") # type: ignore

        res = await self.workspace_with_win(e.container.id) # type: ignore
        if not res:
            return 
        workspace, cont, win = res

        if "_left" in marks:
            if cont.prev and cont.prev.stack:
                await cont.prev.stack.focus(i3)

        if "_right" in marks: 
            if cont.next and cont.next.stack: 
                await cont.next.stack.focus(i3)

        if "_down" in marks:
            if win.prev and self.current == workspace: 
                await win.prev.focus(i3)
            else:
                await self.workspace_down()

        if "_up" in marks:
            if win.next and self.current == workspace:
                await win.next.focus(i3)
            else:
                await self.workspace_up()

        if "_decwidth" in marks:
            cont.width -= DWIDTH
            cont.width = max(cont.width, 150)
            await workspace.focus_cont(cont)
            await self.move_all()

        if "_incwidth" in marks: 
            cont.width += DWIDTH
            cont.width = min(cont.width, SCREEN.width)
            await workspace.focus_cont(cont)
            await self.move_all()

        if "_fullwidth" in marks:
            cont.width = SCREEN.width
            await workspace.focus_cont(cont)
            await self.move_all()

        if "_moveleft" in marks:
            cont.remove(win)
            if cont.size == 0: 
                if cont.prev: 
                    workspace.remove(cont)
                    cont.prev.add(win)
                    if workspace.anchor == cont: 
                        workspace.anchor = cont.prev
                    await workspace.focus_cont(cont.prev)
                    await self.move_all()
            else:
                ncont: Container = Container() # type: ignore
                ncont.add(win)
                workspace.add(ncont, cont.prev)
                await workspace.focus_cont(ncont)
                await self.move_all()

        if "_moveright" in marks:
            cont.remove(win)
            if cont.size == 0: 
                if cont.next: 
                    workspace.remove(cont)
                    cont.next.add(win)
                    if workspace.anchor == cont: 
                        workspace.anchor = cont.prev
                    await workspace.focus_cont(cont.next)
                    await self.move_all()
            else:
                ncont: Container = Container() 
                ncont.add(win)
                workspace.add(ncont, cont)
                await workspace.focus_cont(ncont)
                await self.move_all()

        if "_swapleft" in marks:
            if cont.prev:
                if workspace.anchor == cont: 
                    workspace.anchor = cont.prev
                workspace.swap(cont.prev, cont)
                await workspace.focus_cont(cont)
                await self.move_all()
        
        if "_swapright" in marks:
            if cont.next:
                if workspace.anchor == cont: 
                    workspace.anchor = cont.next
                workspace.swap(cont, cont.next)
                await workspace.focus_cont(cont)
                await self.move_all()

        if "_moveup" in marks:
            if win.next:
                cont.swap(win, win.next)
                await workspace.focus_cont(cont)
                await self.move_all()
            # This does not work yet, and I don't know why. If you do find out, please let me know
            # else: 
            #     await self.workspace_move_up()

        if "_movedown" in marks:
            if win.prev:
                cont.swap(win.prev, win)
                await workspace.focus_cont(cont)
                await self.move_all()
            # else: 
            #     await self.workspace_move_down()

        if "_center" in marks:
            await workspace.anchor_set(cont, 0.5)
            await self.move_all()

    async def focus_workspace(self, i3: Connection, e: WorkspaceEvent): 
        try:
            num: int= min(int(e.current.name), self.size) # type: ignore
        except:
            return
        cur = self.stack
        i = 1
        while cur: 
            if i == num:
                self.current = cur
                if self.current.focus and self.current.focus.stack:
                    await self.current.focus.stack.focus(self.i3)
                else:
                    await self.move_all()
                return
            i += 1
            cur = cur.next

    async def workspace_down(self) -> None:
        if self.current.size != 0:
            if not self.current.next:
                self.add(Workspace(), self.current)
        else: 
            if self.current.next:
                self.remove(self.current)
            
        if self.current.next:
            self.current = self.current.next

        if self.current.focus and self.current.focus.stack:
            await self.current.focus.stack.focus(self.i3)
        await self.move_all()

    async def workspace_up(self) -> None:
        if self.current.size != 0:
            if not self.current.prev:
                self.add(Workspace())
        else: 
            if self.current.prev:
                self.remove(self.current)
            
        if self.current.prev:
            self.current = self.current.prev

        if self.current.focus and self.current.focus.stack:
            await self.current.focus.stack.focus(self.i3)
        await self.move_all()

    async def workspace_move_down(self) -> None:
        if not self.current.focus:
            return

        focus: Container = self.current.focus
        if self.current.next: 
            self.current.remove(focus)
            if self.current.size == 0: 
                self.remove(self.current)
            else:
                self.current.focus = focus.next or focus.prev
            self.current.next.add(focus)
            self.current = self.current.next
        else:
            if self.current.size == 1:
                return
            newws = Workspace()
            self.current.remove(focus)
            self.current.focus = focus.next or focus.prev
            self.add(newws, self.current)
            newws.add(focus)
            self.current = newws

        self.current.focus = focus
        await self.current.focus_cont(focus)
        await self.move_all()

    async def workspace_move_up(self):
        if not self.current.focus:
            return

        focus: Container = self.current.focus
        if self.current.prev: 
            self.current.remove(focus)
            if self.current.size == 0: 
                self.remove(self.current)
            else:
                self.current.focus = focus.next or focus.prev
            self.current.prev.add(focus)
            self.current = self.current.prev
        else:
            if self.current.size == 1:
                return
            newws = Workspace()
            self.current.remove(focus)
            self.current.focus = focus.next or focus.prev
            self.add(newws)
            newws.add(focus)
            self.current = newws

        self.current.focus = focus
        await self.current.focus_cont(focus)
        await self.move_all()

    async def workspace_with_win(self, id: int) -> tuple[Workspace, Container, Window] | None:

        wcur = self.stack
        while wcur: 
            res = await wcur.cont_with_win(id)
            if res: 
                return (wcur, res[0], res[1])
            wcur = wcur.next

    async def move_all(self): 
        global animid
        tree = await self.i3.get_tree()

        animid += 1
        passed: bool = False
        async with asyncio.TaskGroup() as tg:
            # tg.create_task(self.updateinfo())
            wscur = self.stack
            while wscur: 
                if self.current == wscur:
                    passed = True
                ccur = wscur.stack
                while ccur:
                    wcur = ccur.stack
                    while wcur:
                        if self.current != wscur: 
                            tg.create_task(wcur.move_win(self.i3, tree, 1080 if passed else -1080))
                        else:
                            tg.create_task(wcur.move_win(self.i3, tree))
                        wcur = wcur.next
                    ccur = ccur.next
                wscur = wscur.next

    async def updateinfo(self) -> None: 
        translate = {
            "com.github.xournalpp.xournalpp": "xournalpp",
            "sterm": "foot",
            "sranger": "folder",
            "sncmpcpp": "music",
        }

        data = {}
        data["focus"] = 0
        data["windows"] = []
        data["workspace"] = []

        tree = await self.i3.get_tree()
        ccur = self.current.stack
        p = 5
        while ccur: 
            if ccur == self.current.anchor: 
                data["focus"] = p + self.current.anchordir*(ccur.width - SCREEN.width) - 5

            wcur = ccur.stack
            while wcur: 
                win: Con|None = tree.find_by_id(wcur.id)
                if win: 
                    app_id = win.app_id.lower()
                    app_id = translate.get(app_id, app_id)
                    path = fetch(app_id) or fetch("unknown")
                    rect = {}
                    rect["x"] = p + 5 + 5
                    rect["y"] = wcur.y - 50 + 5
                    rect["width"] = wcur.width - 10
                    rect["height"] = wcur.height - 10
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

        wscur = self.stack
        while wscur: 
            data["workspace"].append(wscur == self.current)
            wscur = wscur.next

        data["width"] = max(1920, p+5)
        data = json.dumps(data)
        eww_bin= [subprocess.getoutput("which eww"), "-c", f"{os.path.expanduser('~/.config/eww/whimsy')}"]
        subprocess.Popen(eww_bin+["update", f"nirijson={data}"])
        # print(data, flush=True)

if __name__ == "__main__": 
    animid: int = 0
    niri = Niri()
    asyncio.run(niri.setup())
