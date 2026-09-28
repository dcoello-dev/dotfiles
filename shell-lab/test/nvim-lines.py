import os, pty, time, select
D=os.path.expanduser("~/doc/shell-editor-poc")
env=dict(os.environ); env["TERM"]="xterm-256color"
def run(keys, label):
    out="/tmp/ol.txt"
    if os.path.exists(out): os.remove(out)
    pid,fd=pty.fork()
    if pid==0:
        os.chdir(os.path.expanduser("~/code"))
        os.execvpe("bash",["bash","-c",f"{D}/venv/bin/python {D}/nvline.py --prompt '> ' > {out}"],env)
    def drain(q,mx=20.0):
        s=time.time()
        while time.time()-s<mx:
            r,_,_=select.select([fd],[],[],q)
            if r:
                try: d=os.read(fd,1<<16)
                except OSError: return
                if not d: return
            else: return
    time.sleep(2.5); drain(2.5)
    for b in keys: os.write(fd,bytes([b])); time.sleep(0.09)
    drain(1.5); os.write(fd,b"\r"); time.sleep(1.2); drain(1.5)
    try: os.close(fd)
    except OSError: pass
    try: os.waitpid(pid,0)
    except ChildProcessError: pass
    got = open(out).read() if os.path.exists(out) else "(nada)"
    print(f"  {label:<40} -> {got!r}")
run(b"echo uno\x1boecho dos", "echo uno, Esc, o, echo dos")
run(b"echo uno", "una sola linea, de referencia")
