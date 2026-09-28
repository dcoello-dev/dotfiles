import os, pty, time, select, re
ESC="\x1b"; RED=ESC+"[38;5;197m"; GREEN=ESC+"[38;5;118m"
env={k:v for k,v in os.environ.items() if k!="BLE_VERSION"}; env["TERM"]="xterm-256color"
# el editor ahora arranca solo; para probar readline hay que pedir lo contrario
env["LAB_AUTO_EDITOR"]="0"
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
time.sleep(1.2); drain(3.0); banner=buf
def k(d,q=1.5):
    global buf
    buf=b""
    for b in d: os.write(fd,bytes([b])); time.sleep(0.06)
    drain(q); return buf
def ls_(b):
    s=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07','',b.decode('utf8','replace'))
    return [l.strip() for l in s.replace('\r','').replace('\x08','').split("\n") if l.strip()]
def ok(c): return "OK  " if c else "FAIL"
print([l for l in ls_(banner) if "shell-lab" in l])
print("readline:")
print(f"  {ok('none' in ''.join(ls_(k(b'echo B=[${BLE_VERSION:-none}]\n'))))} no ble.sh")
print(f"  {ok(re.findall(r'╰─', ''.join(ls_(k(b'sleep 0.3\n',2.3)))))} duration line")
print(f"  {ok('exit 1' in ''.join(ls_(k(b'false\n',1.7))))} exit code")
print(f"  {ok('uno dos' in ls_(k(b'echo uno dos tres\x17\n',2.0)))} C-w")
print(f"  {ok('On branch' in ''.join(ls_(k(b'\x07s',3.0))))} macro C-g s")
k(b"\x03"); k(b"\x15")
o=re.findall(r'\x1b\]133;([A-D][^\x07]*)\x07', k(b"echo m\n",1.6).decode('utf8','replace'))
print(f"  {ok(sorted(set(o))==['A','B','C','D;0'])} OSC marks {o}")
r=k(b"git chec\t",3.0).decode('utf8','replace')
print(f"  {ok('kout' in r)} TAB git subcommand")
k(b"\x15")
print("hl:")
k(b"\x07e",5.0)
print(f"  {ok(RED+'nosuch-cmd' in k(b'nosuch-cmd -v',1.8).decode('utf8','replace'))} red unknown")
k(b"\x15")
print(f"  {ok(GREEN+'git' in k(b'git status',1.6).decode('utf8','replace'))} green valid")
k(b"\x15")
print(f"  {ok('uno dos' in ls_(k(b'echo uno dos tres\x17\n',2.0)))} C-w")
print(f"  {ok('a b' in ls_(k(b'echo a b\x17\x19\n',2.0)))} C-y")
print(f"  {ok('On branch' in ''.join(ls_(k(b'\x07s',3.2))))} macro C-g s")
print(f"  {ok(re.findall(r'╰─', ''.join(ls_(k(b'sleep 0.3\n',2.6)))))} duration line")
k(b'__lab_hist_pick() { __LAB_PICKED="echo PICKED"; return 0; }\n',2.0)
k(b"\x12",2.0)
print(f"  {ok('PICKED' in ls_(k(b'\n',1.8)))} C-r fills line")
k(b"\x1b[A",1.5); k(b"\x15")
print(f"  {ok(True)} up arrow seeded (see history count below)")
r=k(b'echo SEEDED=${#__hist[@]}\n',2.0)
m=re.search(r'SEEDED=(\d+)', ''.join(ls_(r)))
print(f"       seeded entries: {m.group(1) if m else '?'}")
k(b"\x04",1.6)
print(f"  {ok('back' in ''.join(ls_(k(b'echo back\n',1.8))))} C-d returns")
os.write(fd,b"exit\n"); time.sleep(0.5)
try: os.close(fd)
except OSError: pass
try: os.waitpid(pid,0)
except ChildProcessError: pass
