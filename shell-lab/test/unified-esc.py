import os, pty, time, select, re
env={k:v for k,v in os.environ.items() if k!="BLE_VERSION"}; env["TERM"]="xterm-256color"
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
time.sleep(2.5); drain(3.5)
first=buf
def k(d,q=3.0):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.08)
    drain(q); return buf
def out(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','\n').split("\n")
            if l.strip() and "➜" not in l and not l.strip().startswith("[")]
def ls_(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','\n').split("\n") if l.strip()]
def ok(c): return "OK  " if c else "FAIL"
print("aviso:", [l for l in ls_(first) if "Esc" in l][:1])
print()
print("un solo prompt, y Esc da el modo normal de vim:")
k(b"echo uno dos tres", 2.0)
a = k(b"\x1b", 4.0)
print(f"  {ok(any('(nvim)' in l for l in ls_(a)))} Esc pasa a nvim -> {[l for l in ls_(a) if '(nvim)' in l][-1:]}")
b = out(k(b"dw\r", 3.5))
# Correct vim behaviour, and my expectation was wrong at first: pressing Esc from
# insert mode puts the cursor ON the last character, not after it, so `dw` deletes from
# there. `echo uno dos tres` becomes `echo uno dos tre`. Asserting `uno dos` made the
# suite cry wolf about something that was right.
print(f"  {ok('uno dos tre' in b)} Esc deja el cursor en el ultimo caracter y dw borra desde ahi -> {b[:1]}")
# el siguiente prompt vuelve al editor rapido
c = k(b"echo vuelta", 2.5)
marker = [l for l in ls_(c) if '(editor)' in l]
print(f"  {ok(bool(marker))} el prompt siguiente es el editor -> {marker[-1:] if marker else 'no visto'}")
d = out(k(b"\r", 3.0))
print(f"  {ok('vuelta' in d)} y ejecuta -> {d[:1]}")
# Esc, yank, paste
k(b"echo alpha", 2.0); k(b"\x1b", 4.0)
e = out(k(b"yiwA \x1bp\r", 4.0))
print(f"  {ok(any('alpha alpha' in x for x in e))} Esc, yiw, A, p -> {[x for x in e if 'alpha' in x][:1]}")
# multilinea sigue en el editor rapido
k(b"for i in 1 2; do\n", 3.0)
f_ = out(k(b"echo n=$i\ndone\n", 4.0))
print(f"  {ok('n=1' in f_ and 'n=2' in f_)} multilinea del editor sigue -> {[x for x in f_ if x.startswith('n=')]}")
os.write(fd,b"\x04"); time.sleep(0.8); os.write(fd,b"exit\n"); time.sleep(0.6)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
