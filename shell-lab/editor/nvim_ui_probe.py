#!/usr/bin/env python3
"""Cliente de UI minimo para nvim --embed: renderiza una rejilla de 1 fila.

Si esto funciona, "modo editor = nvim inline" es viable de verdad: nvim manda
actualizaciones de rejilla y nosotros las pintamos donde queramos, incluida una
sola linea del terminal.
"""
import subprocess, msgpack, sys, time, threading, queue

class Nvim:
    def __init__(self, args):
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        self.unpacker = msgpack.Unpacker(raw=False)
        self.replies = {}
        self.events = queue.Queue()
        self.msgid = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            data = self.p.stdout.read1(65536)
            if not data: return
            self.unpacker.feed(data)
            for msg in self.unpacker:
                if msg[0] == 1:          # respuesta
                    self.replies[msg[1]] = (msg[2], msg[3])
                elif msg[0] == 2:        # notificacion
                    self.events.put((msg[1], msg[2]))

    def call(self, method, *params, timeout=5):
        self.msgid += 1
        mid = self.msgid
        self.p.stdin.write(msgpack.packb([0, mid, method, list(params)]))
        self.p.stdin.flush()
        t0 = time.time()
        while time.time() - t0 < timeout:
            if mid in self.replies: return self.replies.pop(mid)
            time.sleep(0.002)
        raise TimeoutError(method)

    def notify(self, method, *params):
        self.p.stdin.write(msgpack.packb([2, method, list(params)]))
        self.p.stdin.flush()


# ---- la prueba: rejilla de 1 fila, cmdline y mensajes externalizados ----------
def main():
    nv = Nvim(["nvim", "--embed", "-u", "NONE", "-i", "NONE", "--noplugin"])
    err, res = nv.call("nvim_get_api_info")
    print(f"  api alcanzable: version {res[1]['version']['major']}.{res[1]['version']['minor']}")

    # UI de 1 fila. ext_cmdline y ext_messages sacan la linea de ordenes y los
    # mensajes fuera de la rejilla, que es justo lo que quiere un editor de linea:
    # la fila queda solo para el buffer.
    err, _ = nv.call("nvim_ui_attach", 80, 1, {
        "ext_linegrid": True, "ext_cmdline": True, "ext_messages": True,
        "rgb": True,
    })
    print(f"  ui_attach con rejilla 80x1: {'OK' if err is None else 'ERROR ' + str(err)}")

    nv.call("nvim_command", "set filetype=bash")
    nv.call("nvim_command", "set noswapfile nobackup")

    # escribimos una linea como si la teclearas
    nv.notify("nvim_input", "igit commit -m 'hola' && echo $HOME")
    time.sleep(0.6)

    # reconstruimos la fila a partir de los eventos grid_line
    row = [" "] * 80
    attrs = {}
    hl_of = [0] * 80
    count = 0
    while not nv.events.empty():
        name, batch = nv.events.get()
        if name != "redraw": continue
        for ev in batch:
            kind, *args = ev
            count += 1
            if kind == "grid_line":
                for a in args:
                    grid, r, col_start, cells = a[0], a[1], a[2], a[3]
                    if r != 0: continue
                    col = col_start; cur_hl = 0
                    for cell in cells:
                        text = cell[0]
                        if len(cell) > 1: cur_hl = cell[1]
                        rep = cell[2] if len(cell) > 2 else 1
                        for _ in range(rep):
                            if col < 80:
                                row[col] = text; hl_of[col] = cur_hl
                            col += 1
            elif kind == "hl_attr_define":
                for a in args:
                    attrs[a[0]] = a[1]
    line = "".join(row).rstrip()
    print(f"  eventos de redraw recibidos: {count}")
    print(f"  fila reconstruida: {line!r}")
    used = sorted({hl_of[i] for i in range(len(line)) if line[i] != ' '})
    print(f"  identificadores de resaltado en uso: {used}")
    print(f"  definiciones de atributo recibidas: {len(attrs)}")
    for i in used[:6]:
        if i in attrs: print(f"     hl {i}: {attrs[i]}")
    nv.call("nvim_command", "qa!", timeout=2) if False else nv.notify("nvim_command", "qa!")

if __name__ == "__main__":
    main()
