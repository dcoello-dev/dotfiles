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
time.sleep(1.3); drain(3.0)
def k(d,q=2.0):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.06)
    drain(q); return buf
def dur(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return re.findall(r'╰─\s*(\S+)', s.replace('\r','\n'))

print("  1. comando normal, de referencia:")
print("     ", dur(k(b"sleep 0.3\n", 2.5)) or "sin linea")
print("  2. lanzo la macro C-g s y espero 4 segundos sin hacer nada:")
k(b"\x07s", 3.0)
time.sleep(4.0); drain(0.5)
print("  3. y ahora un comando instantaneo. Su duracion deberia ser microsegundos:")
d = dur(k(b"true\n", 2.5))
print("     ", d or "sin linea (correcto si es rapido)")
print("     -> si aparece algo como 4s o mas, el cronometro arrastra el tiempo de espera")
print("  4. el registro del historial dice:")
r = k(b"histdb last 3\n", 3.0)
s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',r.decode('utf8','replace'))
for l in s.replace('\r','\n').split("\n"):
    if re.search(r'\d\d/\d\d \d\d:\d\d', l): print("     ", l.strip()[:80])
os.write(fd,b"exit\n"); time.sleep(0.5)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
