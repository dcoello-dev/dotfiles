import os, pty, time, select, re
env={k:v for k,v in os.environ.items() if k!="BLE_VERSION"}
env["TERM"]="xterm-256color"; env["LAB_AUTO_EDITOR"]="0"
LAB=os.path.expanduser("~/shell-lab/lab")
pid,fd=pty.fork()
if pid==0: os.chdir(os.path.expanduser("~/code/argos")); os.execve(LAB,[LAB],env)
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
time.sleep(1.5); drain(3.0)
def k(d,q=2.5):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.05)
    drain(q); return buf
def ls_(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','\n').split("\n") if l.strip()]
def ok(c): return "OK  " if c else "FAIL"

print("entro en modo nvim con C-g v:")
a = k(b"\x07v", 6.0)
print(f"  {ok(any('nvim mode' in l for l in ls_(a)))} arranca -> {[l for l in ls_(a) if 'nvim' in l][:1]}")
print(f"  {ok(any('(nvim)' in l for l in ls_(a)))} prompt marcado (nvim)")
b = k(b"for i in 1 2; do echo n=$i; done", 2.5)
raw = b.decode('utf8','replace')
cols = set(re.findall(r'\x1b\[0;38;2;(\d+;\d+;\d+)', raw))
print(f"  {ok(len(cols) >= 3)} resaltado con {len(cols)} colores distintos")
print(f"  {ok(True)} muestra: {sorted(cols)[:4]}")
c = k(b"\r", 3.0)
got = ls_(c)
print(f"  {ok('n=1' in got and 'n=2' in got)} Enter ejecuta -> {[x for x in got if x.startswith('n=')]}")
d = k(b"\x04", 3.0)
print(f"  {ok(any('nvim mode off' in l for l in ls_(d)))} C-d sale")
e = k(b"echo readline-vivo\n", 2.0)
print(f"  {ok('readline-vivo' in ls_(e))} readline responde")
os.write(fd,b"exit\n"); time.sleep(0.5)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
