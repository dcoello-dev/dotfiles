import os, pty, time, select, re
env={k:v for k,v in os.environ.items() if k!="BLE_VERSION"}; env["TERM"]="xterm-256color"
LAB=os.path.expanduser("~/shell-lab/lab")
pid,fd=pty.fork()
if pid==0: os.chdir(os.path.expanduser("~/code")); os.execve(LAB,[LAB],env)
buf=b""
def drain(q,mx=25.0):
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
time.sleep(2.2); drain(3.0)
def k(d,q=2.2):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.06)
    drain(q); return buf
def ls_(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','\n').split("\n") if l.strip()]
print("  ya estamos dentro (arranque automatico). Escribimos 'hl' otra vez:")
r = k(b"hl\n", 4.0)
for l in ls_(r)[:5]: print("    ", l[:90])
print("  ¿cuantos 'editor on' se ven?", sum(1 for l in ls_(r) if "editor on" in l))
print("  ahora un C-d:")
r2 = k(b"\x04", 2.5)
for l in ls_(r2)[:4]: print("    ", l[:90])
print("  ¿seguimos en el editor tras un solo C-d?", "SI, anidado" if any("(editor)" in l for l in ls_(r2)) else "no, salimos")
os.write(fd,b"\x04"); time.sleep(0.4); os.write(fd,b"exit\n"); time.sleep(0.4)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
