import os, pty, time, select, re
D=os.path.expanduser("~/doc/shell-editor-poc")
env=dict(os.environ); env["TERM"]="xterm-256color"
pid,fd=pty.fork()
if pid==0:
    os.chdir(os.path.expanduser("~/code"))
    os.execvpe("bash",["bash","-c",f"{D}/venv/bin/python {D}/nvline.py --prompt '➜ ' >/dev/null"],env)
buf=b""
def drain(q,mx=20.0):
    global buf
    s=time.time()
    while time.time()-s<mx:
        r,_,_=select.select([fd],[],[],q)
        if r:
            try: d=os.read(fd,1<<16)
            except OSError: return
            if not d: return
            buf+=d
        else: return
time.sleep(2.5); drain(2.5)
def k(d,q=1.8):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.09)
    drain(q); return buf
def tag(b):
    # el indicador es fondo 256 + texto 232 + ' X '
    m = re.findall(r'\x1b\[48;5;(\d+)m\x1b\[38;5;232m (.) ', b.decode('utf8','replace'))
    return m[-1] if m else None
print("  al arrancar        :", tag(k(b"echo hola", 1.5)))
print("  tras Esc           :", tag(k(b"\x1b", 1.2)))
print("  tras v (visual)    :", tag(k(b"v", 1.2)))
print("  tras Esc y A       :", tag(k(b"\x1bA", 2.0)))
k(b"\x1b", 1.2)
print("  tras Esc, luego R  :", tag(k(b"R", 2.0)))
k(b"\x1b"); os.write(fd,b"\x1b"); time.sleep(0.3)
os.write(fd,b":q!\r"); time.sleep(0.6)
os.write(fd,b"\x03"); time.sleep(0.3); os.write(fd,b"\x04"); time.sleep(0.5)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
