import os, pty, time, select, re
env={k:v for k,v in os.environ.items() if k!="BLE_VERSION"}
env["TERM"]="xterm-256color"; env["LAB_AUTO_EDITOR"]="0"
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
time.sleep(1.5); drain(3.0)
def k(d,q=2.0):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.08)
    drain(q); return buf
def outlines(b):
    """solo lineas que NO llevan prompt: o sea la salida real del comando"""
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','\n').split("\n")
            if l.strip() and "➜" not in l and not l.strip().startswith("[")]
def ok(c): return "OK  " if c else "FAIL"
k(b"\x07v", 6.0)
print("mirando la SALIDA del comando, no el prompt:")
cases = [
  (b"echo alpha beta",      [b"\x1b", b"b", b"ciwGAMMA"], "alpha GAMMA", "ciw cambia palabra"),
  (b"medio",                [b"\x1b", b"I", b"echo ", b"\x1b", b"A-final"], "medio-final", "I al inicio, A al final"),
  (b"echo uno dos tres",    [b"\x1b", b"b", b"dw"],       "uno dos",    "dw borra palabra"),
  (b"echo XXXvale",         [b"\x1b", b"0", b"5l", b"3x"], "vale",      "contador 3x"),
  (b"echo yankeo",          [b"\x1b", b"yiw", b"A ", b"\x1b", b"p"], "yankeo yankeo", "yiw y p"),
]
for typed, keys, expect, label in cases:
    k(typed, 1.2)
    for key in keys: k(key, 1.0)
    r = outlines(k(b"\r", 3.0))
    hit = any(x == expect for x in r)
    print(f"  {ok(hit)} {label:<24} salida={[x for x in r if x][:2]}  esperado={expect!r}")
k(b"\x04", 2.5)
os.write(fd,b"exit\n"); time.sleep(0.5)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
