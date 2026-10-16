import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from .core import Member, Planner, Rule, health_percent
from .desktop import Desktop, foreground_process

CONFIG = Path.home() / ".config" / "aion-healer" / "config.json"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Assistente de cura — configuração")
        self.stop_event = threading.Event()
        self.worker = None
        self.desktop = None
        self.events = queue.Queue()
        self.rows = []
        self.rules = []
        self.simulate = tk.BooleanVar(value=True)
        self.process = tk.StringVar()
        self.delay = tk.StringVar(value="1.5")
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Linux • calibre com barras cheias • simulação ativada ao abrir").pack(anchor="w")
        ttk.Label(frame, text="Processo exato do jogo (campo obrigatório para enviar teclas):").pack(anchor="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self.process).pack(fill="x")
        ttk.Button(frame, text="Detectar processo em 4s — depois clique no jogo", command=self.detect).pack(anchor="w")
        table = ttk.Frame(frame)
        table.pack(pady=10)
        for col, title in enumerate(["Ativo", "Membro", "Seleção", "Barra: x,y,largura,altura", "Cor RGB (hex)", "Calibrar"]):
            ttk.Label(table, text=title).grid(row=0, column=col, padx=4)
        for i in range(6):
            enabled = tk.BooleanVar(value=False)
            values = [tk.StringVar(value=v) for v in [f"Membro {i + 1}", f"f{i + 1}", "0,0,100,10", "00cc44"]]
            ttk.Checkbutton(table, variable=enabled).grid(row=i + 1, column=0)
            for j, value in enumerate(values):
                ttk.Entry(table, textvariable=value, width=[14, 8, 25, 12][j]).grid(row=i + 1, column=j + 1, padx=3)
            ttk.Button(table, text="Selecionar", command=lambda n=i: self.calibrate(n)).grid(row=i + 1, column=5)
            self.rows.append((enabled, values))
        ttk.Label(frame, text="Regras: vida restante ≤ limite; prioridade para menor vida e menor limite disponível.").pack(anchor="w")
        rule_frame = ttk.Frame(frame)
        rule_frame.pack(anchor="w")
        for col, title in enumerate(["Vida restante %", "Tecla de cura", "Recarga (s)"]):
            ttk.Label(rule_frame, text=title).grid(row=0, column=col)
        for i, defaults in enumerate([("30", "1", "8"), ("60", "2", "3"), ("80", "3", "2")]):
            row = [tk.StringVar(value=v) for v in defaults]
            for j, value in enumerate(row):
                ttk.Entry(rule_frame, textvariable=value, width=18).grid(row=i + 1, column=j, padx=3)
            self.rules.append(row)
        ttk.Label(frame, text="Intervalo mínimo entre ações (s), incluindo tempo de conjuração:").pack(anchor="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.delay, width=12).pack(anchor="w")
        ttk.Checkbutton(frame, text="Simulação: registrar decisões sem enviar teclas", variable=self.simulate).pack(anchor="w", pady=8)
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="w")
        for label, callback in [("Salvar", self.save), ("Iniciar", self.start), ("Parar", self.stop)]:
            ttk.Button(buttons, text=label, command=callback).pack(side="left", padx=3)
        ttk.Label(frame, text="Parar: botão acima ou encerre o compartilhamento no desktop. Alt+Tab suspende o envio.").pack(anchor="w", pady=8)
        self.log = tk.Text(frame, height=9, width=95, state="disabled")
        self.log.pack(fill="both", expand=True)
        self.load()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def write(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S ") + text + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 300:
            self.log.delete("1.0", "50.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll(self):
        try:
            while True:
                self.write(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def stopped(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Em execução", "Pare a execução antes de alterar a configuração.")
            return False
        return True

    def detect(self):
        if not self.stopped():
            return
        self.write("Clique na janela do jogo. Detectando em 4 segundos…")
        self.root.after(4000, self.finish_detect)

    def finish_detect(self):
        try:
            name = foreground_process()
            if not name:
                raise ValueError("A janela não informa seu processo. Preencha o nome manualmente.")
            self.process.set(name)
            self.write("Processo detectado: " + name)
        except Exception as exc:
            messagebox.showerror("Detecção", str(exc))

    def calibrate(self, index):
        if not self.stopped():
            return
        messagebox.showinfo("Calibrar", "Deixe a barra CHEIA e visível. Após confirmar, em 3 segundos arraste um retângulo apenas no interior colorido da barra, sem borda nem texto.")
        self.root.withdraw()
        self.root.after(3000, lambda: self.capture_region(index))

    def capture_region(self, index):
        try:
            shot = self.get_desktop().screenshot()
            from PIL import ImageTk
            overlay = tk.Toplevel(self.root)
            overlay.overrideredirect(True)
            overlay.geometry(f"{shot.width}x{shot.height}+0+0")
            overlay.attributes("-topmost", True)
            canvas = tk.Canvas(overlay, width=shot.width, height=shot.height, highlightthickness=0)
            canvas.pack()
            photo = ImageTk.PhotoImage(shot)
            canvas.image = photo
            canvas.create_image(0, 0, image=photo, anchor="nw")
            origin = []
            rectangle = [None]
            def cancel(event=None):
                overlay.destroy()
                self.root.deiconify()
            def down(event):
                origin[:] = [event.x, event.y]
            def drag(event):
                if not origin:
                    return
                if rectangle[0]:
                    canvas.delete(rectangle[0])
                rectangle[0] = canvas.create_rectangle(*origin, event.x, event.y, outline="yellow", width=2)
            def up(event):
                if not origin:
                    return
                x, y = min(origin[0], event.x), min(origin[1], event.y)
                w, h = abs(event.x - origin[0]), abs(event.y - origin[1])
                cancel()
                if w < 10 or h < 2:
                    messagebox.showerror("Calibrar", "Selecione uma região de pelo menos 10 × 2 pixels.")
                    return
                crop = shot.crop((x, y, x + w, y + h)).convert("RGB")
                pixels = list(crop.getdata())
                color = tuple(sorted(p[channel] for p in pixels)[len(pixels) // 2] for channel in range(3))
                enabled, fields = self.rows[index]
                fields[2].set(f"{x},{y},{w},{h}")
                fields[3].set("%02x%02x%02x" % color)
                enabled.set(True)
                self.write(f"Barra {index + 1} calibrada. Confira a leitura em simulação.")
            canvas.bind("<ButtonPress-1>", down)
            canvas.bind("<B1-Motion>", drag)
            canvas.bind("<ButtonRelease-1>", up)
            overlay.bind("<Escape>", cancel)
            overlay.focus_force()
        except Exception as exc:
            self.root.deiconify()
            messagebox.showerror("Captura", str(exc))

    def parse(self, desktop):
        members = []
        for enabled, fields in self.rows:
            if not enabled.get():
                continue
            name, key, region, color = [v.get().strip() for v in fields]
            rect = tuple(int(v.strip()) for v in region.split(","))
            if len(rect) != 4 or min(rect[:2]) < 0 or rect[2] < 10 or rect[3] < 2:
                raise ValueError("Região inválida: use x,y,largura,altura; mínimo 10 × 2.")
            if not desktop.valid_key(key):
                raise ValueError(f"Tecla de seleção inválida: {key}")
            color = color.removeprefix("#")
            if len(color) != 6:
                raise ValueError("Cor deve ter 6 dígitos hexadecimais.")
            rgb = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
            members.append(Member(name, key, rect, rgb))
        if not members:
            raise ValueError("Calibre e ative pelo menos um membro.")
        rules = [Rule(float(row[0].get()), row[1].get().strip(), float(row[2].get())) for row in self.rules]
        import math
        if any(not math.isfinite(r.threshold) or not 0 < r.threshold <= 100 or not math.isfinite(r.cooldown) or r.cooldown < 0 or not desktop.valid_key(r.key) for r in rules):
            raise ValueError("Regras inválidas: vida entre 0 e 100, recarga ≥ 0, tecla válida.")
        delay = float(self.delay.get())
        if not math.isfinite(delay) or delay < 0.5:
            raise ValueError("Use intervalo de pelo menos 0,5 segundo.")
        simulate = self.simulate.get()
        process = self.process.get().strip()
        if not simulate and not process:
            raise ValueError("Detecte ou informe o processo do jogo antes de enviar teclas.")
        if not simulate:
            desktop.focused(process)  # Fail before starting if the focus integration is absent.
        shot = desktop.screenshot()
        for member in members:
            x, y, w, h = member.region
            if x + w > shot.width or y + h > shot.height:
                raise ValueError("Uma barra está fora dos limites da tela.")
        return members, rules, delay, simulate, process

    def start(self):
        if not self.stopped():
            return
        try:
            desktop = self.get_desktop()
            config = self.parse(desktop)
        except Exception as exc:
            messagebox.showerror("Não foi possível iniciar", str(exc))
            return
        self.stop_event.clear()
        self.worker = threading.Thread(target=self.run, args=(desktop, config), daemon=True)
        self.worker.start()
        self.write("Iniciado. Configuração congelada até parar; selecione o jogo para operar.")

    def get_desktop(self):
        if self.desktop is None:
            self.desktop = Desktop()
        return self.desktop

    def run(self, desktop, config):
        members, rules, delay, simulate, process = config
        planner = Planner()
        last_report = float("-inf")
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                if not simulate and not desktop.focused(process):
                    self.stop_event.wait(0.25)
                    continue
                shot = desktop.screenshot()
                readings = []
                for member in members:
                    x, y, w, h = member.region
                    readings.append((member, health_percent(shot.crop((x, y, x + w, y + h)), member.color)))
                if now - last_report >= 2:
                    self.events.put(" | ".join(f"{m.name}: {'sem leitura' if hp is None else str(hp) + '%'}" for m, hp in readings))
                    last_report = now
                choice = planner.choose(readings, rules, now, delay)
                if choice:
                    member, hp, rule = choice
                    if simulate or desktop.cast(member, rule, process, self.stop_event):
                        planner.record(rule, time.monotonic())
                        self.events.put(f"{'SIMULAÇÃO' if simulate else 'TECLAS ENVIADAS'}: {member.name} {hp}% → {member.target_key}, {rule.key}")
                self.stop_event.wait(0.25)
        except Exception as exc:
            self.events.put(f"Interrompido: {exc}")
        finally:
            self.stop_event.set()
            self.events.put("Parado.")

    def stop(self):
        self.stop_event.set()

    def save(self):
        data = {"members": [{"enabled": enabled.get(), "fields": [v.get() for v in fields]} for enabled, fields in self.rows],
                "rules": [[v.get() for v in row] for row in self.rules], "process": self.process.get(), "delay": self.delay.get()}
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temporary = CONFIG.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(CONFIG)
            self.write("Configuração salva em " + str(CONFIG))
        except OSError as exc:
            messagebox.showerror("Salvar", str(exc))

    def load(self):
        if not CONFIG.exists():
            return
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            for (enabled, fields), saved in zip(self.rows, data["members"]):
                enabled.set(bool(saved["enabled"]))
                for field, value in zip(fields, saved["fields"]):
                    field.set(value)
            for row, saved in zip(self.rules, data["rules"]):
                for field, value in zip(row, saved):
                    field.set(value)
            self.process.set(data["process"])
            self.delay.set(data["delay"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.write("Não foi possível carregar configuração: " + str(exc))

    def close(self):
        self.stop()
        if self.worker:
            self.worker.join(timeout=5)
        if self.desktop:
            self.desktop.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
