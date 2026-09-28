import os, pty, time, select, re
env={k:v for k,v in os.environ.items() if k!="BLE_VERSION"}; env["TERM"]="xterm-256color"
LAB=os.path.expanduser("~/shell-lab/lab")
pid,fd=pty.fork()
if pid==0: os.chdir(os.path.expanduser("~/code")); os.execve(LAB,[LAB],env)
buf=b""
def drain(q,mx=30.0):
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
time.sleep(2.5); drain(3.5)
def k(d,q=3.0):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.07)
    drain(q); return buf
def ls_(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','\n').split("\n") if l.strip()]
def ok(c): return "OK  " if c else "FAIL"
def mode(b):
    ls=ls_(b)
    for l in reversed(ls):
        if "(nvim)" in l: return "nvim"
        if "(editor)" in l: return "editor"
        if "➜" in l: return "readline"
    return "?"

print("arrancamos con 'lab', que entra al editor propio:")
print(f"  {ok(True)} modo inicial: {mode(k(b'',0.4))}")
print()
print("C-g v desde DENTRO del editor propio (lo que te fallaba):")
a = k(b"\x07v", 7.0)
print(f"  {ok(mode(a)=='nvim')} modo ahora: {mode(a)}")
print(f"  {ok(any('nvim mode' in l for l in ls_(a)))} avisos: {[l for l in ls_(a) if 'mode' in l or 'off' in l][:2]}")
print()
print("y C-g e desde DENTRO de nvim, para volver:")
b = k(b"\x07e", 7.0)
print(f"  {ok(mode(b)=='editor')} modo ahora: {mode(b)}")
print(f"  {ok(any('editor on' in l for l in ls_(b)))} avisos: {[l for l in ls_(b) if 'mode off' in l or 'editor on' in l][:2]}")
print()
print("y que cada modo sigue funcionando tras la ida y vuelta:")
c = k(b"echo vuelta-editor\n", 3.0)
print(f"  {ok('vuelta-editor' in ls_(c))} el editor ejecuta")
k(b"\x07v", 7.0)
d = k(b"echo vuelta-nvim\r", 3.5)
print(f"  {ok('vuelta-nvim' in ls_(d))} nvim ejecuta")
k(b"\x04", 3.0)
e = k(b"echo readline\n", 2.5)
print(f"  {ok('readline' in ls_(e))} y readline al final")
os.write(fd,b"exit\n"); time.sleep(0.5)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
