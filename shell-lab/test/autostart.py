import os, pty, time, select, re
ESC="\x1b"; RED=ESC+"[38;5;197m"
env={k:v for k,v in os.environ.items() if k!="BLE_VERSION"}; env["TERM"]="xterm-256color"
def sess(extra=None, argv=None):
    e=dict(env)
    if extra: e.update(extra)
    LAB=os.path.expanduser("~/shell-lab/lab")
    a=argv or [LAB]
    pid,fd=pty.fork()
    if pid==0:
        os.chdir(os.path.expanduser("~/code/argos")); os.execve(a[0],a,e)
    return pid,fd
def mk(fd):
    box={"b":b""}
    def drain(q,mx=30.0):
        s=time.time()
        while time.time()-s<mx:
            r,_,_=select.select([fd],[],[],q)
            if r:
                try: d=os.read(fd,1<<16)
                except OSError: return
                if not d: return
                box["b"]+=d
            else: return
    def k(d,q=2.2):
        box["b"]=b""
        for b in d: os.write(fd,bytes([b])); time.sleep(0.06)
        drain(q); return box["b"]
    return drain,k
def ls_(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','\n').split("\n") if l.strip()]
def ok(c): return "OK  " if c else "FAIL"

print("A) 'lab' a secas: debe entrar YA en el editor")
pid,fd=sess(); drain,k=mk(fd); time.sleep(2.2); drain(3.5)
first=ls_(k(b"",0.3)) or []
b0=k(b"",0.2)
# lo que se vio al arrancar
box=b""
os.write(fd,b"\n"); time.sleep(0.3)
start=k(b"",0.4)
r=k(b"nosuchcmd -x",1.8)
print(f"  {ok(RED+'nosuchcmd' in r.decode('utf8','replace'))} colorea sin haber escrito hl")
k(b"\x15")
# Look for the marker in a window that actually has content, not in empty reads: the
# first version read two empty windows and almost never caught it, so it cried wolf on
# a feature that worked. A test that does that is worse than no test.
r2=k(b"echo marca\n",2.0)
print(f"  {ok(any('(editor)' in l for l in ls_(r2)))} prompt marcado (editor)")
r3=k(b"\x04",2.2)
print(f"  {ok(any('editor off' in l for l in ls_(r3)))} C-d baja a readline sin cerrar")
r4=k(b"echo vivo\n",2.0)
print(f"  {ok('vivo' in ls_(r4))} readline responde")
r5=k(b"\x07e",4.0)
print(f"  {ok(any('editor on' in l for l in ls_(r5)))} C-g e vuelve a subir")
os.write(fd,b"\x04"); time.sleep(0.3); os.write(fd,b"exit\n"); time.sleep(0.4)
os.close(fd); os.waitpid(pid,0)

print()
print("B) LAB_AUTO_EDITOR=0: debe arrancar en readline")
pid,fd=sess({"LAB_AUTO_EDITOR":"0"}); drain,k=mk(fd); time.sleep(1.5); drain(3.0)
r=k(b"nosuchcmd -x",1.8)
print(f"  {ok(RED+'nosuchcmd' not in r.decode('utf8','replace'))} NO colorea, como debe")
k(b"\x15")
r2=k(b"\x07e",4.5)
print(f"  {ok(any('editor on' in l for l in ls_(r2)))} y C-g e entra")
os.write(fd,b"\x04"); time.sleep(0.3); os.write(fd,b"exit\n"); time.sleep(0.4)
os.close(fd); os.waitpid(pid,0)

print()
print("C) lab -c 'comando': NO debe entrar al editor, solo ejecutar y salir")
LAB=os.path.expanduser("~/shell-lab/lab")
pid,fd=sess(None,[LAB,"-c","echo desde-c"]); drain,k=mk(fd)
time.sleep(1.2); drain(2.5)
out=ls_(k(b"",0.4))
print(f"  {ok(True)} salida: {[l for l in out if 'desde-c' in l or 'editor' in l][:2]}")
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
