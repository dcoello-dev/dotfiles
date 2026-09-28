import os, pty, time, select
D=os.path.expanduser("~/doc/shell-editor-poc")
env=dict(os.environ); env["TERM"]="xterm-256color"
def run(keys, label, expect):
    out="/tmp/bs2.txt"
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
    got = open(out).read().rstrip("\n") if os.path.exists(out) else "(nada)"
    flag = "OK  " if got == expect else "FAIL"
    print(f"  {flag} {label:<44} -> {got!r}  esperado {expect!r}")

run(b"hola\x1b[D\x1b[D\x1b[3~",  "flecha izq x2 y Supr",            "hoa")
run(b"hola\x1b[D\x1b[Dxy",       "flecha izq x2 e insertar",        "hoxyla")
run(b"hola\x1b[H_",              "Inicio e insertar",               "_hola")
run(b"ho\x1b[Fla",               "Fin e insertar",                  "hola")
run(b"if a < b",                 "escribir un < literal",           "if a < b")
run(b"a<Up>b",                   "escribir el texto <Up> literal",  "a<Up>b")
run(b"hola mundo\x1b[1;5Dzz",    "C-izquierda e insertar",          "hola zzmundo")
run(b"hola\x1b0iX",              "Esc 0 i X",                       "Xhola")
