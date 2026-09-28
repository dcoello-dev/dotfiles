import os, pty, time, select, re, sys
D=os.path.expanduser("~/doc/shell-editor-poc")
env=dict(os.environ); env["TERM"]="xterm-256color"; env["NVLINE_DEBUG"]="/tmp/nvl.dbg"
gap=float(sys.argv[1])
pid,fd=pty.fork()
if pid==0:
    os.chdir(os.path.expanduser("~/code/argos"))
    os.execvpe("bash",["bash","-c",
      f"{D}/venv/bin/python {D}/nvline.py --prompt '> ' --cols 80 --chords 'hmacfgps<' >/tmp/g2.out; echo RC=$?"],env)
def wait(t):
    t0=time.time(); buf=b""
    while time.time()-t0<t:
        r,_,_=select.select([fd],[],[],0.3)
        if r:
            try: buf+=os.read(fd,1<<16)
            except OSError: break
        else: break
    return buf
wait(3.2)
os.write(fd,b"\x1b"); time.sleep(gap)
os.write(fd,b"\x07"); time.sleep(gap)
os.write(fd,b"s")
out=wait(8.0)
txt=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]','',out.decode('utf8','replace'))
m=re.search(r'RC=(\d+)',txt)
print(f"  gap={gap}s  RC={m.group(1) if m else 'sin salir'}  out={open('/tmp/g2.out').read()!r}")
if not m:
    os.write(fd,b"\x03"); time.sleep(0.3); os.write(fd,b"\x04"); time.sleep(0.6)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
