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
def k(d,q=3.0):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.07)
    drain(q); return buf
def ls_(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','\n').split("\n") if l.strip()]
def ok(c): return "OK  " if c else "FAIL"
k(b"\x07v", 7.0)
print("acordes C-g dentro de nvim:")
# en NORMAL: Esc primero
a = ls_(k(b"\x1b\x07s", 5.0))
print(f"  {ok(any('On branch' in l for l in a))} Esc luego C-g s lanza git status")
print(f"  {ok(any('(auto)' in l for l in a))} muestra el aviso (auto)")
b = ls_(k(b"\x1b\x07h", 5.0))
print(f"  {ok(any(re.match(r'^[0-9a-f]{7,9} ', l) for l in b))} Esc luego C-g h lanza git log")
# el buffer a medio escribir vuelve?
k(b"echo pendiente", 2.0)
c = ls_(k(b"\x1b\x07f", 5.0))
print(f"  {ok(any('(auto)' in l for l in c))} con texto a medias lanza fetch")
d = ls_(k(b"\r", 3.0))
print(f"  {ok('pendiente' in d)} y el texto vuelve y se ejecuta -> {[x for x in d if x=='pendiente']}")
# en INSERCION C-g no debe robar nada
k(b"echo insercion", 2.0)
e = k(b"\x07", 2.0)
still = ls_(k(b"X\r", 3.0))
print(f"  {ok(any('insercion' in x for x in still))} en insercion C-g no rompe nada -> {[x for x in still if 'insercion' in x][:1]}")
k(b"\x04", 3.0)
os.write(fd,b"exit\n"); time.sleep(0.5)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
